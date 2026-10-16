"""Source-backed follow-up practice from the latest saved, objectively graded answers."""
import math
from difflib import SequenceMatcher
import re
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


NUMBER = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$', re.I | re.ASCII)


def missed_questions(quiz):
    """Regrade stored attempts; a client-supplied correct flag is not evidence."""
    if quiz.get('format') not in ('mcq', 'calculation') or quiz.get('mode') != 'generated':
        return []
    answers = (quiz.get('progress') or {}).get('answers', {})
    result = []
    for q in quiz['questions']:
        a = answers.get(q['id'], {})
        if not isinstance(a, dict) or a.get('submitted') is not True:
            continue
        skipped = a.get('skipped') is True
        if skipped:
            correct, value = False, None
        elif q['type'] == 'mcq':
            selected = a.get('selected')
            if type(selected) is not int or not 0 <= selected < len(q['options']):
                continue
            correct, value = selected == q['correctIndex'], q['options'][selected]
        elif q['type'] == 'calculation':
            value = str(a.get('gradedValue', a.get('value', ''))).strip()
            if len(value) > 200 or not NUMBER.fullmatch(value):
                continue
            number = float(value)
            if not math.isfinite(number):
                continue
            expected = q['numericAnswer']
            correct = abs(number - expected) <= q['tolerance'] + 2.220446049250313e-16 * max(1, abs(expected))
        else:
            continue
        if not correct:
            result.append({'questionId': q['id'], 'prompt': q['prompt'],
                           'studentAnswer': value, 'status': 'skipped' if skipped else 'incorrect',
                           'source': q['source']})
    return result


def near_repeat(prompt, previous):
    """Conservative wording guard; changed numerical givens can be legitimate new practice."""
    from schemas import normalize
    current = normalize(prompt)
    numbers = re.findall(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?', current)
    for original in previous:
        other = normalize(original)
        if numbers != re.findall(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?', other):
            continue
        if SequenceMatcher(None, current, other).ratio() >= .82:
            return True
    return False


class MistakeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    questionIds: list[str] = Field(min_length=1, max_length=12)
    count: Literal[4, 6, 8, 10] = 4
    requestId: str = Field(min_length=8, max_length=80)


def register_mistake_routes(app, store, engine, create_quiz, request_model, require_collection, mutation_lock):
    def parent(quiz_id):
        quiz = store.quiz(quiz_id)
        if not quiz:
            raise HTTPException(404, 'Quiz not found.')
        require_collection(quiz['collectionId'])
        if quiz['format'] not in ('mcq', 'calculation'):
            raise HTTPException(400, 'Mistake practice is available for graded quizzes and calculations.')
        return quiz

    @app.get('/api/quizzes/{quiz_id}/mistakes')
    def preview(quiz_id: str):
        quiz = parent(quiz_id)
        return {'quizId': quiz_id, 'title': quiz['title'], 'format': quiz['format'],
                'questions': missed_questions(quiz)}

    @app.post('/api/quizzes/{quiz_id}/mistakes', status_code=202)
    def generate(quiz_id: str, request: MistakeRequest):
        with mutation_lock:
            quiz = parent(quiz_id)
            existing = store.one("SELECT id,material_id FROM jobs WHERE kind='quiz' "
                "AND json_extract(params,'$.parentQuizId')=? "
                "AND json_extract(params,'$.mistakePractice.requestId')=? ORDER BY created DESC LIMIT 1",
                (quiz_id, request.requestId))
            if existing:
                return {'jobId': existing['id'], 'materialId': existing['material_id']}
            ids = list(dict.fromkeys(request.questionIds))
            missed = {q['questionId']: q for q in missed_questions(quiz)}
            if not set(ids) <= missed.keys():
                raise HTTPException(400, 'Choose currently incorrect or skipped questions. Reopen mistake practice to refresh the list.')
            focus = [missed[qid] for qid in ids]
            mids = []
            general = quiz.get('grounding') == 'general'
            for item in focus:
                if general and item['source'].get('kind') == 'general':
                    continue
                source = store.one('SELECT s.material_id,mc.collection_id FROM sources s '
                    'JOIN material_collections mc ON mc.material_id=s.material_id WHERE s.id=?', (item['source'].get('id'),))
                if not source or source['collection_id'] != quiz['collectionId']:
                    raise HTTPException(400, 'A lecture source is unavailable. Choose another question.')
                if source['material_id'] not in mids:
                    mids.append(source['material_id'])
            practice = {'requestId': request.requestId, 'questionIds': ids, 'materialIds': mids,
                'questions': [{'questionId': q['questionId'], 'prompt': q['prompt'][:1800],
                    'studentAnswer': str(q['studentAnswer'])[:1000] if q['studentAnswer'] is not None else None,
                    'status': q['status'], 'sourceId': q['source'].get('id'),
                    'sourceQuote': q['source'].get('quote', '')} for q in focus]}
            prompt = ('Practice my mistakes. Create new questions testing the concepts behind the selected '
                      'incorrect or skipped questions. Use different wording and examples. Keep the original '
                      'difficulty and provide useful explanations grounded in the lecture. '
                      'Test application or interpretation in new scenarios, not a paraphrase of an earlier question. '
                      'Focus only on these selected questions:\n' + '\n'.join(q['prompt'][:200] for q in focus))
            return create_quiz(request_model(collectionId=quiz['collectionId'], parentQuizId=quiz_id,
                prompt=prompt, format=quiz['format'], count=request.count), mistake_practice=practice, allow_general=general)
