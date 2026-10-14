"""Structured model contracts and deterministic answer validation."""
import ast
import math
import operator
import re
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, create_model


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedUnit(StrictModel):
    key: str
    text: str
    summary: str
    uncertainty: str


class ExtractedBatch(StrictModel):
    units: list[ExtractedUnit]


class Selection(StrictModel):
    status: Literal["ready", "insufficient_source", "clarification_needed"]
    message: str
    sourceIds: list[str]


class GeneratedQuestion(StrictModel):
    id: str
    type: Literal["mcq", "flashcard", "calculation"]
    prompt: str
    answer: str
    explanation: str
    steps: list[str]
    sourceId: str
    quote: str
    options: list[str]
    correctIndex: int | None
    numericAnswer: float | None
    tolerance: float | None
    arithmetic: str | None


class GeneratedQuiz(StrictModel):
    status: Literal["ready", "insufficient_source", "clarification_needed"]
    message: str
    title: str
    description: str
    questions: list[GeneratedQuestion]


class GeneratedSheetSection(StrictModel):
    heading: str
    points: list[str]
    formulas: list[str]
    sourceId: str
    quote: str


class GeneratedCheatSheet(StrictModel):
    status: Literal["ready", "insufficient_source", "clarification_needed"]
    message: str
    title: str
    description: str
    sections: list[GeneratedSheetSection]


def sheet_excerpts(source):
    """Evidence choices are exact slices, including original technical notation."""
    text = source['text']
    parts = [p.strip() for p in re.split(r'\n\s*\n|(?<=[.!?])\s+(?=[A-Z])', text) if p.strip()]
    # Keep full source context available for sections spanning several statements.
    excerpts = list(dict.fromkeys(parts[:11] + [text]))
    return [{'id': source['id'] + ':e' + str(i), 'text': quote} for i, quote in enumerate(excerpts)]


def sheet_generation_schema(sources):
    if not sources:
        return GeneratedCheatSheet
    ids = tuple(dict.fromkeys(s['id'] for s in sources))
    quotes = tuple(q['id'] for s in sources for q in sheet_excerpts(s))
    fields = {name: (field.annotation, field) for name, field in GeneratedSheetSection.model_fields.items()
              if name not in ('sourceId', 'quote')}
    section = create_model('CitedSheetSection', __base__=StrictModel,
                           sourceId=(Literal[ids], ...), quoteId=(Literal[quotes], ...), **fields)
    return create_model('CitedCheatSheet', __base__=GeneratedCheatSheet,
                        sections=(list[section], ...))


@lru_cache(maxsize=4)
def generation_schema(format_):
    """Constrain the chosen format at the provider; IDs belong to the application."""
    if format_ == 'cheatsheet':
        return GeneratedCheatSheet
    if format_ not in ('mcq', 'flashcard', 'calculation'):
        raise ValueError('Unsupported quiz format')
    fields = {name: (field.annotation, field) for name, field in GeneratedQuestion.model_fields.items()
              if name not in ('id', 'type')}
    question = create_model('Question_' + format_, __base__=StrictModel,
                            type=(Literal[format_], ...), **fields)
    return create_model('Quiz_' + format_, __base__=GeneratedQuiz,
                        questions=(list[question], ...))


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow}


