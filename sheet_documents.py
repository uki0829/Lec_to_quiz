"""Offline, escaped HTML and Chromium PDF exports of structured study guides."""
import json
import shutil
import subprocess
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PDF_SLOTS = threading.BoundedSemaphore(2)


def validate_document(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('title'), str) or not raw['title'].strip():
        raise ValueError('Choose a cheat sheet with a title.')
    sections = raw.get('sections')
    if not isinstance(sections, list) or not 1 <= len(sections) <= 2048 or len(raw['title']) > 180:
        raise ValueError('The guide is empty or too large to export.')
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get('heading'), str):
            raise ValueError('A guide section is missing its heading.')
        points, formulas, source = section.get('points'), section.get('formulas'), section.get('source')
        if (not isinstance(points, list) or not isinstance(formulas, list) or not (points or formulas)
                or len(points)+len(formulas) > 120
                or any(not isinstance(t, str) or not t.strip() or len(t) > 6000 for t in points+formulas)
                or not isinstance(source, dict)
                or any(not isinstance(source.get(k), str) for k in ('name', 'locator'))):
            raise ValueError('The guide has invalid content or source labels.')
    return {'title': raw['title'], 'description': str(raw.get('description') or '')[:6000], 'sections': sections}


def render_html(raw):
    sheet = validate_document(raw)
    node = shutil.which('node')
    if not node:
        raise ValueError('HTML/PDF export needs Node.js. Install it and restart Lecture Lab.')
    try:
        result = subprocess.run([node, str(ROOT/'scripts/render_sheet.mjs')],
            input=json.dumps(sheet), text=True, capture_output=True, timeout=30, check=True, cwd=ROOT)
    except (subprocess.SubprocessError, OSError) as exc:
        raise ValueError('Could not typeset the guide. Run npm ci in the project folder, then retry.') from exc
    return result.stdout


def render_pdf(html):
    # This is the application's document renderer, separate from the user's browser session.
    from playwright.sync_api import sync_playwright, Error
    with PDF_SLOTS, sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(headless=True)
            try:
                page = browser.new_page(java_script_enabled=False)
                page.route('**/*', lambda route: route.abort())
                page.set_content(html, wait_until='load', timeout=30000)
                # Only fixed rendering code runs here, never user/model supplied scripts.
                page.evaluate('document.fonts.ready')
                return page.pdf(format='A4', print_background=True, prefer_css_page_size=True,
                    display_header_footer=True, header_template='<span></span>',
                    footer_template='<div style="font:9px Arial;color:#64718a;width:100%;text-align:center">'
                                    '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
            finally:
                browser.close()
        except Error as exc:
            raise ValueError('PDF export is unavailable. Run .venv/bin/python -m playwright install chromium, then retry.') from exc
