import copy
import json

import pytest
from fastapi.testclient import TestClient

from ai import AI
from app import create_app
from mistakes import missed_questions
from storage import Store
from test_app import FakeAI, NOTES, complete
from test_rag import collection, add
from test_accounts_groups import social


class PracticeAI(FakeAI):
    def __init__(self):
        super().__init__()
        self.calls=[]
        self.queries=[]

    def review_mistake_practice(self, questions, selected):
        if getattr(self, 'bad_focus', False):
            return {'status':'repair', 'message':'An unselected topic was included.'}
        return {'status':'ready', 'message':''}

    def select(self, prompt, sources):
        self.queries.append(prompt)
        return super().select(prompt, sources)

    def generate(self, params, sources, validation_feedback=''):
        self.calls.append((copy.deepcopy(params), copy.deepcopy(sources)))
        result=super().generate(params,sources,validation_feedback)
        if params.get('mistakePractice'):
            for i,q in enumerate(result['questions']):
                q['prompt']='How should the learning-rate-scaled gradient affect the next parameter value? Practice case '+str(i)
        return result


@pytest.fixture
def practice(tmp_path):
    ai=PracticeAI();app=create_app(tmp_path,ai=ai,run_jobs=False,auth_required=False)
    with TestClient(app) as client:
        cid=collection(client)
        mid=add(client,app.state.engine,cid)
        _,job=complete(client,app.state.engine,client.post('/api/quizzes',json={
            'collectionId':cid,'prompt':'Gradient descent','format':'mcq','count':4,'difficulty':'beginner'}))
        quiz=app.state.store.quiz(job['result']['quizId'])
        yield client,app,ai,cid,mid,quiz


def save(client,quiz,answers):
    response=client.put('/api/quizzes/'+quiz['id']+'/progress',json={'index':0,'answers':answers,'review':True})
    assert response.status_code==200,response.text


def request(client,quiz,ids=None,key='mistake-key-0001'):
    return client.post('/api/quizzes/'+quiz['id']+'/mistakes',json={
        'questionIds':ids or [quiz['questions'][0]['id']], 'count':4,'requestId':key})


def test_regrade_latest_attempts_without_trusting_client_flags():
    q={'id':'one','type':'mcq','options':['A','B'],'correctIndex':0,'prompt':'Question','source':{}}
    parent={'mode':'generated','format':'mcq','questions':[q],'progress':{'answers':{'one':{'submitted':True,'selected':1,'correct':True}}}}
    assert missed_questions(parent)[0]['studentAnswer']=='B'
    parent['progress']['answers']['one'].update(selected=0,correct=False)
    assert not missed_questions(parent)
    parent['progress']['answers']['one'].update(selected=True)
    assert not missed_questions(parent)
    parent['progress']['answers']['one'].update(skipped=True)
    assert missed_questions(parent)[0]['status']=='skipped'
    parent.update(format='calculation');q.update(type='calculation',numericAnswer=2.4,tolerance=.001)
    for value in ['2.4e0','2.401']:
        parent['progress']['answers']['one']={'submitted':True,'value':value,'correct':False}
        assert not missed_questions(parent)
    parent['progress']['answers']['one']['value']='3.6'
    assert len(missed_questions(parent))==1
    for value in ['abc','Infinity','NaN','0x10','', '1e9999']:
        parent['progress']['answers']['one']['value']=value
        assert not missed_questions(parent)
    parent['progress']['answers']['one']={'submitted':True,'value':'2.4','gradedValue':'3.6','correct':False}
    assert missed_questions(parent)[0]['studentAnswer']=='3.6'
    parent.update(format='flashcard');assert not missed_questions(parent)
    parent.update(format='calculation',mode='shared');assert not missed_questions(parent)


def test_source_backed_targeted_generation_and_saved_parent_progress(practice):
    client,app,ai,cid,mid,quiz=practice
    ids=[q['id'] for q in quiz['questions']]
    attempts={ids[0]:{'submitted':True,'selected':1,'correct':True},
              ids[1]:{'submitted':True,'skipped':True,'selected':None},
              ids[2]:{'submitted':True,'selected':0,'correct':False}}
    save(client,quiz,attempts)
    add(client,app.state.engine,cid,'An unrelated lecture on memory and perception.')
    preview=client.get('/api/quizzes/'+quiz['id']+'/mistakes').json()
    assert [q['questionId'] for q in preview['questions']]==ids[:2]
    selection_calls = len(ai.queries)
    _,job=complete(client,app.state.engine,request(client,quiz))
    new=app.state.store.quiz(job['result']['quizId'])
    assert new['id']!=quiz['id'] and len(new['questions'])==4
    params,sources=ai.calls[-1]
    assert params['materialSnapshot']==[mid]
    assert params['difficulty']=='beginner' and params['format']=='mcq'
    assert params['mistakePractice']['questionIds']==ids[:1]
    assert params['mistakePractice']['questions'][0]['studentAnswer']=='3.6'
    assert params['followupContext']['request']==params['prompt']
    assert 'studentAnswer' not in client.get('/api/jobs/'+job['id']).json()['mistakePractice']['questions'][0]
    assert params['retrievalQuery']==quiz['questions'][0]['prompt'][:500]
    assert len(ai.queries) == selection_calls  # Saved evidence avoids another model selection.
    assert {s['materialId'] for s in sources}=={mid}
    assert new['request']['parent_quiz_id']==quiz['id']
    assert new['request']['resolved']['focusReview']['status']=='ready'
    assert new['request']['resolved']['mistakePractice']['questionIds']==ids[:1]
    assert new['request']['resolved']['retrievalMode'] == 'selected_mistake_evidence'
    assert new['request']['resolved']['reranking']['status'] == 'reused'
    timings = new['request']['resolved']['timings']
    assert [t['step'] for t in timings] == ['retrieval', 'generation', 'focus_review']
    assert all(t['seconds'] >= 0 for t in timings)
    assert app.state.store.quiz(quiz['id'])['progress']['answers']==attempts
    assert all(client.get('/api/sources/'+q['source']['id']).status_code==200 for q in new['questions'])


