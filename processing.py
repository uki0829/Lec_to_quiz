"""Bounded local media preparation and resumable background jobs."""
import concurrent.futures
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pymupdf as fitz
import imageio_ffmpeg

from schemas import validate_quiz, normalize
from retrieval import Retriever


class Cancelled(Exception):
    pass


def ffmpeg_path():
    return os.getenv("FFMPEG_PATH") or shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()


def stamp(seconds):
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    return f"{minutes:02d}:{seconds:02d}"


def run_media(args, check=lambda: None):
    proc = subprocess.Popen([ffmpeg_path(), "-nostdin", *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while True:
            check()
            try:
                stdout, stderr = proc.communicate(timeout=0.5)
                return proc.returncode, stdout, stderr.decode(errors="replace")
            except subprocess.TimeoutExpired:
                continue
    except BaseException:
        proc.terminate()
        try:
            proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        raise


def duration(path, check=lambda: None):
    _, _, error = run_media(["-hide_banner", "-i", str(path)], check)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", error)
    if not match:
        raise ValueError("This recording could not be read. Use a supported, uncorrupted audio/video file.")
    hours, minutes, seconds = map(float, match.groups())
    return hours * 3600 + minutes * 60 + seconds


class Engine:
    def __init__(self, store, ai):
        self.store, self.ai = store, ai
        self.retriever = Retriever(store, ai)
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="lecture-job")

    def submit(self, job_id):
        self.pool.submit(self.run, job_id)

    def check(self, job_id):
        job = self.store.job(job_id)
        if not job or job["cancel"]:
            raise Cancelled()

    def stage(self, job_id, label, done=0, total=0):
        self.check(job_id)
        self.store.update_job(job_id, stage=label, completed=done, total=total)

    def run(self, job_id):
        job = self.store.job(job_id)
        if not job:
            return
        try:
            self.check(job_id)
            self.store.update_job(job_id, status="running", error=None)
            if job["kind"] == "material":
                self.process_material(job_id, job["material_id"])
                self.retriever.index(job['material_id'], lambda: self.check(job_id), lambda *a: self.stage(job_id, *a))
                self.store.execute("UPDATE materials SET status='ready' WHERE id=?", (job["material_id"],))
                result = {"materialId": job["material_id"]}
            elif job['kind'] == 'index':
                self.retriever.index(job['material_id'], lambda: self.check(job_id), lambda *a: self.stage(job_id, *a))
                result = {'materialId': job['material_id']}
            else:
                result = self.process_quiz(job_id, job["material_id"], job["params"])
            self.check(job_id)
            self.store.update_job(job_id, status="completed", stage="Ready", result=result)
        except Cancelled:
            self.store.update_job(job_id, status="cancelled", stage="Cancelled")
            if job["kind"] == "material":
                self.store.execute("UPDATE materials SET status='cancelled' WHERE id=?", (job["material_id"],))
        except Exception as exc:
            error = str(exc) if isinstance(exc, ValueError) else "Processing failed. Check the file and retry. Completed extraction is retained."
            self.store.update_job(job_id, status="failed", stage="Needs attention", error=error)
            if job["kind"] == "material":
                self.store.execute("UPDATE materials SET status='failed' WHERE id=?", (job["material_id"],))

    def process_material(self, job_id, material_id):
        material = self.store.material(material_id)
        if not material:
            raise Cancelled()
        self.store.execute("UPDATE materials SET status='processing' WHERE id=?", (material_id,))
        if material["notes"]:
            text = material["notes"]
            # Split large notes into useful bounded sections without an AI extraction call.
            for i in range(0, len(text), 8000):
                self.check(job_id)
                key = "notes" if i == 0 else f"notes-{i:06}"
                if self.store.has_unit(material_id, key):
                    continue
                self.store.save_source(material_id, key, {
                    "name": "Pasted lecture notes", "kind": "text", "locator": f"Notes section {i//8000+1}",
                    "text": text[i:i+8000], "summary": text[i:i+8000], "uncertainty": "", "fileId": None})
        for number, file in enumerate(material["files"]):
            self.stage(job_id, f"Reading {file['name']}", number, len(material["files"]))
            path = self.store.root / "materials" / material_id / file["stored"]
            kind = file["kind"]
            if kind == "pdf":
                self.process_pdf(job_id, material_id, file, path)
            elif kind == "image":
                self.process_image(job_id, material_id, file, path)
            elif kind == "text":
                key = file["id"] + ":text"
                text = path.read_text(encoding="utf-8")
                for i in range(0, len(text), 8000):
                    self.check(job_id)
                    unit = key if i == 0 else key + f"-{i:06}"
                    if not self.store.has_unit(material_id, unit):
                        self.store.save_source(material_id, unit, {
                            "name": file["name"], "kind": "text", "locator": f"Text section {i//8000+1}",
                            "text": text[i:i+8000], "summary": text[i:i+8000], "uncertainty": "", "fileId": file["id"]})
            else:
                self.process_recording(job_id, material_id, file, path)
        if not any(s["text"].strip() for s in self.store.sources(material_id)):
            raise ValueError("No readable lecture content was found. Add a clearer source or paste notes.")

    def extract_batch(self, job_id, material_id, batch):
        if not batch:
            return
        self.check(job_id)
        result = self.ai.extract(batch)
        self.check(job_id)
        mapping = {u["key"]: u for u in batch}
        if len(result) != len(batch) or {r["key"] for r in result} != set(mapping):
            raise ValueError("The model did not extract every page. Retry to continue from completed pages.")
        for record in result:
            unit = mapping[record["key"]]
            self.store.save_source(material_id, unit["key"], {
                **unit["metadata"], "text": record["text"], "summary": record["summary"],
                "uncertainty": record["uncertainty"]})

    def process_pdf(self, job_id, material_id, file, path):
        try:
            with fitz.open(path) as pdf:
                if pdf.needs_pass:
                    raise ValueError("Unlock the PDF before uploading it.")
                batch = []
                for i, page in enumerate(pdf):
                    self.stage(job_id, f"Reading PDF pages: {file['name']}", i, len(pdf))
                    key = file["id"] + f":page:{i+1:04}"
                    if self.store.has_unit(material_id, key):
                        continue
                    scale = min(2, 1600/max(page.rect.width, page.rect.height))
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    batch.append({"key": key, "text": page.get_text()[:20000], "image": pix.tobytes("png"),
                                  "metadata": {"name": file["name"], "kind": "pdf", "page": i+1,
                                               "locator": f"Page {i+1}", "fileId": file["id"]}})
                    if len(batch) == 5:
                        self.extract_batch(job_id, material_id, batch)
                        batch = []
                self.extract_batch(job_id, material_id, batch)
        except fitz.FileDataError as exc:
            raise ValueError("The PDF is damaged or unreadable.") from exc

    def process_image(self, job_id, material_id, file, path):
        key = file["id"] + ":image"
        if not self.store.has_unit(material_id, key):
            from PIL import Image
            import io
            with Image.open(path) as image:
                image.thumbnail((2000, 2000))
                buf = io.BytesIO()
                image.convert("RGB").save(buf, "PNG")
            self.extract_batch(job_id, material_id, [{"key": key, "image": buf.getvalue(), "metadata": {
                "name": file["name"], "kind": "image", "locator": "Uploaded image", "fileId": file["id"]}}])

    def process_recording(self, job_id, material_id, file, path):
        check = lambda: self.check(job_id)
        length = duration(path, check)
        if length <= 0 or length > 1800.1:
            raise ValueError("Recordings must be no longer than 30 minutes. Trim the file and upload again.")
        work = path.parent / (file["id"] + "-processed")
        work.mkdir(exist_ok=True)
        for chunk in range(math.ceil(length / 300)):
            start = chunk * 300
            key = file["id"] + f":audio:{chunk:04}"
            if self.store.has_unit(material_id, key):
                continue
            self.stage(job_id, f"Transcribing {file['name']}", chunk, math.ceil(length / 300))
            audio = work / f"audio-{chunk:04}.wav"
            code, _, _ = run_media(["-y", "-v", "error", "-ss", str(start), "-i", str(path),
                                   "-t", "300", "-vn", "-ac", "1", "-ar", "16000", str(audio)], check)
            if code or not audio.exists():
                raise ValueError("The recording has no readable audio track. Upload slides or a recording with sound.")
            if audio.stat().st_size > 24 * 1024 * 1024:
                raise ValueError("An audio chunk exceeds the transcription upload limit.")
            transcript_cache = work / f"transcript-{chunk:04}.json"
            if transcript_cache.exists():
                result = json.loads(transcript_cache.read_text())
            else:
                result = self.ai.transcribe(audio)
                transcript_cache.write_text(json.dumps(result))
            check()
            segments = [{"start": start + s["start"], "end": min(length, start + s["end"]), "text": s["text"]}
                        for s in result.get("segments", [])]
            text = result.get("text", "").strip()
            outline = self.ai.extract([{"key": key, "text": text}])[0] if text else {"summary": ""}
            check()
            self.store.save_source(material_id, key, {
                "name": file["name"], "kind": file["kind"], "locator": stamp(start) + "–" + stamp(min(length, start+300)),
                "start": start, "end": min(length, start+300), "text": text,
                "summary": outline["summary"], "uncertainty": "Transcript may contain recognition errors.",
                "fileId": file["id"], "segments": segments})
            audio.unlink(missing_ok=True)
        if file["kind"] != "video":
            return
        batch = []
        total = math.ceil(length / 60)
        for minute in range(total):
            start = minute * 60
            key = file["id"] + f":visual:{minute:04}"
            if self.store.has_unit(material_id, key):
                continue
            self.stage(job_id, f"Reading sampled slides: {file['name']}", minute, total)
            frame = work / f"frame-{minute:04}.png"
            code, _, _ = run_media(["-y", "-v", "error", "-ss", str(start), "-i", str(path),
                                   "-frames:v", "1", "-vf", "scale=1600:-2", str(frame)], check)
            if code or not frame.exists():
                raise ValueError("Could not extract a video frame. Check that the video has a readable picture track.")
            batch.append({"key": key, "image": frame.read_bytes(), "metadata": {
                "name": file["name"], "kind": "video", "locator": "Slide frame at " + stamp(start),
                "start": start, "end": start, "fileId": file["id"],
                "framePath": str(frame.relative_to(path.parent))}})
            if len(batch) == 5:
                self.extract_batch(job_id, material_id, batch)
                batch = []
        self.extract_batch(job_id, material_id, batch)

    def process_quiz(self, job_id, material_id, params):
        self.stage(job_id, "Searching your study collection", 0, 4)
        cid = params.get('collectionId') or self.store.collection_for(material_id)
        mids = params.get('materialSnapshot') or [material_id]
        query = params['prompt']
        if params.get('followupContext'):
            query = params['followupContext']['request'] + '\nFollow-up: ' + query
        sources = self.retriever.search(cid, mids, query, lambda: self.check(job_id))
        self.store.execute('UPDATE requests SET snapshot=? WHERE job_id=?',
                           (json.dumps([{'chunkId': s['id'], 'sourceId': s['originalSourceId'], 'materialId': s['materialId']} for s in sources]), job_id))
        if not sources:
            return {'status': 'insufficient_source', 'message': 'No indexed lecture content is available. Add or index materials first.'}
        self.stage(job_id, "Selecting relevant lecture sections", 1, 4)
        selection = self.ai.select(query, sources)
        self.check(job_id)
        if selection["status"] != "ready":
            return {"status": selection["status"], "message": selection["message"]}
        selected_ids = selection["sourceIds"]
        mapping = {s["id"]: s for s in sources}
        if not selected_ids or len(selected_ids) > 12 or not set(selected_ids) <= set(mapping):
            raise ValueError("The model selected invalid source references. Narrow the topic and retry.")
        chosen = [mapping[s] for s in dict.fromkeys(selected_ids)]
        self.stage(job_id, "Building your cheat sheet" if params['format'] == 'cheatsheet' else "Building your quiz", 2, 4)
        feedback = ""
        for attempt in range(2):
            self.check(job_id)
            raw = self.ai.generate(params, chosen, feedback)
            self.check(job_id)
            self.stage(job_id, "Checking source references" if params['format'] == 'cheatsheet' else "Checking answers and source references", 3, 4)
            try:
                quiz = validate_quiz(raw, chosen, params["format"], params["count"])
                previous = {normalize(q) for q in params.get('followupContext', {}).get('questions', [])}
                if any(normalize(q['prompt']) in previous for q in quiz.get('questions', [])):
                    raise ValueError('The follow-up repeats an earlier question. Generate different questions grounded in the same lecture evidence.')
                break
            except ValueError as exc:
                if attempt:
                    raise ValueError("The generated study set failed validation: " + str(exc)) from exc
                feedback = str(exc) + ". Repair the result while remaining grounded in the supplied sources."
        if quiz["status"] != "ready":
            return {"status": quiz["status"], "message": quiz["message"]}
        self.check(job_id)
        quiz = self.store.add_quiz(material_id, {**quiz, "format": params["format"]})
        with self.store.connect() as db:
            db.execute('UPDATE requests SET quiz_id=? WHERE job_id=?', (quiz['id'], job_id))
            items = quiz.get('sections', []) if params['format'] == 'cheatsheet' else quiz['questions']
            db.executemany('INSERT OR IGNORE INTO quiz_sources VALUES(?,?)', [(quiz['id'], q['source']['id']) for q in items])
        return {"status": "ready", "quizId": quiz["id"]}
