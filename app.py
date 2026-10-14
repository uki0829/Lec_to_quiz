"""Local-only Lecture Lab server. Run with .venv/bin/python app.py."""
import contextlib
import json
import mimetypes
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
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ai import AI
from processing import Engine, duration, ffmpeg_path
from storage import Store, uid

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


class CollectionName(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def create_app(data_dir=None, ai=None, run_jobs=True):
    store = Store(data_dir or (ROOT / os.getenv("LECTURE_LAB_DATA_DIR", "data")))
    engine = Engine(store, ai or AI())
    mutation_lock = threading.RLock()

    @contextlib.asynccontextmanager
    async def lifespan(app):
        store.recover_interrupted_jobs()
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
                "maxDurationMinutes": 30, "embeddingModel": engine.retriever.model}

    def require_collection(cid):
        row = store.one('SELECT * FROM collections WHERE id=?', (cid,))
        if not row:
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
        rows = store.all('SELECT * FROM collections ORDER BY created DESC')
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
        require_collection(cid)
        if not body.name.strip():
            raise HTTPException(400, 'Enter a collection name.')
        store.execute('UPDATE collections SET name=? WHERE id=?', (body.name.strip(), cid))
        return require_collection(cid)

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
        result = [material_brief(r) for r in store.all('SELECT * FROM materials ORDER BY created DESC')]
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
                    for table in ('quiz_sources', 'quiz_collections', 'quizzes'):
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
        return {k: row[k] for k in ("id", "kind", "material_id", "status", "stage", "completed", "total", "result", "error")}

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
            if row['kind'] == 'quiz':
                mids = row['params'].get('materialSnapshot', [])
                if not mids or not all(store.material(mid) for mid in mids):
                    raise HTTPException(400, 'A source from this request was deleted. Start a new quiz request.')
                # Refresh explicit model-change state without silently mixing vector models.
                if not all(engine.retriever.is_ready(mid) for mid in mids):
                    raise HTTPException(400, 'Index the original request materials with the current embedding model before retrying.')
            return dispatch(row["kind"], row["material_id"], row["params"])

    @app.post("/api/quizzes", status_code=202)
    def generate(params: QuizRequest):
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
            if not mids:
                raise HTTPException(400, 'Process and index at least one lecture in this collection before generating a quiz.')
            if store.one("SELECT id FROM jobs WHERE kind='quiz' AND status IN ('queued','running') AND json_extract(params,'$.collectionId')=?", (cid,)):
                raise HTTPException(409, 'This collection already has an active quiz job.')
            resolved['materialSnapshot'] = mids
            resolved['submitted'] = params.model_dump(exclude_none=True)
            return dispatch('quiz', mids[0], resolved)

    @app.get("/api/quizzes")
    def quizzes(collectionId: str | None = None):
        values = (collectionId,) if collectionId else ()
        where = ' WHERE qc.collection_id=?' if collectionId else ''
        rows = store.all('SELECT q.*,qc.collection_id,c.name AS source_title FROM quizzes q '
                         'JOIN quiz_collections qc ON qc.quiz_id=q.id JOIN collections c ON c.id=qc.collection_id'+where+' ORDER BY q.created DESC', values)
        return {'quizzes': [{'id': r['id'], 'materialId': r['material_id'], 'collectionId': r['collection_id'],
                 'title': json.loads(r['body'])['title'], 'format': json.loads(r['body'])['format'],
                 'questionCount': len(json.loads(r['body'])['questions']),
                 'sectionCount': len(json.loads(r['body']).get('sections', [])),
                 'answeredCount': sum(bool(a.get('submitted')) for a in json.loads(r['progress']).get('answers', {}).values()),
                 'sourceTitle': r['source_title'], 'created': r['created'],
                 'request': store.quiz_request(r['id'])} for r in rows]}

    @app.get("/api/quizzes/{quiz_id}")
    def quiz(quiz_id: str):
        result = store.quiz(quiz_id)
        if not result:
            raise HTTPException(404, "Quiz not found.")
        return result

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
