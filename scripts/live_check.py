"""Opt-in live OpenAI smoke check. Run only after configuring your local key.

Usage: .venv/bin/python scripts/live_check.py [path/to/lecture.pdf]
This sends the selected source to OpenAI and incurs normal API usage.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import create_app

if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit("Configure OPENAI_API_KEY in .env first. No live request was made.")

path = Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/"samples/gradient-descent.pdf"
with tempfile.TemporaryDirectory(prefix="lecture-lab-live-") as tmp:
    app=create_app(tmp, run_jobs=False)
    with TestClient(app) as client:
        with path.open("rb") as f:
            upload=client.post("/api/materials", files=[("files",(path.name,f))])
        upload.raise_for_status()
        material=upload.json()
        app.state.engine.run(material["jobId"])
        job=app.state.store.job(material["jobId"])
        if job["status"]!="completed":
            raise SystemExit("Material processing failed: "+str(job["error"]))
        for format_ in ("mcq","flashcard","calculation"):
            response=client.post("/api/quizzes",json={"materialId":material["materialId"],
                "prompt":"Practice gradient descent, its update rule, learning rate, and numerical examples.",
                "format":format_,"count":4,"difficulty":"beginner"})
            response.raise_for_status()
            app.state.engine.run(response.json()["jobId"])
            job=app.state.store.job(response.json()["jobId"])
            if job["status"]!="completed" or job["result"].get("status")!="ready":
                raise SystemExit(format_+" failed: "+str(job["error"] or job["result"]))
            print(format_+": real generation and validation succeeded")
print("Live source and quiz smoke check passed. Inspect explanations separately for quality.")
