import pytest
from fastapi.testclient import TestClient

from app import create_app
from retrieval import Retriever
from storage import Store
from test_app import NOTES, complete, pdf_bytes
from test_cheatsheets import SheetAI


@pytest.fixture
def folders(tmp_path):
    app = create_app(tmp_path,auth_required=False, ai=SheetAI(), run_jobs=False)
    with TestClient(app) as client:
        yield client, app.state.store, app.state.engine


def folder(client, name):
    return client.post('/api/collections', json={'name': name}).json()['id']


def notes(client, engine, cid):
    result, _ = complete(client, engine, client.post('/api/materials', data={'collectionId': cid, 'notes': NOTES}))
    return result['materialId']


def generate(client, engine, cid, fmt='mcq'):
    _, job = complete(client, engine, client.post('/api/quizzes', json={
        'collectionId': cid, 'prompt': 'Gradient descent', 'format': fmt, 'count': 4}))
    return job['result']['quizId']


def test_folder_deletion_removes_files_sources_sets_and_requests_only_in_folder(folders):
    client, store, engine = folders
    cid = folder(client, 'Delete me'); other = folder(client, 'Keep me')
    result, _ = complete(client, engine, client.post('/api/materials', data={'collectionId': cid},
        files=[('files', ('lecture.pdf', pdf_bytes(), 'application/pdf'))]))
    mid = result['materialId']; second = notes(client, engine, cid)
    sheet = generate(client, engine, cid, 'cheatsheet'); quiz = generate(client, engine, cid)
    preserved_mid = notes(client, engine, other); preserved_quiz = generate(client, engine, other)
    sources = [s['id'] for s in store.sources(mid)]
    assert (store.root / 'materials' / mid).is_dir()
    impact = client.get(f'/api/collections/{cid}/deletion-impact').json()
    assert {m['id'] for m in impact['materials']} == {mid, second}
    assert {q['id'] for q in impact['quizzes']} == {sheet, quiz}
    assert not impact['blocked']
    deletion = client.delete(f'/api/collections/{cid}', params={'expectedRevision': impact['revision']})
    assert deletion.status_code == 200, deletion.text
    assert set(deletion.json()['deletedQuizIds']) == {sheet, quiz}
    assert not (store.root / 'materials' / mid).exists()
    assert client.get(f'/api/collections/{cid}').status_code == 404
    assert client.get(f'/api/materials/{mid}').status_code == 404
    for qid in (sheet, quiz):
        assert client.get(f'/api/quizzes/{qid}').status_code == 404
        assert not store.all('SELECT * FROM quiz_sources WHERE quiz_id=?', (qid,))
    for table in ('requests', 'material_collections', 'quiz_collections', 'chunks'):
        assert not store.all(f'SELECT * FROM {table} WHERE collection_id=?', (cid,))
    assert not store.all('SELECT * FROM sources WHERE material_id=?', (mid,))
    assert not store.all('SELECT * FROM jobs WHERE material_id=?', (mid,))
    assert not engine.retriever.vectors().get(where={'collectionId': cid})['ids']
    assert client.get(f'/api/materials/{preserved_mid}').status_code == 200
    assert client.get(f'/api/quizzes/{preserved_quiz}').status_code == 200
    assert engine.retriever.search(other, [preserved_mid], 'gradient descent')
    reopened = Store(store.root)
    assert [c['id'] for c in reopened.all('SELECT id FROM collections')] == [other]
    assert not any(reopened.one('SELECT id FROM sources WHERE id=?', (sid,)) for sid in sources)


