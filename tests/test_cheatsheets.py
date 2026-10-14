import copy

import pytest
from fastapi.testclient import TestClient

from app import create_app
from ai import AI
from schemas import GeneratedCheatSheet, generation_schema, validate_cheatsheet
from storage import Store
from test_app import FakeAI, NOTES, complete, pdf_bytes


class SheetAI(FakeAI):
    embedding_model = 'fixture-embedding'

    def select(self, prompt, sources):
        if self.absent:
            return super().select(prompt, sources)
        return {'status': 'ready', 'message': '', 'sourceIds': [s['id'] for s in sources]}

    def generate(self, params, sources, validation_feedback=''):
        if params['format'] != 'cheatsheet':
            return super().generate(params, sources, validation_feedback)
        if self.fail_generate:
            raise ValueError('Fixture quota exhausted')
        self.generate_calls += 1
        return {'status': 'ready', 'message': '', 'title': 'Gradient descent reference', 'description': '',
                'sections': [{'heading': 'Concept ' + str(i + 1), 'points': ['Subtract the step from the parameter.'],
                              'formulas': ['w_new = w - eta * gradient'],
                              'sourceId': sources[i % len(sources)]['id'],
                              'quote': sources[i % len(sources)]['text']}
                             for i in range(params['count'])]}


def test_sheet_schema_and_prompt(monkeypatch):
    ai = AI()
    captured = {}
    def structured(system, content, schema):
        captured.update(system=system, content=content, schema=schema)
        return {'status': 'insufficient_source', 'message': 'Missing topic', 'title': '', 'description': '', 'sections': []}
    monkeypatch.setattr(ai, 'structured', structured)
    ai.generate({'prompt': 'Gradient descent', 'format': 'cheatsheet', 'count': 4}, [])
    assert captured['schema'] is GeneratedCheatSheet is generation_schema('cheatsheet')
    assert 'authoritative' in captured['system']
    assert 'never evidence' in captured['system']


def test_sheet_validation_rejects_unsupported_evidence():
    source = {'id': 'chunk', 'originalSourceId': 'original', 'name': 'Lecture.pdf', 'locator': 'Page 2',
              'kind': 'pdf', 'page': 2, 'text': NOTES}
    raw = SheetAI().generate({'format': 'cheatsheet', 'count': 4}, [source])
    result = validate_cheatsheet(raw, [source], 4)
    assert [s['id'] for s in result['sections']] == ['s0', 's1', 's2', 's3']
    assert result['sections'][0]['source']['id'] == 'original'
    assert result['sections'][0]['source']['name'] == 'Lecture.pdf'
    assert result['questions'] == []
    invalid = copy.deepcopy(raw)
    invalid['sections'][0]['sourceId'] = 'invented'
    with pytest.raises(ValueError, match='reference'):
        validate_cheatsheet(invalid, [source], 4)
    invalid = copy.deepcopy(raw)
    invalid['sections'][0]['quote'] = 'Invented excerpt'
    with pytest.raises(ValueError, match='excerpt'):
        validate_cheatsheet(invalid, [source], 4)
    invalid = copy.deepcopy(raw)
    invalid['sections'][0]['points'] = []
    with pytest.raises(ValueError, match='key points'):
        validate_cheatsheet(invalid, [source], 4)
    invalid = copy.deepcopy(raw)
    invalid['sections'][1]['heading'] = invalid['sections'][0]['heading']
    with pytest.raises(ValueError, match='distinct'):
        validate_cheatsheet(invalid, [source], 4)
    with pytest.raises(ValueError, match='instead of'):
        validate_cheatsheet(raw, [source], 6)