def test_saved_mistake_evidence_obeys_scope_and_readiness(practice):
    client, app, ai, cid, mid, quiz = practice
    retriever = app.state.engine.retriever
    q = quiz['questions'][0]
    selected = [{'sourceId': q['source']['id'], 'sourceQuote': q['source']['quote']}]
    assert retriever.mistake_sources(cid, [mid], selected)
    assert not retriever.mistake_sources('another-collection', [mid], selected)
    assert not retriever.mistake_sources(cid, ['another-material'], selected)
    assert not retriever.mistake_sources(cid, [mid], [{'sourceId': q['source']['id'], 'sourceQuote': 'not in the lecture'}])
    assert not retriever.mistake_sources(cid, [mid], [{'sourceId': q['source']['id']}])
    original_model = retriever.model
    retriever.model = 'changed-embedding-model'
    assert not retriever.mistake_sources(cid, [mid], selected)
    retriever.model = original_model
    app.state.store.execute('UPDATE chunks SET indexed=0 WHERE material_id=?', (mid,))
    assert not retriever.mistake_sources(cid, [mid], selected)


def test_mistake_evidence_unavailable_falls_back_to_search(practice, monkeypatch):
    client, app, ai, cid, mid, quiz = practice
    save(client, quiz, {quiz['questions'][0]['id']: {'submitted': True, 'selected': 1}})
    monkeypatch.setattr(app.state.engine.retriever, 'mistake_sources', lambda *args: [])
    _, job = complete(client, app.state.engine, request(client, quiz))
    child = app.state.store.quiz(job['result']['quizId'])
    assert child['request']['resolved']['retrievalMode'] == 'semantic_search'
    assert ai.queries[-1] == quiz['questions'][0]['prompt'][:500]
    assert child['request']['resolved']['focusReview']['status'] == 'ready'


def test_idempotency_and_refresh_persistence(practice):
    client,app,ai,cid,mid,quiz=practice
    save(client,quiz,{quiz['questions'][0]['id']:{'submitted':True,'selected':1}})
    first=request(client,quiz);again=request(client,quiz)
    assert first.status_code==202 and first.json()==again.json()
    assert request(client,quiz,key='another-action-key').status_code==409
    _,job=complete(client,app.state.engine,first)
    assert request(client,quiz).json()['jobId']==job['id']
    reopened=Store(app.state.store.root)
    assert reopened.quiz(job['result']['quizId'])['request']['parent_quiz_id']==quiz['id']
    assert len(missed_questions(reopened.quiz(quiz['id'])))==1


def test_invalid_correct_unanswered_and_foreign_selections(practice):
    client,app,_,_,_,quiz=practice
    assert client.get('/api/quizzes/'+quiz['id']+'/mistakes').json()['questions']==[]
    assert request(client,quiz).status_code==400
    save(client,quiz,{quiz['questions'][0]['id']:{'submitted':True,'selected':0,'correct':False}})
    assert request(client,quiz).status_code==400
    save(client,quiz,{quiz['questions'][0]['id']:{'submitted':True,'selected':1}})
    assert request(client,quiz,['foreign-question']).status_code==400
    assert client.post('/api/quizzes/'+quiz['id']+'/mistakes',json={'questionIds':[],'requestId':'request-123'}).status_code==422
    assert client.post('/api/quizzes/'+quiz['id']+'/mistakes',json={'questionIds':[quiz['questions'][0]['id']],'requestId':'request-123','count':13}).status_code==422
    body=copy.deepcopy(quiz);body.update(format='flashcard')
    other=app.state.store.add_quiz(quiz['materialId'],body)
    assert client.get('/api/quizzes/'+other['id']+'/mistakes').status_code==400


