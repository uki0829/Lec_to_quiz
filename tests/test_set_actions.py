import json

import pytest

from storage import Store
from test_accounts_groups import social
from test_app import prepared_notes, generate, complete


@pytest.fixture
def managed(social):
    app, alice, bob = social
    mid = prepared_notes(alice, app.state.engine)
    sets = [generate(alice, app.state.engine, mid, kind) for kind in ('mcq', 'flashcard', 'calculation')]
    return app, alice, bob, mid, sets


@pytest.mark.parametrize('position', [0, 1, 2])
def test_rename_preserves_content_progress_and_request(managed, position):
    app, alice, bob, mid, sets = managed
    q = sets[position]
    progress = {'index': 1, 'answers': {q['questions'][0]['id']: {'submitted': True, 'correct': True}}}
    alice.put('/api/quizzes/'+q['id']+'/progress', json=progress)
    original = alice.get('/api/quizzes/'+q['id']).json()
    result = alice.patch('/api/quizzes/'+q['id'], json={'title': '  Exam practice  '})
    assert result.status_code == 200
    changed = result.json()
    assert changed['title'] == 'Exam practice'
    assert {k: v for k, v in changed.items() if k != 'title'} == {k: v for k, v in original.items() if k != 'title'}
    listed = alice.get('/api/quizzes').json()['quizzes']
    assert next(x for x in listed if x['id'] == q['id'])['title'] == 'Exam practice'
    assert bob.patch('/api/quizzes/'+q['id'], json={'title': 'Not mine'}).status_code == 404
    assert alice.patch('/api/quizzes/'+q['id'], json={'title': '   '}).status_code == 400
    assert alice.patch('/api/quizzes/'+q['id'], json={'title': 'x'*161}).status_code == 422
    assert alice.get('/api/quizzes/'+q['id']).json()['title'] == 'Exam practice'


def test_permanent_removal_cleans_quiz_records_and_cannot_restore(managed):
    app, alice, bob, mid, sets = managed
    store = app.state.store
    cid = store.collection_for(mid)
    q, cards = sets[:2]
    progress = {'index': 1, 'answers': {q['questions'][0]['id']: {'submitted': True, 'correct': False}}}
    alice.put('/api/quizzes/'+q['id']+'/progress', json=progress)
    alice.put('/api/quizzes/'+cards['id']+'/questions/'+cards['questions'][0]['id']+'/star', json={'starred': True})
    store.execute('INSERT INTO question_hints VALUES(?,?,?,?)',
                  (cards['id'], cards['questions'][0]['id'], 'A cached cue', 1))
    source_count = len(store.sources(mid))
    ids = [x['id'] for x in sets]
    response = alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': ids})
    assert response.status_code == 200
    assert response.json()['removedQuizIds'] == ids
    assert alice.get('/api/quizzes').json()['quizzes'] == []
    assert alice.get(f'/api/collections/{cid}/question-bank').json()['questions'] == []
    for qid in ids:
        assert alice.get('/api/quizzes/'+qid).status_code == 404
    assert Store(store.root).quiz(q['id']) is None  # still hidden after reopening SQLite
    assert len(store.sources(mid)) == source_count
    assert alice.get('/api/materials/'+mid).status_code == 200
    assert alice.post(f'/api/collections/{cid}/quizzes/restore', json={'quizIds': ids}).status_code == 404
    for qid in ids:
        assert store.one('SELECT id FROM quizzes WHERE id=?', (qid,)) is None
        for table in ('quiz_collections','quiz_sources','starred_questions','question_hints','quiz_removals','requests'):
            assert store.one(f'SELECT * FROM {table} WHERE quiz_id=?', (qid,)) is None
        assert store.quiz_request(qid) is None
    assert alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': ids}).status_code == 404


def test_selection_is_atomic_and_scoped_to_folder_and_owner(managed):
    app, alice, bob, mid, sets = managed
    cid = app.state.store.collection_for(mid)
    other_mid = prepared_notes(bob, app.state.engine)
    other = generate(bob, app.state.engine, other_mid)
    qid = sets[0]['id']
    for invalid in ('missing', other['id']):
        assert alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': [qid, invalid]}).status_code == 404
        assert alice.get('/api/quizzes/'+qid).status_code == 200
    assert bob.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': [qid]}).status_code == 404
    assert alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': []}).status_code == 422
    # Duplicates are harmless, and a single selected quiz works.
    result = alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': [qid, qid]})
    assert result.json()['removedQuizIds'] == [qid]
    assert len(alice.get('/api/quizzes').json()['quizzes']) == 2
    assert bob.post(f'/api/collections/{cid}/quizzes/restore', json={'quizIds': [qid]}).status_code == 404
    assert alice.patch('/api/quizzes/'+qid, json={'title': 'Removed'}).status_code == 404