def arithmetic_value(expression):
    """Evaluate numeric literals and arithmetic only. No names/calls/attributes."""
    if not isinstance(expression, str) or len(expression) > 400:
        raise ValueError("Calculation needs a short arithmetic expression")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 80:
        raise ValueError("Calculation expression is too complex")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            result = float(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            result = (-1 if isinstance(node.op, ast.USub) else 1) * visit(node.operand)
        elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and (abs(right) > 10 or abs(left) > 1e12):
                raise ValueError("Exponent exceeds calculation limits")
            result = OPS[type(node.op)](left, right)
        else:
            raise ValueError("Only numeric arithmetic is allowed")
        if not isinstance(result, (int, float)) or not math.isfinite(result) or abs(result) > 1e15:
            raise ValueError("Calculation result is outside supported limits")
        return result

    try:
        return visit(tree.body)
    except (ZeroDivisionError, OverflowError, SyntaxError, TypeError) as exc:
        raise ValueError("Invalid calculation expression") from exc


def normalize(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def resolve_source(item, sources):
    source = {s['id']: s for s in sources}.get(item.pop('sourceId'))
    if not source:
        raise ValueError('A generated reference does not belong to this material')
    quote = item.pop('quote')
    if not quote.strip() or normalize(quote) not in normalize(source['text']):
        raise ValueError('A supporting excerpt does not match the extracted source')
    original_id = source.get('originalSourceId', source['id'])
    return {'id': original_id, 'chunkId': source['id'], 'name': source['name'],
            'locator': source['locator'], 'quote': quote, 'kind': source['kind'],
            'page': source.get('page'), 'start': source.get('start'),
            'url': '/api/sources/' + original_id}


def validate_cheatsheet(raw, sources, count):
    if isinstance(raw, dict) and isinstance(raw.get('sections'), list):
        evidence = {q['id']: (s['id'], q['text']) for s in sources for q in sheet_excerpts(s)}
        sections = []
        for section in raw['sections']:
            if isinstance(section, dict) and 'quoteId' in section:
                section = dict(section)
                selected = evidence.get(section.pop('quoteId'))
                if not selected or selected[0] != section.get('sourceId'):
                    raise ValueError('The selected excerpt does not belong to its cited source')
                section['quote'] = selected[1]
            sections.append(section)
        raw = {**raw, 'sections': sections}
    data = GeneratedCheatSheet.model_validate(raw).model_dump()
    data['questions'] = []  # Saved artifacts share the existing storage/API envelope.
    if data['status'] != 'ready':
        return data
    if not data['title'].strip() or len(data['title']) > 180:
        raise ValueError('The cheat sheet needs a short title')
    if len(data['sections']) != count:
        raise ValueError(f"The model returned {len(data['sections'])} sections instead of {count}")
    headings = set()
    for i, section in enumerate(data['sections']):
        heading = normalize(section['heading'])
        if not heading or heading in headings or len(section['heading']) > 120:
            raise ValueError('Cheat sheet headings must be short and distinct')
        headings.add(heading)
        if not 1 <= len(section['points']) <= 5 or len(section['formulas']) > 3:
            raise ValueError('Each section needs 1–5 key points and at most 3 formulas')
        if any(not t.strip() or len(t) > 1000 for t in section['points'] + section['formulas']):
            raise ValueError('Cheat sheet content is empty or too long')
        section['id'] = 's' + str(i)
        section['source'] = resolve_source(section, sources)
    return data


def validate_quiz(raw, sources, format_, count):
    if format_ == 'cheatsheet':
        return validate_cheatsheet(raw, sources, count)
    if isinstance(raw, dict) and isinstance(raw.get('questions'), list):
        raw = {**raw, 'questions': [{**q, 'id': 'q' + str(i)} if isinstance(q, dict) else q
                                  for i, q in enumerate(raw['questions'])]}
    data = GeneratedQuiz.model_validate(raw).model_dump()
    if data["status"] != "ready":
        return data
    questions = data["questions"]
    if len(questions) != count:
        raise ValueError(f"The model returned {len(questions)} questions instead of {count}")
    if not data["title"].strip() or len(data["title"]) > 180:
        raise ValueError("The generated quiz needs a short title")
    for q in questions:
        if q['type'] != format_:
            raise ValueError(f"The model returned {q['type']} questions; the selected format is {format_}")
        if not all(q[k].strip() for k in ("prompt", "answer", "explanation", "quote")):
            raise ValueError("A question is missing its explanation or supporting excerpt")
        q['source'] = resolve_source(q, sources)
        if format_ == "mcq":
            if len(q["options"]) != 4 or len(set(q["options"])) != 4:
                raise ValueError("Multiple-choice questions need four distinct options")
            if q["correctIndex"] is None or not 0 <= q["correctIndex"] < 4:
                raise ValueError("A correct-option index is invalid")
            if normalize(q["answer"]) != normalize(q["options"][q["correctIndex"]]):
                raise ValueError("A multiple-choice answer disagrees with its correct option")
        elif format_ == "calculation":
            if q["numericAnswer"] is None or q["tolerance"] is None or not 0 <= q["tolerance"] <= 1:
                raise ValueError("A calculation needs a numeric answer and tolerance")
            if not q["steps"]:
                raise ValueError("A calculation needs worked steps")
            expected = arithmetic_value(q["arithmetic"])
            if not math.isclose(expected, q["numericAnswer"], rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("A calculation answer disagrees with its arithmetic")
            try:
                displayed = float(q["answer"].replace("−", "-"))
            except ValueError as exc:
                raise ValueError("Calculation answer must be a scalar number without units") from exc
            if not math.isclose(displayed, expected, rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("The displayed calculation answer is inconsistent")
    return data