@pytest.mark.parametrize('kind', ['material', 'index', 'quiz'])
def test_folder_deletion_blocks_active_dependencies(folders, kind):
    client, store, engine = folders
    cid = folder(client, 'Working folder')
    if kind == 'material':
        result = client.post('/api/materials', data={'collectionId': cid, 'notes': NOTES}).json()
    else:
        mid = notes(client, engine, cid)
        if kind == 'index':
            result = client.post(f'/api/materials/{mid}/index').json()
        else:
            result = client.post('/api/quizzes', json={'collectionId': cid, 'prompt': 'Gradient descent'}).json()
    impact = client.get(f'/api/collections/{cid}/deletion-impact').json()
    assert impact['blocked']
    assert client.delete(f'/api/collections/{cid}').status_code == 409
    assert store.job(result['jobId'])
    client.post(f"/api/jobs/{result['jobId']}/cancel")
    # A cancellation request is not proof the worker has stopped.
    assert client.delete(f'/api/collections/{cid}').status_code == 409
    engine.run(result['jobId'])
    assert client.delete(f'/api/collections/{cid}').status_code == 200


def test_stale_confirmation_preserves_new_content(folders):
    client, store, engine = folders
    cid = folder(client, 'Changing folder'); notes(client, engine, cid)
    old = client.get(f'/api/collections/{cid}/deletion-impact').json()
    mid = notes(client, engine, cid)
    result = client.delete(f'/api/collections/{cid}', params={'expectedRevision': old['revision']})
    assert result.status_code == 409
    assert 'changed' in result.json()['error']
    assert store.material(mid)
    fresh = client.get(f'/api/collections/{cid}/deletion-impact').json()
    client.patch(f'/api/collections/{cid}', json={'name': 'Renamed'})
    assert client.delete(f'/api/collections/{cid}', params={'expectedRevision': fresh['revision']}).status_code == 409


def test_empty_folder_and_missing_folder(folders):
    client, store, engine = folders
    cid = folder(client, 'Empty')
    impact = client.get(f'/api/collections/{cid}/deletion-impact').json()
    assert impact['materials'] == [] and impact['quizzes'] == []
    assert client.delete(f'/api/collections/{cid}').json() == {
        'deleted': True, 'deletedMaterialIds': [], 'deletedQuizIds': [], 'deletedJobIds': []}
    assert client.delete(f'/api/collections/{cid}').status_code == 404
    assert client.get(f'/api/collections/{cid}/deletion-impact').status_code == 404


def test_folder_cleanup_failure_cannot_expose_deleted_sources(folders, monkeypatch):
    client, store, engine = folders
    cid = folder(client, 'Cleanup'); mid = notes(client, engine, cid)
    assert engine.retriever.search(cid, [mid], 'gradient descent')
    monkeypatch.setattr(engine.retriever, 'cleanup', lambda: None)
    assert client.delete(f'/api/collections/{cid}').status_code == 200
    assert store.all('SELECT id FROM vector_cleanup')
    assert engine.retriever.search(cid, [mid], 'gradient descent') == []
    reopened = Retriever(Store(store.root), engine.ai)
    reopened.cleanup()
    assert not store.all('SELECT id FROM vector_cleanup')
    assert not reopened.vectors().get(where={'collectionId': cid})['ids']


def test_upload_commit_rechecks_folder_after_streaming(folders, monkeypatch):
    import asyncio
    from starlette.datastructures import UploadFile
    client, store, engine = folders
    cid = folder(client, 'Concurrent upload')
    original = UploadFile.read
    removed = False

    async def read_and_delete(file, size=-1):
        nonlocal removed
        content = await original(file, size)
        if content and not removed:
            removed = True
            response = await asyncio.to_thread(client.delete, f'/api/collections/{cid}')
            assert response.status_code == 200
        return content

    monkeypatch.setattr(UploadFile, 'read', read_and_delete)
    response = client.post('/api/materials', data={'collectionId': cid},
        files=[('files', ('lecture.txt', NOTES.encode(), 'text/plain'))])
    assert removed and response.status_code == 404
    assert not store.all('SELECT * FROM materials')
    assert not store.all('SELECT * FROM jobs')
    assert not list((store.root / 'materials').iterdir())
    assert not Store(store.root).all('SELECT * FROM collections')
