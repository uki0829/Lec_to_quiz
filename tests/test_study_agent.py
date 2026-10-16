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
        self.chats = []

    def chat_study(self, message, history, sources, teacher=None):
        self.chats.append({'message': message, 'history': copy.deepcopy(history),
                           'sources': copy.deepcopy(sources), 'teacher': teacher})
        if getattr(self, 'fail_chat', False):
            raise ValueError('Chat provider unavailable')
        return {'text': 'Study agenda\n• Review the main concept.\n• Work through an example.',
                'sourceIds': [sources[0]['id']] if sources else []}

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

    def generate_general(self, params, validation_feedback=''):
        self.general_calls = getattr(self, 'general_calls', 0) + 1
        if params['format'] == 'cheatsheet':
            return {'status': 'ready', 'message': '', 'title': 'General study guide', 'description': '',
                    'sections': [{'heading': 'Core ideas', 'points': ['An authored fixture explanation.'],
                                  'formulas': [], 'sourceId': '', 'quote': ''}]}
        raw = self.generate(params, [{'id': 'test-only', 'text': 'Authored fixture content'}], validation_feedback)
        for q in raw['questions']:
            q.update(sourceId='', quote='')
        return raw


@pytest.fixture
def agent(tmp_path):
    ai = AgentAI()
    app = create_app(tmp_path, ai=ai, run_jobs=False, auth_required=False)
    with TestClient(app) as client:
        cid = collection(client)
        mid = add(client, app.state.engine, cid)
        yield client, app, ai, cid, mid


def send(client, cid, text='/quiz Quiz me', key='request-0001'):
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
    assert q['request']['submitted']['prompt'] == '/quiz Quiz me'
    assert q['request']['submitted']['origin'] == 'agent'
    assert q['request']['resolved']['prompt'] == 'Practice gradient descent'
    assert q['request']['resolved']['reranking']['inputCount'] > 0
    again = finish(client, app, cid, send(client, cid, '/flashcards Make these harder', 'request-0002'))
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
    changed = finish(client, app, cid, send(client, cid, '/flashcards Four advanced cards', 'explicit-settings'))
    monkeypatch.setattr(ai, 'plan_study', unspecified)
    response = send(client, cid, '/flashcards More like these, harder', 'inherited-settings')
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
    assert finish(client, app, empty, response)['state'] == 'ready'
    assert ai.plans[-1]['materials'] == []
    ai.clarify = True
    response = send(client, cid)
    assert response.json()['messages'][-1]['state'] == 'clarify'
    assert not app.state.store.one("SELECT id FROM jobs WHERE kind='quiz' AND status IN ('queued','running')")
    ai.clarify = False; ai.fail_plan = True
    response = send(client, cid, key='request-0004')
    assert response.json()['messages'][-1]['state'] == 'failed'
    assert 'unavailable' in response.json()['messages'][-1]['text']
    ai.fail_plan = False; ai.bad_plan = True
    response = send(client, cid, key='request-0005')
    assert response.json()['messages'][-1]['state'] == 'failed'
    assert not app.state.store.one("SELECT id FROM jobs WHERE kind='quiz' AND status IN ('queued','running')")
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
    assert app.state.store.quiz(ready['quizId'])['request']['submitted']['prompt'] == '/quiz Quiz me'
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
    assert send(bob, cid, 'Make an agenda.', 'private-chat').status_code == 404
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
    assert 'Uploads are optional' in captured['system']
    assert 'untrusted data' in captured['system']
    assert 'Psychology lecture' in captured['content'][0]['text']


@pytest.mark.parametrize('message', ['Create a study agenda for my lecture.', 'hello',
                                   'Why does gradient descent work?', 'Create a quiz about memory.',
                                   'Explain what /quiz means without running it.'])
def test_normal_messages_reply_in_chat_without_generating(agent, message):
    client, app, ai, cid, mid = agent
    before = app.state.store.all('SELECT id FROM jobs')
    response = send(client, cid, message)
    reply = response.json()['messages'][-1]
    assert reply['state'] == 'ready' and reply['chat']
    assert reply['text'].startswith('Study agenda')
    assert reply['jobId'] is None and reply['quizId'] is None and 'set' not in reply
    assert reply['sources'][0]['id'] == app.state.store.sources(mid)[0]['id']
    assert app.state.store.all('SELECT id FROM jobs') == before
    assert not ai.plans
    assert {s['materialId'] for s in ai.chats[-1]['sources']} == {mid}
    duplicate = send(client, cid, message)
    assert duplicate.json()['messageId'] == response.json()['messageId']
    assert len(ai.chats) == 1
    assert StudyAgent(app.state.store, app.state.engine).history(cid)[-1]['chat']


