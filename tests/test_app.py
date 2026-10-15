import copy
import io
import json
import math
import os
import wave

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import create_app
from processing import duration, run_media
from schemas import arithmetic_value, validate_quiz
from storage import Store

NOTES = "Gradient descent uses w_new = w - eta * gradient. For w=3, eta=0.1, gradient=6, the new w is 2.4."


class FakeAI:
    model = "fixture-model"
    audio_model = "fixture-transcription"

    def __init__(self):
        self.extractions = 0
        self.transcriptions = []
        self.fail_extract = False
        self.fail_generate = False
        self.absent = False
        self.generate_calls = 0

    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def extract(self, units):
        self.extractions += len(units)
        if self.fail_extract:
            raise ValueError("Fixture provider is temporarily unavailable")
        return [{"key": u["key"], "text": u.get("text") or NOTES,
                 "summary": "Gradient descent and its update rule", "uncertainty": ""} for u in units]

    def transcribe(self, path, context=""):
        self.transcriptions.append(os.path.getsize(path))
        return {"text": NOTES, "segments": [{"start": 1, "end": 3, "text": NOTES}]}

    def select(self, prompt, sources):
        if self.absent:
            return {"status": "insufficient_source", "message": "This topic is absent.", "sourceIds": []}
        return {"status": "ready", "message": "", "sourceIds": [sources[0]["id"]]}

    def generate(self, params, sources, validation_feedback=""):
        self.generate_calls += 1
        if self.fail_generate:
            raise ValueError("Fixture quota exhausted")
        q = {"id": "q", "type": params["format"], "prompt": "Calculate the update from 3 with eta=0.1 and gradient=6.",
             "answer": "2.4", "explanation": "Subtract the learning rate times the gradient.",
             "steps": ["3 - 0.1 * 6 = 2.4"], "sourceId": sources[0]["id"], "quote": sources[0]["text"],
             "options": [], "correctIndex": None, "numericAnswer": None, "tolerance": None, "arithmetic": None}
        if params["format"] == "mcq":
            q.update(options=["2.4", "3.6", "0.6", "2.9"], correctIndex=0)
        elif params["format"] == "calculation":
            q.update(prompt=(r"\[w^{\mathrm{new}} = w - \eta g\]"
                             "\n" + r"\[w=3,\quad \eta=0.1,\quad g=6\]"
                             "\nCalculate the updated parameter."),
                     numericAnswer=2.4, tolerance=0.001, arithmetic="3 - 0.1 * 6",
                     problemEquation=r'w^{\mathrm{new}} = w - \eta g')
        questions = [{**copy.deepcopy(q), "id": "q" + str(i)} for i in range(params["count"])]
        return {"status": "ready", "message": "", "title": "Gradient descent", "description": "Fixture quiz", "questions": questions}


@pytest.fixture
def setup(tmp_path):
    ai = FakeAI()
    app = create_app(tmp_path,auth_required=False, ai=ai, run_jobs=False)
    with TestClient(app) as client:
        yield client, app.state.store, app.state.engine, ai


def complete(client, engine, response):
    assert response.status_code == 202, response.text
    result = response.json()
    engine.run(result["jobId"])
    job = client.get("/api/jobs/" + result["jobId"]).json()
    assert job["status"] == "completed", job
    return result, job


def pdf_bytes(pages=1):
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page().insert_text((30, 60), NOTES, fontsize=9)
    return doc.tobytes()


def prepared_notes(client, engine):
    result, _ = complete(client, engine, client.post("/api/materials", data={"notes": NOTES}))
    return result["materialId"]


def generate(client, engine, material_id, format_="mcq"):
    _, job = complete(client, engine, client.post("/api/quizzes", json={"materialId": material_id,
        "prompt": "Practice gradient descent", "format": format_, "count": 6, "difficulty": "beginner"}))
    return client.get("/api/quizzes/" + job["result"]["quizId"]).json()


@pytest.mark.parametrize("format_", ["mcq", "flashcard", "calculation"])
def test_pdf_to_quiz_and_source(setup, format_):
    client, store, engine, ai = setup
    material, _ = complete(client, engine, client.post("/api/materials", files=[("files", ("lecture.pdf", pdf_bytes(), "application/pdf"))]))
    quiz = generate(client, engine, material["materialId"], format_)
    assert len(quiz["questions"]) == 6
    question = quiz["questions"][0]
    source = client.get(question["source"]["url"]).json()
    assert source["page"] == 1
    assert source["name"] == "lecture.pdf"
    assert client.get(source["previewUrl"]).content.startswith(b"\x89PNG")
    assert client.get(source["fileUrl"]).content.startswith(b"%PDF")
    assert ai.extractions == 1