def test_pdf_sheet_saved_sources_followup_and_failures(tmp_path):
    ai = SheetAI()
    app = create_app(tmp_path, ai=ai, run_jobs=False)
    with TestClient(app) as client:
        c = client.post('/api/collections', json={'name': 'Machine Learning'}).json()['id']
        material, _ = complete(client, app.state.engine, client.post('/api/materials',
            data={'collectionId': c}, files=[('files', ('lecture.pdf', pdf_bytes(), 'application/pdf'))]))
        _, job = complete(client, app.state.engine, client.post('/api/quizzes', json={
            'collectionId': c, 'prompt': 'Gradient descent', 'format': 'cheatsheet', 'count': 4}))
        sid = job['result']['quizId']
        sheet = client.get('/api/quizzes/' + sid).json()
        assert sheet['format'] == 'cheatsheet' and len(sheet['sections']) == 4
        source = client.get(sheet['sections'][0]['source']['url']).json()
        assert source['page'] == 1
        assert client.get(source['previewUrl']).content.startswith(b'\x89PNG')
        listing = client.get('/api/quizzes?collectionId=' + c).json()['quizzes'][0]
        assert listing['sectionCount'] == 4 and listing['questionCount'] == 0
        assert sheet['request']['submitted']['prompt'] == 'Gradient descent'
        assert sheet['request']['snapshot'][0]['sourceId'] == source['id']
        assert client.put('/api/quizzes/' + sid + '/progress', json={'index': 0}).status_code == 400
        # A sheet may be the parent for practice; evidence still comes from the lecture.
        _, followup = complete(client, app.state.engine, client.post('/api/quizzes', json={
            'collectionId': c, 'parentQuizId': sid, 'prompt': 'Practice the update rule', 'format': 'flashcard'}))
        q = client.get('/api/quizzes/' + followup['result']['quizId']).json()
        assert q['format'] == 'flashcard'
        assert q['request']['resolved']['followupContext']['sections'] == [s['heading'] for s in sheet['sections']]
        ai.absent = True
        _, absent = complete(client, app.state.engine, client.post('/api/quizzes', json={
            'collectionId': c, 'format': 'cheatsheet', 'count': 4, 'prompt': 'Absent topic'}))
        assert absent['result']['status'] == 'insufficient_source'
        assert client.get('/api/quizzes/' + sid).status_code == 200
        ai.absent = False
        ai.fail_generate = True
        response = client.post('/api/quizzes', json={'collectionId': c, 'format': 'cheatsheet', 'count': 4, 'prompt': 'Gradient descent'}).json()
        app.state.engine.run(response['jobId'])
        assert app.state.store.job(response['jobId'])['status'] == 'failed'
        assert client.get('/api/quizzes/' + sid).status_code == 200
    # A fresh store restores section citations as well as question citations.
    reopened = Store(tmp_path)
    assert len(reopened.quiz(sid)['sections']) == 4
    assert reopened.all('SELECT source_id FROM quiz_sources WHERE quiz_id=?', (sid,))
    app = create_app(tmp_path, ai=SheetAI(), run_jobs=False)
    with TestClient(app) as client:
        impact = client.get('/api/materials/' + material['materialId'] + '/deletion-impact').json()
        assert sid in [q['id'] for q in impact['quizzes']]
        client.delete('/api/materials/' + material['materialId'])
        assert client.get('/api/quizzes/' + sid).status_code == 404


def test_sheet_quote_schema_locks_exact_excerpts():
    from schemas import sheet_generation_schema, sheet_excerpts
    sources = [{'id': 's1', 'text': 'The gradient is ∇L(w). The update is w − η ∇L(w).'},
               {'id': 's2', 'text': 'A high learning rate may diverge.'}]
    schema = sheet_generation_schema(sources).model_json_schema()
    section = schema['$defs']['CitedSheetSection']['properties']
    assert set(section['sourceId']['enum']) == {'s1', 's2'}
    assert set(section['quoteId']['enum']) == {q['id'] for s in sources for q in sheet_excerpts(s)}
    assert all(q['text'] in s['text'] for s in sources for q in sheet_excerpts(s))
    assert all('\n' not in q['id'] for s in sources for q in sheet_excerpts(s))
    source = {'id':'s1','text':'A gradient points uphill.\nSubtract it.', 'name':'Notes','locator':'Section 1','kind':'text'}
    raw = SheetAI().generate({'format':'cheatsheet','count':4}, [source])
    for s in raw['sections']:
        s.pop('quote');s['quoteId']=sheet_excerpts(source)[-1]['id']
    result = validate_cheatsheet(raw,[source],4)
    assert result['sections'][0]['source']['quote']==source['text']
    raw['sections'][0]['quoteId']='invented'
    with pytest.raises(ValueError,match='excerpt'):
        validate_cheatsheet(raw,[source],4)


def test_sheet_collection_growth_isolation_and_dependencies(tmp_path):
    ai = SheetAI()
    app = create_app(tmp_path, ai=ai, run_jobs=False)
    with TestClient(app) as client:
        engine, store = app.state.engine, app.state.store
        c = client.post('/api/collections', json={'name': 'ML'}).json()['id']
        other = client.post('/api/collections', json={'name': 'History'}).json()['id']
        mids = []
        for cid, text in [(c, NOTES), (c, 'Learning rate eta controls the update step. ' + NOTES), (other, 'Unrelated historical events')]:
            material, _ = complete(client, engine, client.post('/api/materials', data={'collectionId': cid, 'notes': text}))
            if cid == c:
                mids.append(material['materialId'])
        _, job = complete(client, engine, client.post('/api/quizzes', json={'collectionId': c, 'format': 'cheatsheet', 'count': 4, 'prompt': 'Gradient descent'}))
        sheet = client.get('/api/quizzes/' + job['result']['quizId']).json()
        expected = {store.sources(mid)[0]['id'] for mid in mids}
        assert {s['source']['id'] for s in sheet['sections']} == expected
        assert {entry['materialId'] for entry in sheet['request']['snapshot']} == set(mids)
        assert len(store.all('SELECT * FROM quiz_sources WHERE quiz_id=?', (sheet['id'],))) == 2
        assert not client.get('/api/quizzes?collectionId=' + other).json()['quizzes']
        client.delete('/api/materials/' + mids[1])
        assert client.get('/api/quizzes/' + sheet['id']).status_code == 404
        assert store.material(mids[0]) is not None