def test_chat_history_empty_folder_and_source_validation(agent, monkeypatch):
    client, app, ai, cid, mid = agent
    empty = collection(client, 'Chat without uploads')
    response = send(client, empty, 'Make a study agenda.')
    reply = response.json()['messages'][-1]
    assert reply['grounding'] == 'general' and reply['sources'] == []
    response = send(client, empty, 'Make it shorter.', 'chat-followup')
    assert ai.chats[-1]['history'][0]['text'] == 'Make a study agenda.'
    assert not app.state.store.all("SELECT id FROM jobs WHERE kind='quiz'")
    monkeypatch.setattr(ai, 'chat_study', lambda *a: {'text': 'Bad reference', 'sourceIds': ['another-users-source']})
    response = send(client, cid, 'Explain my lecture.', 'bad-chat-reference')
    assert response.json()['messages'][-1]['state'] == 'failed'
    assert 'invalid lecture references' in response.json()['messages'][-1]['text']


@pytest.mark.parametrize('command,expected', [('/quiz','mcq'),('/flashcards','flashcard'),
    ('/calculation','calculation'),('/cheatsheet','cheatsheet')])
def test_slash_command_controls_format_even_if_planner_disagrees(agent, monkeypatch, command, expected):
    client, app, ai, cid, _ = agent
    plan = ai.plan_study
    def wrong_format(*args):
        value = plan(*args);value['format'] = 'mcq';return value
    monkeypatch.setattr(ai, 'plan_study', wrong_format)
    response = send(client, cid, command+' Create practice about the lecture.')
    reply = response.json()['messages'][-1]
    assert reply['state'] == 'pending'
    assert app.state.store.job(reply['jobId'])['params']['format'] == expected
    assert not ai.chats


def test_unknown_commands_do_not_trigger_generation(agent):
    client, app, ai, cid, _ = agent
    reply = send(client, cid, '/quizlet Create questions.').json()['messages'][-1]
    assert reply['state'] == 'clarify' and '/flashcards' in reply['text']
    assert not ai.plans and not ai.chats


def test_chat_prompt_answers_agendas_and_does_not_request_formats(monkeypatch):
    from schemas import AgentReply
    captured = {}
    monkeypatch.setattr(AI, 'structured', lambda self, system, content, schema: captured.update(system=system, content=content, schema=schema) or {})
    AI().chat_study('Make an agenda', [], [{'id':'chunk', 'text':NOTES}])
    assert captured['schema'] is AgentReply
    assert 'Normal text NEVER creates a saved study set' in captured['system']
    assert 'write that agenda now' in captured['system']
    assert 'Do not ask the user to choose a quiz format' in captured['system']
    assert 'chunk' in captured['content'][0]['text']


@pytest.mark.parametrize('format_', ['mcq', 'flashcard', 'calculation', 'cheatsheet'])
def test_agent_without_uploads_saves_general_practice_and_survives_restart(agent, monkeypatch, format_):
    from storage import Store
    client, app, ai, _, _ = agent
    cid = collection(client, 'No uploads')
    plan = ai.plan_study
    def choose(*args):
        result = plan(*args); result['format'] = format_; return result
    monkeypatch.setattr(ai, 'plan_study', choose)
    command = {'mcq':'quiz', 'flashcard':'flashcards', 'calculation':'calculation', 'cheatsheet':'cheatsheet'}[format_]
    message = finish(client, app, cid, send(client, cid, '/'+command+' Practice my topic', 'empty-' + format_))
    assert message['state'] == 'ready', message
    assert message['set']['grounding'] == 'general' and message['set']['sources'] == []
    quiz = client.get('/api/quizzes/' + message['quizId']).json()
    assert quiz['grounding'] == 'general' and quiz['collectionId'] == cid
    assert app.state.store.collection_materials(cid) == []
    assert quiz['request']['resolved']['fallbackReason'] == 'no_indexed_sources'
    assert quiz['request']['submitted']['origin'] == 'agent'
    for item in quiz.get('sections', []) + quiz['questions']:
        assert item['source']['kind'] == 'general'
        assert not item['source'].get('id') and item['source']['quote'] == ''
    assert not app.state.store.all('SELECT * FROM quiz_sources WHERE quiz_id=?', (quiz['id'],))
    restarted = Store(app.state.store.root)
    assert restarted.quiz(quiz['id'])['collectionId'] == cid
    assert client.get('/api/quizzes?collectionId=' + cid).json()['quizzes'][0]['id'] == quiz['id']
    if format_ == 'cheatsheet':
        response = client.post('/api/cheatsheets/export?format=html', json=quiz)
        assert response.status_code == 200 and 'General knowledge' in response.text


def test_agent_irrelevant_rag_falls_back_but_clarification_and_failures_do_not(agent, monkeypatch):
    client, app, ai, cid, mid = agent
    ai.absent = True
    message = finish(client, app, cid, send(client, cid))
    quiz = app.state.store.quiz(message['quizId'])
    assert quiz['grounding'] == 'general'
    assert quiz['request']['resolved']['fallbackReason'] == 'no_relevant_sources'
    assert ai.selected and ai.general_calls == 1
    # Removing the unrelated upload preserves the general quiz and its request.
    assert client.delete('/api/materials/' + mid).status_code == 200
    assert app.state.store.quiz(quiz['id'])['request'] is not None
    add(client, app.state.engine, cid)
    monkeypatch.setattr(ai, 'select', lambda *args: {'status': 'clarification_needed', 'message': 'Which notation?', 'sourceIds': []})
    result = finish(client, app, cid, send(client, cid, key='ambiguous-request'))
    assert result['state'] == 'clarify' and ai.general_calls == 1
    def unavailable(*args): raise ValueError('Retrieval selection provider unavailable')
    monkeypatch.setattr(ai, 'select', unavailable)
    result = finish(client, app, cid, send(client, cid, key='provider-failure'))
    assert result['state'] == 'failed' and ai.general_calls == 1