def test_active_followup_blocks_permanent_removal(managed):
    app, alice, bob, mid, sets = managed
    store = app.state.store
    cid = store.collection_for(mid)
    qid = sets[0]['id']
    job = store.add_job('quiz', mid, {'collectionId': cid, 'parentQuizId': qid})
    assert alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': [qid]}).status_code == 409
    assert alice.get('/api/quizzes/'+qid).status_code == 200
    store.update_job(job, status='cancelled')
    assert alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds': [qid]}).status_code == 200
    assert alice.delete('/api/materials/'+mid).status_code == 200
    assert store.all('SELECT * FROM quiz_removals') == []
    assert alice.post(f'/api/collections/{cid}/quizzes/restore', json={'quizIds': [qid]}).status_code == 404


def test_flashcard_review_counts_without_self_grading(managed):
    app, alice, bob, mid, sets = managed
    quiz = sets[1]
    first, second = quiz['questions'][:2]
    progress = {'index': 1, 'answers': {first['id']: {'reviewed': True, 'revealed': False},
                                       second['id']: {'reviewed': True, 'revealed': True}}}
    assert alice.put('/api/quizzes/'+quiz['id']+'/progress', json=progress).status_code == 200
    saved = alice.get('/api/quizzes/'+quiz['id']).json()
    assert saved['progress'] == progress
    listing = alice.get('/api/quizzes').json()['quizzes']
    assert next(q for q in listing if q['id'] == quiz['id'])['answeredCount'] == 2


def test_delete_parent_preserves_child_but_removes_parent_context(managed, monkeypatch):
    app, alice, bob, mid, sets = managed
    store = app.state.store
    parent = sets[0]
    cid = store.collection_for(mid)
    original = app.state.engine.ai.generate
    def followup(params, sources, validation_feedback=''):
        result = original(params, sources, validation_feedback)
        for q in result['questions']:
            q['prompt'] = 'A different exercise: ' + q['prompt']
        return result
    monkeypatch.setattr(app.state.engine.ai, 'generate', followup)
    _, job = complete(alice, app.state.engine, alice.post('/api/quizzes', json={
        'collectionId': cid, 'parentQuizId': parent['id'], 'prompt': 'Follow-up practice',
        'format': 'mcq', 'count': 4, 'difficulty': 'beginner'}))
    child_id = job['result']['quizId']
    child_before = alice.get('/api/quizzes/'+child_id).json()
    assert store.quiz_request(child_id)['parent_quiz_id'] == parent['id']
    assert alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds':[parent['id']]}).status_code == 200
    child_after = alice.get('/api/quizzes/'+child_id).json()
    assert child_after['questions'] == child_before['questions']
    request = store.quiz_request(child_id)
    assert request['parent_quiz_id'] is None
    assert 'followupContext' not in request['resolved']
    assert 'parentQuizId' not in request['submitted']
    params = store.one('SELECT params FROM jobs WHERE id=?', (job['id'],))
    assert 'followupContext' not in json.loads(params['params'])


def test_private_deletion_preserves_explicit_shared_copy(managed):
    app, alice, bob, mid, sets = managed
    cid = app.state.store.collection_for(mid)
    q = sets[0]
    group_id = alice.post('/api/groups', json={'name':'Study circle'}).json()['id']
    share_id = alice.post('/api/groups/'+group_id+'/share', json={'quizId':q['id']}).json()['shareId']
    assert alice.post(f'/api/collections/{cid}/quizzes/remove', json={'quizIds':[q['id']]}).status_code == 200
    assert alice.get('/api/quizzes/'+q['id']).status_code == 404
    shared = alice.get('/api/shared-sets/'+share_id)
    assert shared.status_code == 200
    assert len(shared.json()['questions']) == len(q['questions'])
    assert app.state.store.one('SELECT original_quiz_id FROM group_sets WHERE id=?', (share_id,))['original_quiz_id'] is None
