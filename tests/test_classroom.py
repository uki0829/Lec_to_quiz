import copy
import json

import pytest
from fastapi.testclient import TestClient

from app import create_app
from ai import AI
from classroom import Classroom, cosine
from schemas import ClassroomReply
from test_study_agent import AgentAI
from test_rag import collection, add
from test_app import generate


class ClassroomAI(AgentAI):
    def __init__(self):
        super().__init__()
        self.teaching, self.embedding_inputs = [], []
        self.bad_citation = False

    def embed(self, texts):
        self.embedding_inputs.extend(texts)
        return super().embed(texts)

    def teach_classroom(self, prompt, teacher, style, sources, earlier, history):
        self.teaching.append(copy.deepcopy({'teacher': teacher, 'style': style, 'sources': sources,
                                            'earlier': earlier, 'history': history}))
        return {'text': 'A distinct explanation by '+teacher['name'], 'takeaway': 'Apply the concept step by step.',
                'sourceIds': ['invented-private-source'] if self.bad_citation else [s['id'] for s in sources[:1]]}


@pytest.fixture
def room(tmp_path, monkeypatch):
    monkeypatch.delenv('COHERE_API_KEY', raising=False)
    ai = ClassroomAI()
    app = create_app(tmp_path, ai=ai, run_jobs=False)
    with TestClient(app) as alice, TestClient(app) as bob, TestClient(app) as outsider:
        for client, name in ((alice,'Alice'),(bob,'Bob'),(outsider,'Outsider')):
            client.post('/api/auth/register', json={'name':name,'email':name+'@example.test','password':'StudyDemo!123'})
        a = alice.get('/api/auth/me').json()['user']['id']
        b = bob.get('/api/auth/me').json()['user']['id']
        gid = alice.post('/api/groups', json={'name':'Pixel class'}).json()['id']
        code = alice.get('/api/groups/'+gid).json()['invite_code']
        bob.post('/api/groups/join', json={'code':code})
        yield app, ai, alice, bob, outsider, gid, a, b


def ask(client, gid, ids, action='explain', key='classroom-request', text='Explain gradient descent'):
    return client.post(f'/api/groups/{gid}/classroom', json={'message':text,'agentIds':ids,
        'action':action,'count':4,'requestId':key})


def finish(app, client, response):
    assert response.status_code == 202, response.text
    job_id = response.json()['jobId']
    app.state.engine.run(job_id)
    job = client.get('/api/jobs/'+job_id).json()
    assert job['status'] == 'completed', job
    return job['result']


def shared_fixture(app, alice, gid):
    cid = collection(alice)
    mid = add(alice, app.state.engine, cid)
    quiz = generate(alice, app.state.engine, mid)
    sid = alice.post(f'/api/groups/{gid}/share', json={'quizId':quiz['id']}).json()['shareId']
    return cid, mid, quiz, sid


def test_profile_is_per_account_customizable_and_persistent(room):
    app, ai, alice, bob, outside, gid, a, b = room
    before = bob.get('/api/agents/me').json()['agent']
    mine = alice.get('/api/agents/me').json()
    assert mine['agent']['id'] == a and len(mine['avatars']) == 4
    result = alice.patch('/api/agents/me', json={'name':'Professor Pip','avatar':'pig','style':'coach'})
    assert result.status_code == 200 and result.json()['agent']['name'] == 'Professor Pip'
    assert bob.get('/api/agents/me').json()['agent'] == before
    assert alice.patch('/api/agents/me', json={'name':'Pip','avatar':'../../secret','style':'coach'}).status_code == 400
    assert alice.patch('/api/agents/me', json={'name':'Pip','avatar':'pig','style':'delete-files'}).status_code == 400
    reopened = Classroom(app.state.store, app.state.engine, app.state.engine.classroom.accounts, app.state.engine.classroom.groups)
    assert reopened.profile({'id':a,'name':'Alice'})['avatar'] == 'pig'
    agents = bob.get(f'/api/groups/{gid}/classroom').json()['agents']
    assert {x['id'] for x in agents} == {a,b}
    assert all('email' not in x for x in agents)


def test_two_teachers_collaborate_without_private_materials_or_progress(room):
    app, ai, alice, bob, outside, gid, a, b = room
    _, _, _, sid = shared_fixture(app, alice, gid)
    private = collection(bob, 'PRIVATE TITLE MUST NOT LEAK')
    add(bob, app.state.engine, private, 'PRIVATE LECTURE MUST NOT LEAK. Gradient descent is studied here.')
    app.state.store.execute('INSERT INTO shared_progress VALUES(?,?,?)',
        (sid,b,json.dumps({'answers':{'q0':{'note':'PRIVATE PROGRESS MUST NOT LEAK'}}})))
    ai.embedding_inputs.clear()
    result = finish(app, alice, ask(alice, gid, [a,b]))
    assert result['shareId'] is None and len(ai.teaching) == 2
    assert ai.teaching[1]['earlier'][0]['agent']['id'] == a
    sent = json.dumps(ai.teaching)+json.dumps(ai.embedding_inputs)
    assert 'PRIVATE TITLE MUST NOT LEAK' not in sent
    assert 'PRIVATE LECTURE MUST NOT LEAK' not in sent
    assert 'PRIVATE PROGRESS MUST NOT LEAK' not in sent
    assert all(s['shareId']==sid for call in ai.teaching for s in call['sources'])
    turn = bob.get(f'/api/groups/{gid}/classroom').json()['turns'][-1]
    assert turn['status'] == 'completed' and len(turn['replies']) == 2
    assert turn['jobId'] is None
    assert turn['replies'][0]['sources'][0]['shareId'] == sid


