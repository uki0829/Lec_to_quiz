"""Opt-in real PDF/AI checks for three authored academic-subject fixtures.

Run: .venv/bin/python scripts/live_subject_check.py
Uses the configured OpenAI and optional Cohere connections with normal API billing.
All uploads, quizzes, and databases are temporary; no user study sets are changed.
"""
import concurrent.futures
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf
from fastapi.testclient import TestClient
from app import create_app


ROOT = Path(__file__).resolve().parents[1]


def run_subject(item):
    subject, lecture = item
    with tempfile.TemporaryDirectory(prefix='lecture-subject-') as root:
        app = create_app(root, auth_required=False, run_jobs=False)
        with TestClient(app) as client:
            doc = pymupdf.open()
            page = doc.new_page()
            remaining = page.insert_textbox(pymupdf.Rect(42, 45, 550, 790),
                lecture['title'] + '\n\n' + lecture['text'], fontsize=11)
            assert remaining >= 0, 'Fixture text did not fit the PDF page'
            pdf = doc.tobytes()
            doc.close()
            uploaded = client.post('/api/materials', files=[('files', (subject+'.pdf', pdf, 'application/pdf'))])
            uploaded.raise_for_status()
            upload = uploaded.json()
            app.state.engine.run(upload['jobId'])
            job = client.get('/api/jobs/'+upload['jobId']).json()
            assert job['status'] == 'completed', job.get('error')
            results = []
            formats = ['mcq', 'flashcard'] + (['calculation'] if subject == 'physics' else [])
            for kind in formats:
                response = client.post('/api/quizzes', json={'materialId': upload['materialId'],
                    'prompt': 'Cover the main topics of this lecture using relevant questions and applications.',
                    'format': kind, 'count': 4, 'difficulty': 'beginner'})
                response.raise_for_status()
                job_id = response.json()['jobId']
                app.state.engine.run(job_id)
                job = client.get('/api/jobs/'+job_id).json()
                assert job['status'] == 'completed' and job['result'].get('status') == 'ready', job
                quiz = client.get('/api/quizzes/'+job['result']['quizId']).json()
                assert len(quiz['questions']) == 4
                for question in quiz['questions']:
                    source = client.get(question['source']['url'])
                    source.raise_for_status()
                    assert source.json()['page'] == 1
                    assert source.json()['name'] == subject+'.pdf'
                    preview = client.get(source.json()['previewUrl'])
                    assert preview.content.startswith(b'\x89PNG')
                # Ignored evidence artifacts; temporary source IDs resolve only in this check.
                output = ROOT/'data'/(subject+'-'+kind+'-live-check.json')
                output.write_text(json.dumps(quiz, indent=2))
                results.append(kind)
            return {'subject': subject, 'formats': results, 'questions': 4*len(results),
                    'pdfExtraction': 'live', 'sourcePages': 'resolved'}


if __name__ == '__main__':
    lectures = json.loads((ROOT/'fixtures/subject-lectures.json').read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(run_subject, lectures.items()):
            print(json.dumps(result), flush=True)
