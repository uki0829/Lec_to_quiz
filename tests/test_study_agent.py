import copy
import json

import pytest
from fastapi.testclient import TestClient

from app import create_app
from ai import AI
from study_agent import StudyAgent
from schemas import AgentPlan
from test_app import FakeAI, NOTES, complete
from test_rag import collection, add
from test_accounts_groups import social


class AgentAI(FakeAI):
    embedding_model = 'fixture-embedding'

    def __init__(self):
        super().__init__()
        self.plans = []
        self.clarify = False
        self.fail_plan = False
        self.bad_plan = False
        self.selected = []

    def plan_study(self, message, history, materials, previous):
        self.plans.append({'message': message, 'history': copy.deepcopy(history),
                           'materials': materials, 'previous': previous})
        if self.fail_plan:
            raise ValueError('Planning provider unavailable')
        return {'action': 'clarify' if self.clarify else 'generate',
                'message': 'Which topic would you like?' if self.clarify else 'Creating practice from your lectures.',
                'prompt': 'New practice on learning rate' if previous else 'Practice gradient descent',
                'format': 'flashcard' if 'flashcard' in message else 'mcq',
                'count': 13 if self.bad_plan else 4,
                'difficulty': 'advanced' if 'harder' in message else 'beginner',
                'buildOnPrevious': bool(previous and 'harder' in message)}

    def select(self, prompt, sources):
        self.selected.append(copy.deepcopy(sources))
        return super().select(prompt, sources)

    def generate(self, params, sources, validation_feedback=''):
        result = super().generate(params, sources, validation_feedback)
        if params.get('followupContext'):
            for q in result['questions']:
                q['prompt'] = 'Different practice: ' + q['prompt']
        return result


@pytest.fixture
def agent(tmp_path):
    ai = AgentAI()
    app = create_app(tmp_path, ai=ai, run_jobs=False, auth_required=False)
    with TestClient(app) as client:
        cid = collection(client)
        mid = add(client, app.state.engine, cid)
        yield client, app, ai, cid, mid


def send(client, cid, text='Quiz me', key='request-0001'):
    return client.post(f'/api/collections/{cid}/agent/messages', json={'message': text, 'requestId': key})


def finish(client, app, cid, response):
    assert response.status_code == 200, response.text
    assistant = response.json()['messages'][-1]
    app.state.engine.run(assistant['jobId'])
    return client.get(f'/api/collections/{cid}/agent').json()['messages'][-1]


def test_agent_uses_rag_and_preserves_followup_settings(agent):
    client, app, ai, cid, mid = agent
    first = finish(client, app, cid, send(client, cid))
    assert first['state'] == 'ready' and first['set']['count'] == 4
    assert first['set']['sources'][0]['id'] == app.state.store.sources(mid)[0]['id']
    assert ai.selected and {s['materialId'] for s in ai.selected[-1]} == {mid}
    assert client.get('/api/sources/'+first['set']['sources'][0]['id']).status_code == 200
    q = app.state.store.quiz(first['quizId'])
    assert q['request']['submitted']['prompt'] == 'Quiz me'
    assert q['request']['submitted']['origin'] == 'agent'
    assert q['request']['resolved']['prompt'] == 'Practice gradient descent'
    assert q['request']['resolved']['reranking']['inputCount'] > 0
    again = finish(client, app, cid, send(client, cid, 'Make these harder as flashcards', 'request-0002'))
    assert again['set']['format'] == 'flashcard'
    q2 = app.state.store.quiz(again['quizId'])
    assert q2['request']['parent_quiz_id'] == q['id']
    assert q2['request']['resolved']['difficulty'] == 'advanced'
    assert ai.plans[-1]['previous']['format'] == 'mcq'
    assert ai.plans[-1]['history'][0]['role'] == 'user'


def test_agent_resolves_unspecified_settings_on_server(agent, monkeypatch):
    client, app, ai, cid, _ = agent
    plan = ai.plan_study
    def unspecified(*args):
        result = plan(*args)
        result.update(count=None, difficulty=None, format=None)
        return result
    monkeypatch.setattr(ai, 'plan_study', unspecified)
    initial = finish(client, app, cid, send(client, cid))
    quiz = app.state.store.quiz(initial['quizId'])
    assert quiz['format'] == 'mcq' and len(quiz['questions']) == 6
    assert quiz['request']['resolved']['difficulty'] == 'intermediate'
    def explicit(*args):
        result = plan(*args)
        result.update(count=4, difficulty='advanced', format='flashcard', buildOnPrevious=True)
        return result
    monkeypatch.setattr(ai, 'plan_study', explicit)
    changed = finish(client, app, cid, send(client, cid, 'Four advanced flashcards', 'explicit-settings'))
    monkeypatch.setattr(ai, 'plan_study', unspecified)
    response = send(client, cid, 'More like these, harder', 'inherited-settings')
    params = app.state.store.job(response.json()['messages'][-1]['jobId'])['params']
    assert params['format'] == 'flashcard' and params['count'] == 4
    assert params['difficulty'] == 'advanced'
    assert params['parentQuizId'] == changed['quizId']


