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