@pytest.mark.parametrize('format_', ['mcq','flashcard','calculation','cheatsheet'])
def test_empty_classroom_creates_real_group_artifact_without_private_uploads(room, format_):
    app, ai, alice, bob, outside, gid, a, b = room
    result = finish(app, alice, ask(alice, gid, [b,a], action=format_))
    shared = bob.get('/api/shared-sets/'+result['shareId']).json()
    assert shared['format'] == format_ and shared['grounding'] == 'general'
    assert shared['teachers'][0] == ai.teaching[0]['teacher']['name']
    assert not app.state.store.all('SELECT * FROM quizzes')
    assert not app.state.store.collection_materials('')
    assert app.state.store.all('SELECT * FROM classroom_vectors') == []
    assert outside.get('/api/shared-sets/'+result['shareId']).status_code == 404
    assert alice.delete(f'/api/groups/{gid}/sets/'+result['shareId']).status_code == 200
    assert alice.get(f'/api/groups/{gid}/classroom').json()['turns'][-1]['shareId'] is None


def test_grounded_group_generation_has_shared_evidence_without_private_source_ids(room):
    app, ai, alice, bob, outside, gid, a, b = room
    shared_fixture(app, alice, gid)
    count = len(app.state.store.all('SELECT * FROM quizzes'))
    result = finish(app, alice, ask(alice,gid,[a,b],action='mcq'))
    shared = bob.get('/api/shared-sets/'+result['shareId']).json()
    assert shared['grounding']=='shared' and len(shared['questions'])==4
    assert all('id' not in q['source'] and 'url' not in q['source'] for q in shared['questions'])
    assert all(q['source']['quote'] for q in shared['questions'])
    assert len(app.state.store.all('SELECT * FROM quizzes'))==count


def test_idempotency_job_permissions_and_cancel(room):
    app, ai, alice, bob, outside, gid, a, b = room
    response = ask(alice,gid,[a,b])
    assert ask(alice,gid,[a,b]).json()==response.json()
    assert ask(bob,gid,[b],key='second-request').status_code==409
    job_id=response.json()['jobId']
    assert bob.get('/api/jobs/'+job_id).status_code==404
    assert bob.post('/api/jobs/'+job_id+'/cancel').status_code==404
    assert outside.get(f'/api/groups/{gid}/classroom').status_code==404
    assert ask(outside,gid,[a]).status_code==404
    alice.post('/api/jobs/'+job_id+'/cancel')
    app.state.engine.run(job_id)
    assert alice.get('/api/jobs/'+job_id).json()['status']=='cancelled'
    assert ai.teaching==[]
    assert alice.post('/api/jobs/'+job_id+'/retry').status_code==400


def test_member_teacher_and_shared_source_changes_are_rechecked(room):
    app, ai, alice, bob, outside, gid, a, b = room
    _,_,_,sid=shared_fixture(app,alice,gid)
    response=ask(alice,gid,[a,b])
    assert alice.delete(f'/api/groups/{gid}/sets/{sid}').status_code==409
    assert bob.post(f'/api/groups/{gid}/leave').status_code==200
    job_id=response.json()['jobId'];app.state.engine.run(job_id)
    assert alice.get('/api/jobs/'+job_id).json()['status']=='failed'
    assert ai.teaching==[]
    assert ask(alice,gid,[b],key='departed-teacher').status_code==400


def test_cache_reuse_is_group_scoped_and_removed_content_not_retrieved(room):
    app, ai, alice, bob, outside, gid, a, b = room
    _,_,_,sid=shared_fixture(app,alice,gid)
    finish(app,alice,ask(alice,gid,[a]))
    vectors=app.state.store.all('SELECT * FROM classroom_vectors WHERE group_id=?',(gid,))
    assert vectors
    ai.embedding_inputs.clear()
    finish(app,alice,ask(alice,gid,[a],key='cached-request'))
    assert ai.embedding_inputs==['Explain gradient descent']
    alice.delete(f'/api/groups/{gid}/sets/{sid}')
    assert app.state.store.all('SELECT * FROM classroom_vectors WHERE group_id=?',(gid,))==[]
    finish(app,alice,ask(alice,gid,[a],key='after-delete'))
    assert ai.teaching[-1]['sources']==[]
    other=alice.post('/api/groups',json={'name':'Another class'}).json()['id']
    finish(app,alice,ask(alice,other,[a]))
    assert ai.teaching[-1]['sources']==[]


def test_bad_references_and_provider_failures_preserve_existing_sets(room):
    app, ai, alice, bob, outside, gid, a, b = room
    shared_fixture(app,alice,gid)
    before=alice.get('/api/groups/'+gid).json()['sets']
    ai.bad_citation=True
    response=ask(alice,gid,[a],action='mcq')
    app.state.engine.run(response.json()['jobId'])
    assert alice.get('/api/jobs/'+response.json()['jobId']).json()['status']=='failed'
    assert alice.get('/api/groups/'+gid).json()['sets']==before


def test_tutor_prompt_is_structured_and_marks_private_boundary(monkeypatch):
    captured={}
    monkeypatch.setattr(AI,'structured',lambda self,system,content,schema:captured.update(system=system,content=content,schema=schema) or {})
    AI().teach_classroom('Explain',{'name':'Pip'},'Guide with hints',[],[],[])
    assert captured['schema'] is ClassroomReply
    assert 'private' in captured['system'] and 'untrusted' in captured['system']
    assert cosine([1,0],[1,0])==1 and cosine([1,0],[0,1])==0