def test_image_extraction(setup):
    client, store, engine, ai = setup
    buf = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buf, "PNG")
    result, _ = complete(client, engine, client.post("/api/materials", files=[("files", ("slide.png", buf.getvalue(), "image/png"))]))
    quiz = generate(client, engine, result["materialId"])
    source = client.get(quiz["questions"][0]["source"]["url"]).json()
    assert source["kind"] == "image"
    assert client.get(source["fileUrl"]).status_code == 200


def test_saved_progress_and_deletion(setup):
    client, store, engine, ai = setup
    mid = prepared_notes(client, engine)
    quiz = generate(client, engine, mid)
    progress = {"index": 1, "answers": {"q0": {"selected": 0, "submitted": True, "correct": True}}}
    assert client.put("/api/quizzes/"+quiz["id"]+"/progress", json=progress).status_code == 200
    assert client.get("/api/quizzes/"+quiz["id"]).json()["progress"] == progress
    # Reviewed cards remain reviewed after flipping back, without claiming recall.
    reviewed = {"index": 0, "answers": {"q0": {"reviewed": True, "revealed": False}}, "review": True}
    assert client.put("/api/quizzes/"+quiz["id"]+"/progress", json=reviewed).status_code == 200
    assert client.get("/api/quizzes/"+quiz["id"]).json()["progress"] == reviewed
    restart = {"index": 0, "answers": {}, "review": False}
    assert client.put("/api/quizzes/"+quiz["id"]+"/progress", json=restart).status_code == 200
    restored = client.get("/api/quizzes/"+quiz["id"]).json()
    assert restored["id"] == quiz["id"]
    assert restored["progress"] == restart
    assert restored["questions"] == quiz["questions"]
    assert client.delete("/api/materials/"+mid).json()["deleted"]
    assert client.get("/api/quizzes/"+quiz["id"]).status_code == 404
    assert not store.sources(mid)


def test_missing_topic_preserves_quiz(setup):
    client, store, engine, ai = setup
    mid = prepared_notes(client, engine)
    quiz = generate(client, engine, mid)
    ai.absent = True
    _, job = complete(client, engine, client.post("/api/quizzes", json={"materialId": mid,
        "prompt": "Explain quantum mechanics", "format": "mcq", "count": 6, "difficulty": "beginner"}))
    assert job["result"]["status"] == "insufficient_source"
    assert client.get("/api/quizzes/"+quiz["id"]).status_code == 200


def test_provider_error_and_retry_reuses_pdf_pages(setup):
    client, store, engine, ai = setup
    upload = client.post("/api/materials", files=[("files", ("slides.pdf", pdf_bytes(6), "application/pdf"))]).json()
    original = ai.extract

    def fail_second(units):
        if ai.extractions:
            raise ValueError("Temporary failure")
        return original(units)

    ai.extract = fail_second
    engine.run(upload["jobId"])
    assert store.job(upload["jobId"])["status"] == "failed"
    assert len(store.sources(upload["materialId"])) == 5
    ai.extract = original
    complete(client, engine, client.post("/api/jobs/"+upload["jobId"]+"/retry"))
    assert ai.extractions == 6


def test_cancellation_and_active_delete(setup):
    client, store, engine, ai = setup
    upload = client.post("/api/materials", data={"notes": NOTES}).json()
    assert client.delete("/api/materials/"+upload["materialId"]).status_code == 409
    assert client.post("/api/jobs/"+upload["jobId"]+"/cancel").status_code == 200
    engine.run(upload["jobId"])
    assert store.job(upload["jobId"])["status"] == "cancelled"
    assert client.delete("/api/materials/"+upload["materialId"]).status_code == 200


def test_restart_marks_jobs_interrupted(tmp_path):
    s = Store(tmp_path)
    s.add_material("m", [], NOTES)
    jid = s.add_job("material", "m")
    app = create_app(tmp_path,auth_required=False, ai=FakeAI(), run_jobs=False)
    with TestClient(app):
        assert app.state.store.job(jid)["status"] == "interrupted"


@pytest.mark.parametrize("files", [
    [("files", ("bad.pdf", b"not a PDF", "application/pdf"))],
    [("files", ("empty.png", b"", "image/png"))],
    [("files", ("x.exe", b"not allowed", "application/octet-stream"))],
    [("files", (f"{i}.txt", b"notes", "text/plain")) for i in range(5)],
])
def test_invalid_uploads(setup, files):
    client, *_ = setup
    assert client.post("/api/materials", files=files).status_code == 400


