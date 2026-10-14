from types import SimpleNamespace
import pytest
from ai import AI
from schemas import Selection


def test_structured_sdk_contract(monkeypatch):
    captured = {}
    def parse(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status="completed", output_parsed=Selection(status="insufficient_source", message="Not present", sourceIds=[]))
    ai = AI()
    monkeypatch.setattr(ai, "client", lambda: SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    result = ai.structured("system", [{"type": "input_text", "text": "notes"}], Selection)
    assert result["status"] == "insufficient_source"
    assert captured["store"] is False
    assert captured["text_format"] is Selection


def test_incomplete_output_is_not_success(monkeypatch):
    ai = AI()
    monkeypatch.setattr(ai, "client", lambda: SimpleNamespace(responses=SimpleNamespace(parse=lambda **kw: SimpleNamespace(status="incomplete", output_parsed=None))))
    with pytest.raises(ValueError, match="complete structured"):
        ai.structured("system", [], Selection)

@pytest.mark.parametrize('format_', ['mcq','flashcard','calculation'])
def test_generation_schema_locks_selected_format(format_, monkeypatch):
    from schemas import generation_schema
    schema=generation_schema(format_).model_json_schema()
    question=schema['$defs']['Question_'+format_]
    assert question['properties']['type']['const']==format_
    assert 'id' not in question['properties']
    captured={}
    ai=AI()
    def structured(system,content,schema):
        captured.update(system=system,content=content,schema=schema)
        return {'status':'insufficient_source','message':'fixture','title':'','description':'','questions':[]}
    monkeypatch.setattr(ai,'structured',structured)
    ai.generate({'prompt':'Create four flashcards','format':format_,'count':4,'difficulty':'beginner'},[])
    assert captured['schema'] is generation_schema(format_)
    assert 'authoritative' in captured['system']
    assert r'\( ... \)' in captured['system']
    assert r'W^{\mathrm{new}}' in captured['system']
    assert 'bare scalar numeric string' in captured['system']
    assert 'After JSON decoding' in captured['system']
    assert 'standalone' in captured['system']
    assert 'Do not reveal the computed answer in the prompt' in captured['system']
    assert 'never rewrite cited source text' in captured['system']


def test_question_ids_are_application_assigned():
    from test_app import FakeAI,NOTES
    from schemas import validate_quiz
    sources=[{'id':'s','name':'Lecture','kind':'text','locator':'Notes','text':NOTES}]
    raw=FakeAI().generate({'format':'mcq','count':4},sources)
    for q in raw['questions']:
        q['id']='duplicate'
    validated=validate_quiz(raw,sources,'mcq',4)
    assert [q['id'] for q in validated['questions']]==['q0','q1','q2','q3']
    for q in raw['questions']:
        del q['id']
    assert len(validate_quiz(raw,sources,'mcq',4)['questions'])==4
    raw['questions'][0]['type']='flashcard'
    with pytest.raises(ValueError,match='selected format'):
        validate_quiz(raw,sources,'mcq',4)


def test_source_selection_schema_rejects_invented_ids(monkeypatch):
    import json
    from pydantic import ValidationError
    ai = AI(); captured = {}
    sources = [{'id': 'chunk-a', 'locator': 'Page 1', 'text': 'Warehouse data supports decisions.'},
               {'id': 'chunk-b', 'locator': 'Page 2', 'text': 'Facts contain measurements.'}]
    def structured(system, content, schema):
        captured.update(schema=schema, input=json.loads(content[0]['text']))
        return schema(status='ready', message='', sourceIds=['chunk-b']).model_dump()
    monkeypatch.setattr(ai, 'structured', structured)
    result = ai.select('Key lecture concepts', sources)
    assert result['sourceIds'] == ['chunk-b']
    assert {s['id'] for s in captured['input']['sources']} == {'chunk-a', 'chunk-b'}
    with pytest.raises(ValidationError):
        captured['schema'](status='ready', message='', sourceIds=['page-2'])


@pytest.mark.parametrize('format_', ['mcq', 'flashcard', 'calculation'])
def test_provider_evidence_ids_bind_original_source_and_verbatim_quote(format_, monkeypatch):
    import copy
    import json
    from pydantic import ValidationError
    from test_app import FakeAI, NOTES
    from schemas import quiz_evidence, validate_quiz
    sources = [{'id': 'long-chunk-a', 'originalSourceId': 'original-a', 'name': 'Lecture.pdf',
                'kind': 'pdf', 'locator': 'Page 1', 'page': 1, 'text': NOTES},
               {'id': 'long-chunk-b', 'originalSourceId': 'original-b', 'name': 'Lecture.pdf',
                'kind': 'pdf', 'locator': 'Page 2', 'page': 2, 'text': 'A gradient points uphill.\nSubtract it. ' + NOTES}]
    evidence = next(e for e in quiz_evidence(sources) if e['sourceId'] == 'long-chunk-b' and e['text'] == sources[1]['text'])
    raw = FakeAI().generate({'format': format_, 'count': 4}, sources)
    for q in raw['questions']:
        for name in ('id', 'sourceId', 'quote'):
            q.pop(name)
        q['evidenceId'] = evidence['id']
    captured = {}; ai = AI()
    def structured(system, content, schema):
        captured.update(schema=schema, input=json.loads(content[0]['text']))
        return schema.model_validate(raw).model_dump()
    monkeypatch.setattr(ai, 'structured', structured)
    params = {'format': format_, 'count': 4, 'prompt': 'Gradient descent', 'difficulty': 'beginner'}
    generated = ai.generate(params, sources)
    validated = validate_quiz(generated, sources, format_, 4)
    assert [q['id'] for q in validated['questions']] == ['q0', 'q1', 'q2', 'q3']
    assert all(q['source']['id'] == 'original-b' and q['source']['quote'] == sources[1]['text']
               and q['source']['page'] == 2 for q in validated['questions'])
    supplied = [e for s in captured['input']['sources'] for e in s['evidenceQuotes']]
    assert supplied == quiz_evidence(sources)
    invalid = copy.deepcopy(raw); invalid['questions'][0]['evidenceId'] = 'invented'
    with pytest.raises(ValidationError):
        captured['schema'].model_validate(invalid)
    with pytest.raises(ValueError, match='selected evidence'):
        validate_quiz(invalid, sources, format_, 4)
    invalid = copy.deepcopy(raw); invalid['questions'][0]['sourceId'] = 'foreign'
    with pytest.raises(ValueError, match='selected evidence'):
        validate_quiz(invalid, sources, format_, 4)
    # A reference from an earlier request cannot pass the current source snapshot.
    with pytest.raises(ValueError, match='selected evidence'):
        validate_quiz(raw, sources[:1], format_, 4)
