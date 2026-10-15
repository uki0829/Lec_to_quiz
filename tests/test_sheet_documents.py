import copy

import pymupdf as fitz
import pytest
from fastapi.testclient import TestClient

from app import create_app
from sheet_documents import render_html, render_pdf, validate_document
from test_app import FakeAI


def document():
    return {'title': 'Optimization study guide', 'description': 'Definitions, equations, and interpretation.',
        'sections': [{'heading': 'Gradient descent',
            'points': [r'For a differentiable loss \(L(w)\), move against its gradient.',
                       r'The learning rate \(\eta\) controls the update size.'],
            'formulas': [r'w^{\mathrm{new}}=w-\eta\nabla L(w)', r'L(w)=\frac{1}{2}w^2'],
            'source': {'name': 'Optimization.pdf', 'locator': 'Page 1'}}]}


def test_offline_html_escapes_content_and_preserves_math():
    sheet = document()
    sheet['sections'][0]['points'].append('<script>alert("bad")</script>')
    html = render_html(sheet)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'data:font/woff2;base64,' in html
    assert 'url(fonts/' not in html
    assert 'class="katex' in html and 'application/x-tex' in html
    assert 'Optimization.pdf' in html and 'Page 1' in html
    assert 'default-src' in html and 'https://' not in html
    wide = document()
    wide['sections'][0]['points'] *= 4
    wide['sections'][0]['formulas'] *= 3
    assert validate_document(wide)['sections']
    broken = copy.deepcopy(wide)
    broken['sections'][0]['points'] = broken['sections'][0]['formulas'] = []
    with pytest.raises(ValueError, match='content'):
        validate_document(broken)


def test_export_endpoints_html_pdf_and_errors(tmp_path):
    app = create_app(tmp_path, ai=FakeAI(), auth_required=False, run_jobs=False)
    with TestClient(app) as client:
        response = client.post('/api/cheatsheets/export?format=html', json=document())
        assert response.status_code == 200
        assert response.headers['content-type'].startswith('text/html')
        assert 'attachment' in response.headers['content-disposition']
        pdf = client.post('/api/cheatsheets/export?format=pdf', json=document())
        assert pdf.status_code == 200, pdf.text
        assert pdf.content.startswith(b'%PDF')
        with fitz.open(stream=pdf.content, filetype='pdf') as doc:
            assert len(doc) >= 1
            text = ''.join(page.get_text() for page in doc)
            assert 'Optimization study guide' in text and 'Gradient descent' in text
            assert 'Optimization.pdf' in text
        assert client.post('/api/cheatsheets/export?format=exe', json=document()).status_code == 400
        assert client.post('/api/cheatsheets/export', content='invalid').status_code == 400
        assert client.post('/api/cheatsheets/export', json={'title': 'Empty', 'sections': []}).status_code == 400
        assert client.post('/api/cheatsheets/export', content='x'*(4*1024*1024+1)).status_code == 413


def test_export_requires_signin(tmp_path):
    app = create_app(tmp_path, ai=FakeAI(), run_jobs=False)
    with TestClient(app) as client:
        assert client.post('/api/cheatsheets/export', json=document()).status_code == 401
