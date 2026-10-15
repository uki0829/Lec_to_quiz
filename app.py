"""Local-only Lecture Lab server. Run with .venv/bin/python app.py."""
import contextlib
import json
import hashlib
import mimetypes
import re
import os
import shutil
import time
import threading
from pathlib import Path

import pymupdf as fitz
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sheet_documents import render_html, render_pdf, validate_document
from study_agent import StudyAgent
from mistakes import register_mistake_routes
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ai import AI
from processing import Engine, duration, ffmpeg_path
from storage import Store, uid, CURRENT_USER
from accounts import Accounts
from study_groups import Groups
from schemas import normalize

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
EXTENSIONS = {".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
              ".mp3": "audio", ".wav": "audio", ".ogg": "audio", ".flac": "audio", ".m4a": "audio",
              ".mp4": "video", ".webm": "video", ".txt": "text"}
LIMITS = {"pdf": 25*1024**2, "image": 10*1024**2, "audio": 500*1024**2,
          "video": 500*1024**2, "text": 500*1024}


class QuizRequest(BaseModel):
    materialId: str | None = None
    collectionId: str | None = None
    parentQuizId: str | None = None
    prompt: str = Field(min_length=1, max_length=4000)
    format: str | None = None
    count: int | None = None
    difficulty: str | None = None


class StarStatus(BaseModel):
    starred: bool