def test_agent_idempotency_isolation_and_conversation_persistence(agent):
    client, app, ai, cid, mid = agent
    other = collection(client, 'Psychology')
    add(client, app.state.engine, other, 'Psychology study concepts. '+NOTES)
    first = send(client, cid)
    duplicate = send(client, cid)
    assert first.json()['messageId'] == duplicate.json()['messageId']
    assert len(ai.plans) == 1
    assert send(client, cid, key='different-key').status_code == 409
    ready = finish(client, app, cid, first)
    assert client.get(f'/api/collections/{other}/agent').json()['messages'] == []
    finish(client, app, other, send(client, other, key='request-0003'))
    assert {s['materialId'] for s in ai.selected[-1]} != {mid}
    assert all(m['name'] != 'Pasted lecture notes from another folder' for m in ai.plans[-1]['materials'])
    reopened = StudyAgent(app.state.store, app.state.engine)
    assert reopened.history(cid)[-1]['quizId'] == ready['quizId']


def test_agent_empty_sources_clarification_and_planning_failure(agent):
    client, app, ai, cid, _ = agent
    empty = collection(client, 'Empty')
    response = send(client, empty)
    assert response.json()['messages'][-1]['state'] == 'clarify'
    assert not ai.plans
    ai.clarify = True
    response = send(client, cid)
    assert response.json()['messages'][-1]['state'] == 'clarify'
    assert not app.state.store.one("SELECT id FROM jobs WHERE kind='quiz'")
    ai.clarify = False; ai.fail_plan = True
    response = send(client, cid, key='request-0004')
    assert response.json()['messages'][-1]['state'] == 'failed'
    assert 'unavailable' in response.json()['messages'][-1]['text']
    ai.fail_plan = False; ai.bad_plan = True
    response = send(client, cid, key='request-0005')
    assert response.json()['messages'][-1]['state'] == 'failed'
    assert not app.state.store.one("SELECT id FROM jobs WHERE kind='quiz'")
    assert send(client, cid, '   ', key='request-0006').status_code == 400


def test_agent_generation_failure_cancel_retry_and_deleted_set(agent):
    client, app, ai, cid, _ = agent
    ai.fail_generate = True
    response = send(client, cid)
    failed = finish(client, app, cid, response)
    assert failed['state'] == 'failed'
    ai.fail_generate = False
    retry = client.post(f"/api/collections/{cid}/agent/messages/{failed['id']}/retry")
    ready = finish(client, app, cid, retry)
    assert ready['state'] == 'ready'
    assert app.state.store.quiz(ready['quizId'])['request']['submitted']['prompt'] == 'Quiz me'
    response = send(client, cid, key='request-cancel')
    pending = response.json()['messages'][-1]
    client.post('/api/jobs/'+pending['jobId']+'/cancel')
    cancelled = finish(client, app, cid, response)
    assert cancelled['state'] == 'failed' and 'cancelled' in cancelled['text']
    client.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': [ready['quizId']]})
    messages = client.get(f'/api/collections/{cid}/agent').json()['messages']
    removed = next(m for m in messages if m['id'] == ready['id'])
    assert removed['state'] == 'removed' and not removed.get('set')


def test_agent_planning_recovery_and_folder_cleanup(agent):
    client, app, ai, cid, _ = agent
    ai.clarify = True
    response = send(client, cid)
    ident = response.json()['messageId']
    app.state.store.execute("UPDATE agent_messages SET state='planning' WHERE id=?", (ident,))
    StudyAgent(app.state.store, app.state.engine).recover()
    assert client.get(f'/api/collections/{cid}/agent').json()['messages'][-1]['state'] == 'failed'
    assert client.delete('/api/collections/'+cid).status_code == 200
    assert not app.state.store.all('SELECT * FROM agent_threads WHERE collection_id=?', (cid,))
    assert not app.state.store.all('SELECT * FROM agent_messages')


def test_agent_requires_account_and_collection_ownership(social):
    app, alice, bob = social
    cid = collection(alice)
    assert bob.get(f'/api/collections/{cid}/agent').status_code == 404
    assert send(bob, cid).status_code == 404
    alice.post('/api/auth/logout')
    assert alice.get(f'/api/collections/{cid}/agent').status_code == 401


def test_agent_planner_uses_structured_contract(monkeypatch):
    captured = {}
    def structured(system, content, schema):
        captured.update(system=system, content=content, schema=schema)
        return {}
    monkeypatch.setattr(AI, 'structured', lambda self, *args: structured(*args))
    AI().plan_study('Quiz me', [], [{'name': 'Psychology lecture'}], None)
    assert captured['schema'] is AgentPlan
    assert 'retrieves actual lecture evidence using RAG' in captured['system']
    assert 'untrusted data' in captured['system']
    assert 'Psychology lecture' in captured['content'][0]['text']
