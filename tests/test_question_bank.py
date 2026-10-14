import pytest
from fastapi.testclient import TestClient

from app import create_app
from storage import Store
from test_app import FakeAI
from test_rag import collection, add, quiz_request


class HintAI(FakeAI):
    def __init__(self):
        super().__init__(); self.hint_calls = 0; self.bad_hint = False; self.fail_hint = False
    def hint(self, question, source, feedback=''):
        self.hint_calls += 1
        assert source['text'] and question['source']['id'] == source['id']
        if self.fail_hint:
            raise ValueError('Fixture hint provider failed')
        return {'hint': question['answer'] if self.bad_hint else 'Recall which operation subtracts the learning step from the current value.'}


@pytest.fixture
def bank(tmp_path):
    ai=HintAI();app=create_app(tmp_path,ai=ai,run_jobs=False)
    with TestClient(app) as client:
        cid=collection(client);mid=add(client,app.state.engine,cid)
        q=quiz_request(client,app.state.engine,cid,format='flashcard',count=4)
        yield client,app.state.store,app.state.engine,ai,cid,mid,q


def question_url(q, action, qid='q0'):
    return f"/api/quizzes/{q['id']}/questions/{qid}/{action}"


def test_star_bank_persistence_isolation_and_unstar(bank):
    client,store,engine,ai,cid,mid,q=bank
    other=collection(client,'Another course');add(client,engine,other)
    q2=quiz_request(client,engine,cid,format='flashcard',count=4)
    for quiz in (q,q2):
        assert client.put(question_url(quiz,'star'),json={'starred':True}).status_code==200
        assert client.put(question_url(quiz,'star'),json={'starred':True}).status_code==200
    cards=client.get(f'/api/collections/{cid}/question-bank').json()['questions']
    assert len(cards)==2 and {x['originQuizId'] for x in cards}=={q['id'],q2['id']}
    assert all(x['originQuestionId']=='q0' and x['starred'] for x in cards)
    assert client.get(f'/api/collections/{other}/question-bank').json()['questions']==[]
    reopened=Store(store.root)
    assert reopened.quiz(q['id'])['questions'][0]['starred']
    assert client.put(question_url(q,'star'),json={'starred':False}).status_code==200
    assert len(client.get(f'/api/collections/{cid}/question-bank').json()['questions'])==1
    assert client.get(f"/api/quizzes/{q['id']}").json()['questions'][0]['starred'] is False


def test_hint_cached_without_changing_answer_or_progress(bank):
    client,store,engine,ai,cid,mid,q=bank
    progress={'index':0,'answers':{'q0':{'revealed':False,'submitted':True,'correct':True}}}
    client.put(f"/api/quizzes/{q['id']}/progress",json=progress)
    first=client.post(question_url(q,'hint'));assert first.status_code==200,first.text
    assert first.json()['cached'] is False
    assert client.post(question_url(q,'hint')).json()['cached'] is True
    assert ai.hint_calls==1
    reopened=Store(store.root).quiz(q['id'])
    assert reopened['questions'][0]['hint']==first.json()['hint']
    assert reopened['questions'][0]['answer']==q['questions'][0]['answer']
    assert reopened['progress']==progress


@pytest.mark.parametrize('failure',['answer_leak','provider'])
def test_hint_failures_do_not_replace_quiz(bank,failure):
    client,store,engine,ai,cid,mid,q=bank
    ai.bad_hint=failure=='answer_leak';ai.fail_hint=failure=='provider'
    result=client.post(question_url(q,'hint'))
    assert result.status_code==502
    assert not store.all('SELECT * FROM question_hints')
    assert client.get(f"/api/quizzes/{q['id']}").status_code==200
    assert ai.hint_calls==(2 if failure=='answer_leak' else 1)


@pytest.mark.parametrize('remove',['material','collection'])
def test_deletion_cleans_starred_questions_and_hints(bank,remove):
    client,store,engine,ai,cid,mid,q=bank
    client.put(question_url(q,'star'),json={'starred':True});client.post(question_url(q,'hint'))
    url=f'/api/materials/{mid}' if remove=='material' else f'/api/collections/{cid}'
    assert client.delete(url).status_code==200
    assert not store.all('SELECT * FROM starred_questions')
    assert not store.all('SELECT * FROM question_hints')


def test_missing_questions_and_other_formats_rejected(bank):
    client,store,engine,ai,cid,mid,q=bank
    assert client.put(question_url(q,'star','missing'),json={'starred':True}).status_code==404
    assert client.post(question_url(q,'hint','missing')).status_code==404
    mcq=quiz_request(client,engine,cid)
    assert client.post(question_url(mcq,'hint')).status_code==400
    assert client.put(question_url(mcq,'star'),json={'starred':True}).status_code==400