class CollectionName(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class QuizName(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class QuizSelection(BaseModel):
    quizIds: list[str] = Field(min_length=1, max_length=100)


def create_app(data_dir=None, ai=None, run_jobs=True, auth_required=True):
    store = Store(data_dir or (ROOT / os.getenv("LECTURE_LAB_DATA_DIR", "data")))
    engine = Engine(store, ai or AI())
    accounts = Accounts(store)
    groups = Groups(store, accounts)
    mutation_lock = threading.RLock()
    study_agent = StudyAgent(store, engine)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        store.recover_interrupted_jobs()
        study_agent.recover()
        if run_jobs:
            engine.retriever.cleanup()
            if not isinstance(engine.ai, AI) or os.getenv('OPENAI_API_KEY'):
                for row in store.all("SELECT id FROM materials WHERE status='ready'"):
                    if not engine.retriever.is_ready(row['id']):
                        dispatch('index', row['id'])
        yield
        store.execute("UPDATE jobs SET cancel=1 WHERE status IN ('queued','running')")
        engine.pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Lecture Lab", lifespan=lifespan)
    app.state.store, app.state.engine = store, engine
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])

    @app.middleware("http")
    async def local_boundary(request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD") and origin and origin != str(request.base_url).rstrip("/"):
            return JSONResponse({"error": "Use the local Lecture Lab page to make this request."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.middleware("http")
    async def identity_boundary(request, call_next):
        user = accounts.session_user(request)
        token = CURRENT_USER.set(user)
        try:
            if request.url.path.startswith('/api/') and not request.url.path.startswith('/api/auth/'):
                if auth_required and not user:
                    return JSONResponse({'error':'Sign in to continue.'}, status_code=401)
                if auth_required:
                    try:
                        accounts.authorize_path(request, user)
                    except HTTPException as exc:
                        return JSONResponse({'error':exc.detail},status_code=exc.status_code)
            return await call_next(request)
        finally:
            CURRENT_USER.reset(token)

    accounts.routes(app)
    groups.routes(app)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    def dispatch(kind, material_id, params=None):
        if kind == 'quiz' and store.one("SELECT id FROM jobs WHERE kind='quiz' AND status IN ('queued','running') AND json_extract(params,'$.collectionId')=?", (params['collectionId'],)):
            raise HTTPException(409, 'This collection already has an active quiz job.')
        if store.one("SELECT id FROM jobs WHERE material_id=? AND status IN ('queued','running')", (material_id,)):
            raise HTTPException(409, "This material already has an active job. Wait or cancel it first.")
        job_id = store.add_job(kind, material_id, params)
        if kind == 'quiz':
            store.execute('INSERT INTO requests(id,job_id,collection_id,parent_quiz_id,submitted,resolved,created) VALUES(?,?,?,?,?,?,?)',
                          (uid(), job_id, params['collectionId'], params.get('parentQuizId'),
                           json.dumps(params.get('submitted', params)), json.dumps(params), time.time()))
        if run_jobs:
            engine.submit(job_id)
        return {"jobId": job_id, "materialId": material_id}

    @app.get("/")
    def page():
        return FileResponse(ROOT / "source" / "page.html")

    @app.get('/study/local')
    @app.get('/study/{kind}/{set_id}')
    def study_page(kind: str = '', set_id: str = ''):
        # The shell contains no study data; authenticated APIs resolve each set.
        return FileResponse(ROOT / 'source' / 'page.html')

    app.mount("/static", StaticFiles(directory=ROOT / "source"), name="static")

    @app.get("/api/config")
    def config():
        try:
            path = ffmpeg_path()
            ready = Path(path).is_file()
        except Exception:
            ready = False
        return {"connected": bool(os.getenv("OPENAI_API_KEY")), "model": engine.ai.model,
                "transcriptionModel": engine.ai.audio_model, "ffmpegAvailable": ready,
                "maxDurationMinutes": 30, "embeddingModel": engine.retriever.model,
                "rerankConfigured": bool(engine.reranker.api_key), "rerankModel": engine.reranker.model}

    def require_collection(cid):
        row = store.one('SELECT * FROM collections WHERE id=?', (cid,))
        if not row or (auth_required and not accounts.owns_collection(cid)):
            raise HTTPException(404, 'Study collection not found.')
        return row

    def material_brief(row):
        mid = row['id']
        latest = store.one('SELECT id,status FROM jobs WHERE material_id=? AND kind IN (\'material\',\'index\') ORDER BY created DESC LIMIT 1', (mid,))
        return {'id': mid, 'title': row['title'], 'status': row['status'], 'created': row['created'],
                'collectionId': store.collection_for(mid), 'jobId': latest['id'] if latest else None,
                'jobStatus': latest['status'] if latest else None, 'searchReady': engine.retriever.is_ready(mid),
                'sourceCount': len(store.sources(mid))}

    @app.get('/api/collections')
    def collections():
        rows = store.all('SELECT c.* FROM collections c JOIN collection_owners o ON o.collection_id=c.id WHERE o.user_id=? ORDER BY c.created DESC', (CURRENT_USER.get()['id'],)) if auth_required else store.all('SELECT * FROM collections ORDER BY created DESC')
        folders = []
        for row in rows:
            members = store.collection_materials(row['id'])
            folders.append({**row, 'materialCount': len(members),
                            'fileCount': sum(len(json.loads(m['files'])) for m in members),
                            'noteCount': sum(bool(m['notes']) for m in members)})
        return {'collections': folders}

    @app.post('/api/collections', status_code=201)
    def add_collection(body: CollectionName):
        name = body.name.strip()
        if not name:
            raise HTTPException(400, 'Enter a collection name.')
        cid = store.add_collection(name)
        return require_collection(cid)

    @app.get('/api/collections/{cid}')
    def collection(cid: str):
        latest = store.one("SELECT id,status,created FROM jobs WHERE kind='quiz' AND json_extract(params,'$.collectionId')=? ORDER BY created DESC LIMIT 1", (cid,))
        return {**require_collection(cid), 'latestQuizJob': latest,
                'materials': [material_brief(m) for m in store.collection_materials(cid)]}

    @app.patch('/api/collections/{cid}')
    def rename_collection(cid: str, body: CollectionName):
        with mutation_lock:
            require_collection(cid)
            if not body.name.strip():
                raise HTTPException(400, 'Enter a collection name.')
            store.execute('UPDATE collections SET name=? WHERE id=?', (body.name.strip(), cid))
            return require_collection(cid)

    def folder_impact(cid):
        folder = require_collection(cid)
        members = store.collection_materials(cid)
        quizzes = store.all(
            'SELECT DISTINCT q.id,q.body FROM quizzes q WHERE q.id IN '
            '(SELECT quiz_id FROM quiz_collections WHERE collection_id=? UNION '
            'SELECT qs.quiz_id FROM quiz_sources qs JOIN sources s ON s.id=qs.source_id '
            'JOIN material_collections mc ON mc.material_id=s.material_id WHERE mc.collection_id=?) '
            'ORDER BY q.id', (cid, cid))
        jobs = store.all(
            "SELECT DISTINCT j.id,j.status FROM jobs j WHERE json_extract(j.params,'$.collectionId')=? "
            'OR j.material_id IN (SELECT material_id FROM material_collections WHERE collection_id=?) '
            "OR EXISTS (SELECT 1 FROM json_each(j.params,'$.materialSnapshot') snap "
            'JOIN material_collections mc ON mc.material_id=snap.value WHERE mc.collection_id=?) '
            'ORDER BY j.id', (cid, cid, cid))
        materials = [{'id': m['id'], 'title': m['title']} for m in members]
        sets = [{'id': q['id'], 'title': json.loads(q['body'])['title']} for q in quizzes]
        # Refuse a stale confirmation if new uploads/sets have appeared or the name changed.
        revision = hashlib.sha256(json.dumps([folder['name'], sorted(m['id'] for m in members),
                                              sets, [j['id'] for j in jobs]], sort_keys=True).encode()).hexdigest()
        return {'id': cid, 'name': folder['name'], 'materials': materials, 'quizzes': sets,
                'jobIds': [j['id'] for j in jobs], 'revision': revision,
                'blocked': any(j['status'] in ('queued', 'running') for j in jobs)}

    @app.get('/api/collections/{cid}/deletion-impact')
    def collection_deletion_impact(cid: str):
        with mutation_lock:
            return folder_impact(cid)

    @app.delete('/api/collections/{cid}')
    def delete_collection(cid: str, expectedRevision: str | None = None):
        with mutation_lock:
            impact = folder_impact(cid)
            if impact['blocked']:
                raise HTTPException(409, 'Stop active processing before deleting this folder.')
            if expectedRevision is not None and expectedRevision != impact['revision']:
                raise HTTPException(409, 'Folder contents changed. Close and reopen the deletion preview.')
            mids = [m['id'] for m in impact['materials']]
            qids = [q['id'] for q in impact['quizzes']]
            with store.connect() as db:
                for qid in qids:
                    for table in ('starred_questions', 'question_hints', 'quiz_sources', 'quiz_collections', 'quiz_removals', 'quizzes'):
                        db.execute(f"DELETE FROM {table} WHERE {'id' if table == 'quizzes' else 'quiz_id'}=?", (qid,))
                    db.execute('DELETE FROM requests WHERE quiz_id=?', (qid,))
                for mid in mids:
                    db.execute('INSERT OR IGNORE INTO vector_cleanup SELECT id FROM chunks WHERE material_id=?', (mid,))
                    for table in ('chunks', 'sources', 'material_collections'):
                        db.execute(f'DELETE FROM {table} WHERE material_id=?', (mid,))
                    db.execute('DELETE FROM materials WHERE id=?', (mid,))
                for jid in impact['jobIds']:
                    db.execute('DELETE FROM requests WHERE job_id=?', (jid,))
                    db.execute('DELETE FROM jobs WHERE id=?', (jid,))
                db.execute('DELETE FROM requests WHERE collection_id=?', (cid,))
                db.execute('DELETE FROM agent_messages WHERE thread_id IN (SELECT id FROM agent_threads WHERE collection_id=?)', (cid,))
                db.execute('DELETE FROM agent_threads WHERE collection_id=?', (cid,))
                db.execute('DELETE FROM collection_owners WHERE collection_id=?', (cid,))
                db.execute('DELETE FROM collections WHERE id=?', (cid,))
            for mid in mids:
                shutil.rmtree(store.root / 'materials' / mid, ignore_errors=True)
            engine.retriever.cleanup()
            return {'deleted': True, 'deletedMaterialIds': mids, 'deletedQuizIds': qids,
                    'deletedJobIds': impact['jobIds']}

    @app.post("/api/materials", status_code=202)
    async def upload(files: list[UploadFile] = File(default=[]), notes: str = Form(default=""), collectionId: str | None = Form(default=None)):
        if collectionId:
            require_collection(collectionId)
        notes = notes.strip()
        if not files and not notes:
            raise HTTPException(400, "Upload lecture material or paste notes.")
        if len(files) > 4 or len(notes) > 100000:
            raise HTTPException(400, "Use at most four files and 100,000 characters of pasted notes.")
        material_id = uid()
        folder = store.root / "materials" / material_id
        folder.mkdir(parents=True)
        saved, total, pages = [], 0, 0
        try:
            for file in files:
                name = Path((file.filename or "upload").replace("\\", "/")).name[:180]
                extension = Path(name).suffix.lower()
                kind = EXTENSIONS.get(extension)
                if not kind:
                    raise HTTPException(400, f"Unsupported file: {name}")
                file_id = uid()
                stored = file_id + extension
                path = folder / stored
                size = 0
                with path.open("wb") as target:
                    while chunk := await file.read(1024*1024):
                        size += len(chunk)
                        total += len(chunk)
                        if size > LIMITS[kind] or total > 1024**3:
                            raise HTTPException(413, "File size limit exceeded. Use PDFs ≤25 MB, images ≤10 MB, recordings ≤500 MB, and ≤1 GB combined.")
                        target.write(chunk)
                if size == 0:
                    raise HTTPException(400, f"{name} is empty.")
                if kind == "pdf":
                    with fitz.open(path) as pdf:
                        if pdf.needs_pass:
                            raise HTTPException(400, "Unlock the PDF before uploading it.")
                        pages += len(pdf)
                        if pages > 100 or not len(pdf):
                            raise HTTPException(400, "Use 1–100 PDF pages per material set.")
                if kind == "image":
                    from PIL import Image
                    with Image.open(path) as image:
                        image.verify()
                if kind == "text" and len(path.read_text(encoding="utf-8")) > 100000:
                    raise HTTPException(400, "Use a text file with at most 100,000 characters.")
                if kind in ("audio", "video"):
                    length = duration(path)
                    if length > 1800.1:
                        raise HTTPException(400, "Recordings must be no longer than 30 minutes.")
                saved.append({"id": file_id, "name": name, "stored": stored, "kind": kind, "size": size})
            with mutation_lock:
                # An upload may have streamed while its folder was deleted.
                if collectionId:
                    require_collection(collectionId)
                store.add_material(material_id, saved, notes, collectionId)
                return dispatch("material", material_id)
        except HTTPException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(folder, ignore_errors=True)
            raise HTTPException(400, "A file could not be read. Check its format, encoding, or integrity.") from exc
        finally:
            for file in files:
                await file.close()

    @app.get("/api/materials")
    def materials():
        rows = store.all('SELECT m.* FROM materials m JOIN material_collections mc ON mc.material_id=m.id JOIN collection_owners o ON o.collection_id=mc.collection_id WHERE o.user_id=? ORDER BY m.created DESC',(CURRENT_USER.get()['id'],)) if auth_required else store.all('SELECT * FROM materials ORDER BY created DESC')
        result = [material_brief(r) for r in rows]
        return {"materials": result}

    @app.get("/api/materials/{material_id}")
    def material(material_id: str):
        row = store.material(material_id)
        if not row:
            raise HTTPException(404, "Material not found.")
        sources = store.sources(material_id)
        return {**material_brief(row), "notes": row["notes"],
                "files": [{k: v for k, v in f.items() if k != "stored"} for f in row["files"]],
                "sources": [{k: v for k, v in s.items() if k not in ("framePath",)} for s in sources]}

    @app.post('/api/materials/{material_id}/index', status_code=202)
    def index_material(material_id: str):
        row = store.material(material_id)
        if not row or row['status'] != 'ready':
            raise HTTPException(400, 'Complete extraction before indexing this material.')
        with mutation_lock:
            if not store.material(material_id):
                raise HTTPException(404, 'Material not found.')
            return dispatch('index', material_id)

    def affected_quizzes(material_id):
        return store.all('SELECT DISTINCT q.id,q.body FROM quizzes q JOIN quiz_sources qs ON qs.quiz_id=q.id '
                         'JOIN sources s ON s.id=qs.source_id WHERE s.material_id=?', (material_id,))

    @app.get('/api/materials/{material_id}/deletion-impact')
    def deletion_impact(material_id: str):
        if not store.material(material_id):
            raise HTTPException(404, 'Material not found.')
        return {'quizzes': [{'id': q['id'], 'title': json.loads(q['body'])['title']} for q in affected_quizzes(material_id)]}

    @app.delete("/api/materials/{material_id}")
    def delete_material(material_id: str):
        with mutation_lock:
            if not store.material(material_id):
                raise HTTPException(404, "Material not found.")
            cid = store.collection_for(material_id)
            if store.one("SELECT id FROM jobs WHERE status IN ('queued','running') AND (material_id=? OR (kind='quiz' AND json_extract(params,'$.collectionId')=?))", (material_id,cid)):
                raise HTTPException(409, "Cancel the dependent active job and wait for it to stop before deleting this material.")
            affected = affected_quizzes(material_id)
            with store.connect() as db:
                for q in affected:
                    for table in ('starred_questions', 'question_hints', 'quiz_sources', 'quiz_collections', 'quiz_removals', 'quizzes'):
                        db.execute(f"DELETE FROM {table} WHERE {'id' if table=='quizzes' else 'quiz_id'}=?", (q['id'],))
                    db.execute('DELETE FROM requests WHERE quiz_id=?', (q['id'],))
                db.execute('INSERT OR IGNORE INTO vector_cleanup SELECT id FROM chunks WHERE material_id=?', (material_id,))
                for table in ('chunks', 'sources', 'jobs', 'material_collections'):
                    db.execute(f'DELETE FROM {table} WHERE material_id=?', (material_id,))
                db.execute('DELETE FROM materials WHERE id=?', (material_id,))
            shutil.rmtree(store.root / "materials" / material_id, ignore_errors=True)
            engine.retriever.cleanup()
            return {"deleted": True, 'deletedQuizIds': [q['id'] for q in affected]}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        row = store.job(job_id)
        if not row:
            raise HTTPException(404, "Job not found.")
        result = {k: row[k] for k in ("id", "kind", "material_id", "status", "stage", "completed", "total", "result", "error")}
        practice = row['params'].get('mistakePractice')
        if practice:
            result['mistakePractice'] = {'parentQuizId': row['params'].get('parentQuizId'),
                'questions': [{k: q[k] for k in ('questionId', 'prompt', 'status')} for q in practice['questions']]}
        return result

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        row = store.job(job_id)
        if not row:
            raise HTTPException(404, "Job not found.")
        if row["status"] in ("queued", "running"):
            store.update_job(job_id, cancel=1, stage="Cancelling; waiting for the current request to finish")
        return {"accepted": True}

    @app.get('/api/jobs/{job_id}/request')
    def job_request(job_id: str):
        row = store.job(job_id)
        if not row or row['kind'] != 'quiz':
            raise HTTPException(404, 'Quiz request not found.')
        allowed = ('collectionId', 'parentQuizId', 'prompt', 'format', 'count', 'difficulty')
        return {'request': {k: row['params'][k] for k in allowed if k in row['params']}}

    @app.post("/api/jobs/{job_id}/retry", status_code=202)
    def retry_job(job_id: str):
        row = store.job(job_id)
        if not row:
            raise HTTPException(404, "Job not found.")
        if row["status"] not in ("failed", "interrupted", "cancelled"):
            raise HTTPException(409, "Only stopped or failed jobs can be retried.")
        with mutation_lock:
            row = store.job(job_id)
            if not row or not store.material(row['material_id']):
                raise HTTPException(404, 'The job or its material was deleted.')
            if row['kind'] == 'quiz':
                mids = row['params'].get('materialSnapshot', [])
                if not mids or not all(store.material(mid) for mid in mids):
                    raise HTTPException(400, 'A source from this request was deleted. Start a new quiz request.')
                # Refresh explicit model-change state without silently mixing vector models.
                if not all(engine.retriever.is_ready(mid) for mid in mids):
                    raise HTTPException(400, 'Index the original request materials with the current embedding model before retrying.')
            return dispatch(row["kind"], row["material_id"], row["params"])

    def create_quiz(params: QuizRequest, mistake_practice=None):
        with mutation_lock:
            if not os.getenv("OPENAI_API_KEY") and isinstance(engine.ai, AI):
                raise HTTPException(400, "Configure OPENAI_API_KEY in the local .env file and restart the app.")
            cid = params.collectionId or store.collection_for(params.materialId)
            require_collection(cid)
            if params.materialId and store.collection_for(params.materialId) != cid:
                raise HTTPException(400, 'The selected material does not belong to this collection.')
            parent = store.quiz(params.parentQuizId) if params.parentQuizId else None
            if params.parentQuizId and (not parent or parent['collectionId'] != cid):
                raise HTTPException(400, 'Choose a saved parent quiz from this collection.')
            inherited = (parent.get('request') or {}).get('resolved', {}) if parent else {}
            resolved = params.model_dump(exclude_none=True)
            resolved['collectionId'] = cid
            for field, default in [('format','mcq'), ('count',6), ('difficulty','intermediate')]:
                resolved[field] = resolved.get(field, inherited.get(field, default))
            if resolved['format'] not in ('mcq','flashcard','calculation','cheatsheet') or resolved['count'] not in (4,6,8,10):
                raise HTTPException(400, 'Choose a supported format and 4, 6, 8, or 10 items.')
            if resolved['difficulty'] not in ('beginner','intermediate','advanced') or not params.prompt.strip():
                raise HTTPException(400, 'Choose a difficulty and enter a topic request.')
            if parent:
                resolved['followupContext'] = {'request': inherited.get('retrievalQuery', inherited.get('prompt', parent['title'])),
                    'questions': [q['prompt'] for q in parent['questions']],
                    'sections': [s['heading'] for s in parent.get('sections', [])]}
            resolved['retrievalQuery'] = ((resolved['followupContext']['request'] + '\nFollow-up: ') if parent else '') + params.prompt
            mids = engine.retriever.snapshot(cid)
            if mistake_practice:
                wanted = mistake_practice['materialIds']
                if not set(wanted) <= set(mids):
                    raise HTTPException(400, 'Process and index the selected questions’ lecture materials before practicing mistakes.')
                mids = [mid for mid in mids if mid in wanted]
                resolved['mistakePractice'] = mistake_practice
                resolved['followupContext']['request'] = params.prompt
                resolved['retrievalQuery'] = '\n'.join(q['prompt'][:500] for q in mistake_practice['questions'])
            if not mids:
                raise HTTPException(400, 'Process and index at least one lecture in this collection before generating a quiz.')
            if store.one("SELECT id FROM jobs WHERE kind='quiz' AND status IN ('queued','running') AND json_extract(params,'$.collectionId')=?", (cid,)):
                raise HTTPException(409, 'This collection already has an active quiz job.')
            resolved['materialSnapshot'] = mids
            resolved['submitted'] = params.model_dump(exclude_none=True)
            return dispatch('quiz', mids[0], resolved)

    @app.post('/api/quizzes', status_code=202)
    def generate(params: QuizRequest):
        return create_quiz(params)

    register_mistake_routes(app, store, engine, create_quiz, QuizRequest, require_collection, mutation_lock)

    study_agent.routes(app, lambda params: generate(QuizRequest(**params)), retry_job, require_collection, mutation_lock)

    @app.get("/api/quizzes")
    def quizzes(collectionId: str | None = None, groupId: str | None = None):
        if groupId:
            if not CURRENT_USER.get():raise HTTPException(401, 'Sign in to continue.')
            groups.member(groupId)
        values = (collectionId,) if collectionId else ()
        where = ' WHERE NOT EXISTS (SELECT 1 FROM quiz_removals r WHERE r.quiz_id=q.id)'
        if collectionId:
            where += ' AND qc.collection_id=?'
        if auth_required:
            where += (' AND ' if where else ' WHERE ') + 'qc.collection_id IN (SELECT collection_id FROM collection_owners WHERE user_id=?)'
            values += (CURRENT_USER.get()['id'],)
        eligibility=',EXISTS(SELECT 1 FROM group_sets gs WHERE gs.group_id=? AND gs.original_quiz_id=q.id) AS already_shared' if groupId else ''
        rows = store.all('SELECT q.*,qc.collection_id,c.name AS source_title'+eligibility+' FROM quizzes q '
                         'JOIN quiz_collections qc ON qc.quiz_id=q.id JOIN collections c ON c.id=qc.collection_id'+where+' ORDER BY q.created DESC', ((groupId,)+values) if groupId else values)
        return {'quizzes': [{'id': r['id'], 'materialId': r['material_id'], 'collectionId': r['collection_id'],
                 'title': json.loads(r['body'])['title'], 'format': json.loads(r['body'])['format'],
                 'questionCount': len(json.loads(r['body'])['questions']),
                 'sectionCount': len(json.loads(r['body']).get('sections', [])),
                 'answeredCount': sum(bool(a.get('submitted') or (json.loads(r['body'])['format']=='flashcard'
                                      and (a.get('reviewed') or a.get('revealed'))))
                                      for a in json.loads(r['progress']).get('answers', {}).values()),
                 'sourceTitle': r['source_title'], 'created': r['created'],
                 'request': store.quiz_request(r['id']),
                 **({'alreadyShared': bool(r['already_shared'])} if groupId else {})} for r in rows]}

    @app.get("/api/quizzes/{quiz_id}")
    def quiz(quiz_id: str):
        result = store.quiz(quiz_id)
        if not result:
            raise HTTPException(404, "Quiz not found.")
        return result

    @app.patch('/api/quizzes/{quiz_id}')
    def rename_quiz(quiz_id: str, body: QuizName):
        title = body.title.strip()
        if not title:
            raise HTTPException(400, 'Enter a set name.')
        with mutation_lock, store.connect() as db:
            row = db.execute('SELECT body FROM quizzes WHERE id=? AND NOT EXISTS '
                             '(SELECT 1 FROM quiz_removals r WHERE r.quiz_id=quizzes.id)', (quiz_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Set no longer available.')
            content = json.loads(row['body'])
            content['title'] = title
            db.execute('UPDATE quizzes SET body=? WHERE id=?', (json.dumps(content), quiz_id))
        return store.quiz(quiz_id)

    def permanently_remove_quizzes(cid, selection):
        ids = list(dict.fromkeys(selection.quizIds))
        with mutation_lock, store.connect() as db:
            require_collection(cid)
            # Validate the whole selection before changing anything.
            for qid in ids:
                if not db.execute('SELECT q.id FROM quizzes q JOIN quiz_collections qc ON qc.quiz_id=q.id '
                                  'WHERE q.id=? AND qc.collection_id=?', (qid, cid)).fetchone():
                    raise HTTPException(404, 'A selected set is no longer available in this folder.')
            marks = ','.join('?' for _ in ids)
            if db.execute("SELECT id FROM jobs WHERE status IN ('queued','running') "
                          f"AND json_extract(params,'$.parentQuizId') IN ({marks})", ids).fetchone():
                raise HTTPException(409, 'A selected set is being used for generation. Wait or cancel that job first.')
            store.delete_quizzes(db, ids)
        return {'removedQuizIds': ids}

    @app.post('/api/collections/{cid}/quizzes/remove')
    def remove_quizzes(cid: str, body: QuizSelection):
        return permanently_remove_quizzes(cid, body)

    def require_flashcard(quiz_id, question_id):
        quiz = store.quiz(quiz_id)
        question = next((q for q in quiz['questions'] if q['id'] == question_id), None) if quiz else None
        if not question:
            raise HTTPException(404, 'Flashcard not found.')
        if question['type'] != 'flashcard':
            raise HTTPException(400, 'This action is available for flashcards.')
        return quiz, question

    @app.put('/api/quizzes/{quiz_id}/questions/{question_id}/star')
    def star_question(quiz_id: str, question_id: str, body: StarStatus):
        with mutation_lock:
            require_flashcard(quiz_id, question_id)
            if body.starred:
                store.execute('INSERT OR IGNORE INTO starred_questions VALUES(?,?,?)',
                              (quiz_id, question_id, time.time()))
            else:
                store.execute('DELETE FROM starred_questions WHERE quiz_id=? AND question_id=?',
                              (quiz_id, question_id))
            return {'starred': body.starred}

    @app.get('/api/collections/{cid}/question-bank')
    def question_bank(cid: str):
        require_collection(cid)
        rows = store.all('SELECT sq.quiz_id,sq.question_id,sq.created FROM starred_questions sq '
                         'JOIN quiz_collections qc ON qc.quiz_id=sq.quiz_id WHERE qc.collection_id=? '
                         'ORDER BY sq.created DESC', (cid,))
        questions = []
        for row in rows:
            quiz = store.quiz(row['quiz_id'])
            question = next((q for q in quiz['questions'] if q['id'] == row['question_id']), None) if quiz else None
            if question:
                questions.append({**question, 'quizTitle': quiz['title'], 'starredAt': row['created']})
        return {'questions': questions}

    @app.post('/api/quizzes/{quiz_id}/questions/{question_id}/hint')
    def flashcard_hint(quiz_id: str, question_id: str):
        with mutation_lock:
            _, question = require_flashcard(quiz_id, question_id)
            cached = store.one('SELECT hint FROM question_hints WHERE quiz_id=? AND question_id=?',
                               (quiz_id, question_id))
            if cached:
                return {'hint': cached['hint'], 'cached': True}
            sid = question['source'].get('id')
            row = store.one('SELECT body FROM sources WHERE id=?', (sid,))
            if not row:
                raise HTTPException(404, 'The lecture source is no longer available.')
            source = json.loads(row['body'])
        try:
            hint = ''
            for attempt in range(2):
                raw = engine.ai.hint(question, source, 'Avoid stating the answer. Give a reasoning cue.' if attempt else '')
                hint = raw.get('hint', '').strip()
                answer = normalize(question['answer'])
                if hint and len(hint) <= 140 and not re.search(r'(?<!\w)' + re.escape(answer) + r'(?!\w)', normalize(hint)):
                    break
            else:
                raise ValueError('A hint could not be created without revealing the answer. Try again.')
        except (ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(502, str(exc) if isinstance(exc, ValueError) else 'Hint unavailable. Try again.') from exc
        with mutation_lock:
            require_flashcard(quiz_id, question_id)
            store.execute('INSERT OR IGNORE INTO question_hints VALUES(?,?,?,?)',
                          (quiz_id, question_id, hint, time.time()))
            cached = store.one('SELECT hint FROM question_hints WHERE quiz_id=? AND question_id=?',
                               (quiz_id, question_id))
        return {'hint': cached['hint'], 'cached': False}

    @app.post('/api/cheatsheets/export')
    async def export_sheet(request: Request, format: str = 'html'):
        if format not in ('html', 'pdf'):
            raise HTTPException(400, 'Choose HTML or PDF.')
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 4*1024*1024:
                raise HTTPException(413, 'The guide is too large to export.')
        try:
            sheet = validate_document(json.loads(payload))
        except (ValueError, TypeError) as exc:
            raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else 'Invalid guide.') from exc
        try:
            html = await run_in_threadpool(render_html, sheet)
            content = await run_in_threadpool(render_pdf, html) if format == 'pdf' else html
        except ValueError as exc:
            raise HTTPException(503, str(exc)) from exc
        return Response(content, media_type='application/pdf' if format == 'pdf' else 'text/html',
            headers={'Content-Disposition': f'attachment; filename="lecture-lab-study-guide.{format}"'})

    @app.put("/api/quizzes/{quiz_id}/progress")
    async def progress(quiz_id: str, request: Request):
        quiz = store.quiz(quiz_id)
        if not quiz:
            raise HTTPException(404, "Quiz not found.")
        if quiz['format'] == 'cheatsheet':
            raise HTTPException(400, 'Cheat sheets do not use answer progress.')
        raw = await request.body()
        if len(raw) > 100000:
            raise HTTPException(413, "Practice progress is too large.")
        try:
            body = json.loads(raw)
            answers = body.get("answers", {})
            if not isinstance(answers, dict) or not set(answers) <= {q["id"] for q in quiz["questions"]}:
                raise ValueError()
            if not isinstance(body.get("index", 0), int) or not 0 <= body.get("index", 0) < len(quiz["questions"]):
                raise ValueError()
            if not all(isinstance(a, dict) for a in answers.values()):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, "Invalid practice progress.")
        store.execute("UPDATE quizzes SET progress=? WHERE id=?", (json.dumps(body), quiz_id))
        return {"saved": True}

    @app.get("/api/files/{material_id}/{file_id}")
    def original(material_id: str, file_id: str):
        row = store.material(material_id)
        file = next((f for f in row["files"] if f["id"] == file_id), None) if row else None
        if not file:
            raise HTTPException(404, "Source file not found.")
        path = store.root / "materials" / material_id / file["stored"]
        return FileResponse(path, media_type=mimetypes.guess_type(file["name"])[0] or "application/octet-stream")

    @app.get("/api/sources/{source_id}")
    def source(source_id: str):
        row = store.one("SELECT body FROM sources WHERE id=?", (source_id,))
        if not row:
            raise HTTPException(404, "Source reference not found.")
        source = json.loads(row["body"])
        source["fileUrl"] = f"/api/files/{source['materialId']}/{source['fileId']}" if source.get("fileId") else None
        source["frameUrl"] = f"/api/sources/{source_id}/frame" if source.get("framePath") else None
        source["previewUrl"] = f"/api/sources/{source_id}/preview" if source["kind"] == "pdf" else None
        source.pop("framePath", None)
        return source

    @app.get("/api/sources/{source_id}/preview")
    def pdf_preview(source_id: str):
        row = store.one("SELECT body FROM sources WHERE id=?", (source_id,))
        source = json.loads(row["body"]) if row else None
        material = store.material(source["materialId"]) if source else None
        file = next((f for f in material["files"] if f["id"] == source["fileId"]), None) if material else None
        if not source or source["kind"] != "pdf" or not file:
            raise HTTPException(404, "PDF source page not found.")
        with fitz.open(store.root / "materials" / source["materialId"] / file["stored"]) as pdf:
            page = pdf[source["page"]-1]
            scale = min(2, 1600/max(page.rect.width, page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            return Response(pix.tobytes("png"), media_type="image/png")

    @app.get("/api/sources/{source_id}/frame")
    def frame(source_id: str):
        row = store.one("SELECT body FROM sources WHERE id=?", (source_id,))
        source = json.loads(row["body"]) if row else None
        if not source or not source.get("framePath"):
            raise HTTPException(404, "Sampled frame not found.")
        path = store.root / "materials" / source["materialId"] / source["framePath"]
        return FileResponse(path, media_type="image/png")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8765")))
