import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def isolate_rerank_credentials(monkeypatch):
    # Fixture tests never send documents to the live account's rerank API.
    monkeypatch.delenv('COHERE_API_KEY', raising=False)
