"""Prepare genuine saved demo results through the running local API.

Requires the server and an OpenAI key. Uses normal API billing. The optional
--all-media check also processes authored image, synthesized audio, and video.
"""
import argparse
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--all-media", action="store_true")
args = parser.parse_args()
client = httpx.Client(base_url="http://127.0.0.1:8765", timeout=180)


def request(method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def wait(job_id):
    last = None
    for _ in range(450):
        job = request("GET", "/api/jobs/"+job_id)
        if job["stage"] != last:
            print(job["stage"], flush=True)
            last = job["stage"]
        if job["status"] == "completed":
            return job["result"]
        if job["status"] in ("failed", "cancelled", "interrupted"):
            raise RuntimeError(job["error"] or job["status"])
        time.sleep(2)
    request("POST", "/api/jobs/"+job_id+"/cancel")
    raise RuntimeError("Demo preparation timed out; cancellation requested.")


if not request("GET", "/api/config")["connected"]:
    raise SystemExit("Configure the local OpenAI key and restart first.")

files = ["gradient-descent.pdf"]
if args.all_media:
    files += ["gradient-descent.png", "gradient-descent.wav", "gradient-descent.mp4"]
for name in files:
    print("Processing authored demo source: "+name, flush=True)
    existing = next((m for m in request("GET", "/api/materials")["materials"]
                     if m["title"] == name and m["status"] == "ready"), None)
    if existing:
        material_id = existing["id"]
        print("Reusing processed sample material", flush=True)
    else:
        with (ROOT/"samples"/name).open("rb") as source:
            job = request("POST", "/api/materials", files=[("files", (name, source))])
        result = wait(job["jobId"])
        material_id = result["materialId"]
    formats = ["mcq", "flashcard", "calculation"] if name.endswith(".pdf") else ["mcq"]
    for format_ in formats:
        saved = [request("GET", "/api/quizzes/"+q["id"]) for q in request("GET", "/api/quizzes")["quizzes"]
                 if q["materialId"] == material_id]
        if any(q["format"] == format_ for q in saved):
            print("Reusing saved "+format_+" quiz", flush=True)
            continue
        prompt = ("Practice gradient descent, the update rule, learning rate, and numerical examples from this lecture."
                  if not name.endswith(".png") else
                  "Practice the definition and update rule of gradient descent, the role of the learning rate, and stationary points. Use only this slide.")
        job = request("POST", "/api/quizzes", json={"materialId": material_id,
            "prompt": prompt,
            "format": format_, "count": 6 if name.endswith(".pdf") else 4, "difficulty": "beginner"})
        result = wait(job["jobId"])
        if result.get("status") != "ready":
            raise RuntimeError(result.get("message", "Quiz was not ready"))
        quiz = request("GET", "/api/quizzes/"+result["quizId"])
        print(name+" / "+format_+": "+str(len(quiz["questions"]))+" real generated questions saved", flush=True)
print("Saved live demo preparation completed.", flush=True)