def test_missing_index_and_source_preserve_original(practice):
    client,app,_,_,mid,quiz=practice
    save(client,quiz,{quiz['questions'][0]['id']:{'submitted':True,'selected':1}})
    app.state.store.execute('UPDATE chunks SET indexed=0 WHERE material_id=?',(mid,))
    response=request(client,quiz)
    assert response.status_code==400 and 'index' in response.json()['error']
    assert app.state.store.quiz(quiz['id'])


def test_failure_retry_cancel_and_parent_deletion(practice):
    client,app,ai,cid,_,quiz=practice
    save(client,quiz,{quiz['questions'][0]['id']:{'submitted':True,'selected':1}})
    ai.fail_generate=True
    response=request(client,quiz);job_id=response.json()['jobId'];app.state.engine.run(job_id)
    assert app.state.store.job(job_id)['status']=='failed'
    assert missed_questions(app.state.store.quiz(quiz['id']))
    ai.fail_generate=False
    retry=client.post('/api/jobs/'+job_id+'/retry')
    _,job=complete(client,app.state.engine,retry)
    child=job['result']['quizId']
    assert request(client,quiz).json()['jobId']==job['id']
    response=request(client,quiz,key='cancel-practice-key')
    client.post('/api/jobs/'+response.json()['jobId']+'/cancel')
    app.state.engine.run(response.json()['jobId'])
    assert app.state.store.job(response.json()['jobId'])['status']=='cancelled'
    result=client.post(f'/api/collections/{cid}/quizzes/remove',json={'quizIds':[quiz['id']]})
    assert result.status_code==200,result.text
    child=app.state.store.quiz(child)
    assert child and child['request']['parent_quiz_id'] is None
    assert 'mistakePractice' not in child['request']['resolved']
    assert child['request']['submitted']['prompt']=='Focused follow-up practice.'
    assert child['request']['resolved']['prompt']=='Focused follow-up practice.'


def test_private_owner_boundaries(social):
    app,alice,bob=social
    cid=collection(alice);add(alice,app.state.engine,cid)
    _,job=complete(alice,app.state.engine,alice.post('/api/quizzes',json={'collectionId':cid,'prompt':'gradient descent','count':4}))
    quiz=app.state.store.quiz(job['result']['quizId'])
    assert bob.get('/api/quizzes/'+quiz['id']+'/mistakes').status_code==404
    assert request(bob,quiz).status_code==404
    alice.post('/api/auth/logout')
    assert request(alice,quiz).status_code==401


def test_generation_prompt_keeps_attempts_separate_from_evidence(monkeypatch):
    captured={}
    def structured(self,system,content,schema):
        captured.update(system=system,content=content);return {}
    monkeypatch.setattr(AI,'structured',structured)
    AI().generate({'prompt':'Practice mistakes','format':'mcq','count':4,'difficulty':'beginner',
                   'mistakePractice':{'questions':[{'prompt':'Test concept','studentAnswer':'fallible answer',
                                                    'sourceQuote':'local-evidence-lookup-only'}]}},
                  [{'id':'source','text':NOTES}])
    assert 'not source facts' in captured['system']
    assert 'ONLY its selected incorrect/skipped questions' in captured['system']
    assert 'mistakePractice' in captured['content'][0]['text']
    assert 'local-evidence-lookup-only' not in captured['content'][0]['text']


def test_near_repeat_guard_allows_new_numerical_givens():
    from mistakes import near_repeat
    assert near_repeat('Why does gradient descent step in the negative gradient direction?',
                       ['Why does gradient descent move in the negative gradient direction?'])
    assert not near_repeat('For w=5 and eta=0.2, calculate the update.',
                           ['For w=3 and eta=0.1, calculate the update.'])
    assert not near_repeat('A derivative is negative at the current point. Which move lowers the loss?',
                           ['Why does gradient descent move in the negative gradient direction?'])


def test_focus_review_retries_and_preserves_parent_on_failure(practice):
    client,app,ai,_,_,quiz=practice
    save(client,quiz,{quiz['questions'][0]['id']:{'submitted':True,'selected':1}})
    ai.bad_focus=True
    response=request(client,quiz);job_id=response.json()['jobId']
    before=ai.generate_calls
    app.state.engine.run(job_id)
    job=app.state.store.job(job_id)
    assert job['status']=='failed' and 'unselected topic' in job['error']
    assert ai.generate_calls==before+3
    assert missed_questions(app.state.store.quiz(quiz['id']))


def test_review_uses_a_structured_focus_contract(monkeypatch):
    from schemas import MistakeReview
    captured={}
    def structured(self,system,content,schema):
        captured.update(system=system,content=content,schema=schema);return {'status':'ready','message':''}
    monkeypatch.setattr(AI,'structured',structured)
    AI().review_mistake_practice([{'prompt':'A new scenario','answer':'A'}],[{'prompt':'Selected concept'}])
    assert captured['schema'] is MistakeReview
    assert 'not instructions' in captured['system'] and 'selected missed questions' in captured['system']
    assert 'Selected concept' in captured['content'][0]['text']
