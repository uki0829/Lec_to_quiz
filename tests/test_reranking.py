import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import create_app
from processing import Cancelled
from reranking import CohereReranker
from test_rag import CrossSourceAI, collection, add, quiz_request


SOURCES = [{'id': 'a', 'text': 'An operational database captures transactions.'},
           {'id': 'b', 'text': 'An analytical warehouse compares measures over time.'}]


def reranker(handler):
    return CohereReranker(api_key='fixture-key', transport=httpx.MockTransport(handler))


def test_ranking_contract_and_original_evidence():
    captured = {}
    def handler(request):
        captured.update(body=json.loads(request.content), url=str(request.url))
        assert request.headers['Authorization'] == 'Bearer fixture-key'
        return httpx.Response(200, json={'results': [{'index': 1, 'relevance_score': .9},
                                                  {'index': 0, 'relevance_score': .1}]})
    ranked, meta = reranker(handler).rank('OLAP', SOURCES)
    assert ranked == [SOURCES[1], SOURCES[0]]
    assert ranked[0] is SOURCES[1]
    assert captured['url'] == 'https://api.cohere.com/v2/rerank'
    assert captured['body']['documents'] == [s['text'] for s in SOURCES]
    assert captured['body']['top_n'] == 2 and meta['status'] == 'applied'
    assert 'fixture-key' not in json.dumps(meta)


def test_missing_credentials_and_empty_input_do_not_call_provider():
    def handler(request):
        raise AssertionError('Unexpected external request')
    ranked, meta = CohereReranker(api_key='', transport=httpx.MockTransport(handler)).rank('OLAP', SOURCES)
    assert ranked is SOURCES and meta['status'] == 'not_configured'
    assert reranker(handler).rank('OLAP', [])[1]['status'] == 'empty'


@pytest.mark.parametrize('status,reason', [(401, 'authentication'), (403, 'authentication'),
                                          (429, 'rate_limit'), (503, 'service_error')])
def test_provider_errors_preserve_vector_results(status, reason):
    ranked, meta = reranker(lambda request: httpx.Response(status, json={'error': 'private body'})).rank('OLAP', SOURCES)
    assert ranked is SOURCES and meta['status'] == 'fallback' and meta['reason'] == reason
    assert 'private body' not in json.dumps(meta)


@pytest.mark.parametrize('results', [[], [{'index': 0, 'relevance_score': .9}],
    [{'index': 9, 'relevance_score': .9}, {'index': 0, 'relevance_score': .1}],
    [{'index': 0, 'relevance_score': .9}, {'index': 0, 'relevance_score': .1}],
    [{'index': 0, 'relevance_score': 'unknown'}, {'index': 1, 'relevance_score': .1}]])
def test_malformed_ranking_cannot_invent_or_duplicate_sources(results):
    ranked, meta = reranker(lambda request: httpx.Response(200, json={'results': results})).rank('OLAP', SOURCES)
    assert ranked is SOURCES and meta['reason'] == 'invalid_response'


def test_timeout_and_cancellation():
    def timeout(request):
        raise httpx.ReadTimeout('fixture', request=request)
    assert reranker(timeout).rank('OLAP', SOURCES)[1]['reason'] == 'connection'
    checks = 0
    def check():
        nonlocal checks
        checks += 1
        if checks == 2:
            raise Cancelled()
    valid = lambda request: httpx.Response(200, json={'results': [
        {'index': 0, 'relevance_score': .9}, {'index': 1, 'relevance_score': .1}]})
    with pytest.raises(Cancelled):
        reranker(valid).rank('OLAP', SOURCES, check)


def test_collection_isolation_evidence_and_ranking_audit(tmp_path):
    ai = CrossSourceAI(); app = create_app(tmp_path,auth_required=False, ai=ai, run_jobs=False)
    engine = app.state.engine
    calls = []
    def handler(request):
        docs = json.loads(request.content)['documents']; calls.append(docs)
        order = sorted(range(len(docs)), key=lambda i: 'learning rate' not in docs[i].lower())
        return httpx.Response(200, json={'results': [
            {'index': i, 'relevance_score': 1 - n / len(docs)} for n, i in enumerate(order[:12])]})
    engine.reranker = reranker(handler)
    with TestClient(app) as client:
        cid = collection(client, 'Machine Learning'); other = collection(client, 'History')
        m1 = add(client, engine, cid)
        m2 = add(client, engine, cid, 'Learning rate controls the step size. Smaller learning rate means smaller steps.')
        add(client, engine, other, 'HISTORY CONTENT MUST STAY OUT OF THIS SEARCH')
        q = quiz_request(client, engine, cid, prompt='learning rate')
        assert not any('HISTORY' in d for d in calls[-1])
        assert {s['materialId'] for s in ai.selections[-1][1]} == {m1, m2}
        assert q['request']['resolved']['reranking']['status'] == 'applied'
        assert q['request']['resolved']['reranking']['rankings'][0]['score'] == 1
        assert all(client.get(x['source']['url']).status_code == 200 for x in q['questions'])
        engine.reranker = reranker(lambda request: httpx.Response(429))
        fallback = quiz_request(client, engine, cid)
        assert fallback['request']['resolved']['reranking']['reason'] == 'rate_limit'
        assert client.get('/api/quizzes/' + q['id']).status_code == 200