def test_general_jobs_retry_cancel_and_reject_fabricated_sources(agent, monkeypatch):
    client, app, ai, _, _ = agent
    cid = collection(client, 'Empty')
    ai.fail_generate = True
    failed = finish(client, app, cid, send(client, cid))
    assert failed['state'] == 'failed'
    ai.fail_generate = False
    ready = finish(client, app, cid, client.post(f"/api/collections/{cid}/agent/messages/{failed['id']}/retry"))
    assert ready['state'] == 'ready'
    response = send(client, cid, key='cancel-general')
    pending = response.json()['messages'][-1]
    client.post('/api/jobs/' + pending['jobId'] + '/cancel')
    before = ai.general_calls
    assert finish(client, app, cid, response)['state'] == 'failed'
    assert ai.general_calls == before
    generate = ai.generate_general
    def fabricated(*args):
        raw = generate(*args); raw['questions'][0]['quote'] = 'Fabricated lecture quotation'; return raw
    monkeypatch.setattr(ai, 'generate_general', fabricated)
    result = finish(client, app, cid, send(client, cid, key='fabricated-source'))
    assert result['state'] == 'failed' and 'invent lecture citations' in result['text']


def test_general_jobs_and_sets_remain_private(tmp_path):
    ai = AgentAI()
    app = create_app(tmp_path, ai=ai, run_jobs=False)
    with TestClient(app) as alice, TestClient(app) as bob:
        for client, name in ((alice, 'Alice'), (bob, 'Bob')):
            client.post('/api/auth/register', json={'name': name, 'email': name+'@example.test', 'password': 'StudyDemo!123'})
        cid = collection(alice)
        response = send(alice, cid)
        job_id = response.json()['messages'][-1]['jobId']
        assert alice.get('/api/jobs/' + job_id).status_code == 200
        assert bob.get('/api/jobs/' + job_id).status_code == 404
        assert bob.post('/api/jobs/' + job_id + '/cancel').status_code == 404
        ready = finish(alice, app, cid, response)
        assert bob.get('/api/quizzes/' + ready['quizId']).status_code == 404
        assert bob.get('/api/collections/' + cid + '/agent').status_code == 404
        quiz = app.state.store.quiz(ready['quizId'])
        q = quiz['questions'][0]
        alice.put('/api/quizzes/' + quiz['id'] + '/progress', json={'index': 0, 'answers': {q['id']: {'submitted': True, 'selected': 1}}})
        monkey = pytest.MonkeyPatch()
        monkey.setattr(ai, 'review_mistake_practice', lambda *a: {'status': 'ready', 'message': ''}, raising=False)
        try:
            response = alice.post('/api/quizzes/' + quiz['id'] + '/mistakes', json={'questionIds': [q['id']], 'count': 4, 'requestId': 'general-mistakes'})
            assert response.status_code == 202, response.text
            # A folder cannot be deleted while its no-upload job is active.
            assert alice.delete('/api/collections/' + cid).status_code == 409
            generate = ai.generate_general
            def different(*args):
                raw = generate(*args)
                for index, item in enumerate(raw['questions']):
                    item['prompt'] = 'A new scenario tests the same concept, with distinct wording: ' + str(index)
                return raw
            monkey.setattr(ai, 'generate_general', different)
            app.state.engine.run(response.json()['jobId'])
            job = alice.get('/api/jobs/' + response.json()['jobId']).json()
            assert job['status'] == 'completed', job
            assert app.state.store.quiz(job['result']['quizId'])['grounding'] == 'general'
            gid = alice.post('/api/groups', json={'name': 'General practice group'}).json()['id']
            shared = alice.post(f'/api/groups/{gid}/share', json={'quizId': quiz['id']}).json()['shareId']
            assert alice.get('/api/shared-sets/' + shared).json()['grounding'] == 'general'
        finally: monkey.undo()


def test_general_prompt_keeps_citations_empty_and_preserves_math_contract(monkeypatch):
    captured = {}
    monkeypatch.setattr(AI, 'structured', lambda self, system, content, schema: captured.update(system=system, content=content, schema=schema) or {})
    AI().generate_general({'prompt': 'Practice Newton laws', 'format': 'calculation', 'count': 4, 'difficulty': 'beginner'})
    assert 'sourceId and quote' in captured['system']
    assert 'standalone' in captured['system'] and 'numericAnswer' in captured['system']
    assert 'Practice Newton laws' in captured['content'][0]['text']