def test_origin_and_host_boundary(setup):
    client, *_ = setup
    assert client.post("/api/materials", data={"notes": NOTES}, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.get("/api/config", headers={"Host": "untrusted.example"}).status_code == 400


def test_arithmetic_validation():
    assert arithmetic_value("3 - 0.1 * 6") == pytest.approx(2.4)
    for expression in ["__import__('os').system('x')", "w - 1", "2**1000", "[1][0]", "1/0", "float('nan')"]:
        with pytest.raises((ValueError, SyntaxError)):
            arithmetic_value(expression)


def test_generated_reference_and_answer_validation():
    ai = FakeAI()
    source = {"id": "s", "text": NOTES, "name": "notes", "locator": "Section 1", "kind": "text"}
    raw = ai.generate({"format": "calculation", "count": 1}, [source])
    assert validate_quiz(raw, [source], "calculation", 1)["questions"][0]["numericAnswer"] == 2.4
    raw["questions"][0]["numericAnswer"] = 3.6
    with pytest.raises(ValueError, match="arithmetic"):
        validate_quiz(raw, [source], "calculation", 1)
    raw = ai.generate({"format": "mcq", "count": 1}, [source])
    raw["questions"][0]["sourceId"] = "invented"
    with pytest.raises(ValueError, match="reference"):
        validate_quiz(raw, [source], "mcq", 1)
    raw["questions"][0]["sourceId"] = "s"
    raw["questions"][0]["quote"] = "invented quotation"
    with pytest.raises(ValueError, match="excerpt"):
        validate_quiz(raw, [source], "mcq", 1)


def test_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = create_app(tmp_path,auth_required=False, run_jobs=False)
    with TestClient(app) as client:
        upload = client.post('/api/materials', data={'notes': NOTES}).json()
        app.state.engine.run(upload['jobId'])
        mid = upload['materialId']
        assert app.state.store.job(upload['jobId'])['status'] == 'failed'
        assert 'OpenAI' in app.state.store.job(upload['jobId'])['error']
        response = client.post("/api/quizzes", json={"materialId": mid, "prompt": "gradient descent",
            "format": "mcq", "count": 6, "difficulty": "beginner"})
        assert response.status_code == 400
        assert "OPENAI_API_KEY" in response.json()["error"]
        assert not client.get("/api/config").json()["connected"]


@pytest.mark.parametrize("kind", ["audio", "video"])
def test_real_30_minute_media_chunking_with_fixture_ai(setup, tmp_path, kind):
    client, store, engine, ai = setup
    path = tmp_path / ("lecture.wav" if kind == "audio" else "lecture.mp4")
    if kind == "audio":
        args = ["-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "1800", str(path)]
    else:
        args = ["-f", "lavfi", "-i", "color=c=white:s=160x90:r=1", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                "-t", "1800", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(path)]
    assert run_media(["-y", "-v", "error", *args])[0] == 0
    assert duration(path) == pytest.approx(1800, abs=.1)
    with path.open("rb") as f:
        upload, _ = complete(client, engine, client.post("/api/materials", files=[("files", (path.name, f, "audio/wav" if kind == "audio" else "video/mp4"))]))
    assert len(ai.transcriptions) == 6
    assert all(0 < size < 25*1024**2 for size in ai.transcriptions)
    sources = store.sources(upload["materialId"])
    audio_sources = [s for s in sources if "segments" in s]
    assert audio_sources[-1]["segments"][0]["start"] == 1501
    if kind == "video":
        frames = [s for s in sources if "framePath" in s]
        assert len(frames) == 30
        assert max(s["start"] for s in frames) == 1740
        response = client.get("/api/sources/"+frames[-1]["id"])
        assert client.get(response.json()["frameUrl"]).status_code == 200
    quiz = generate(client, engine, upload["materialId"])
    cited = quiz['questions'][0]['source']
    original = client.get(cited['url']).json()
    assert cited['start'] == original['start']
    assert 0 <= cited['start'] < 1800


def test_study_page_routes_serve_shell_without_set_data(setup):
    client, store, engine, ai = setup
    for path in ('/study/local', '/study/quiz/not-a-real-set', '/study/shared/not-a-real-share'):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/html')
        assert '/static/practice.js' in response.text
        assert 'not-a-real-set' not in response.text
    assert client.get('/api/quizzes/not-a-real-set').status_code == 404
