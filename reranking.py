"""Cohere passage ranking, with bounded calls and a safe vector-search fallback."""
import math
import os

import httpx


class CohereReranker:
    def __init__(self, api_key=None, model=None, transport=None):
        self.api_key = (os.getenv('COHERE_API_KEY', '') if api_key is None else api_key).strip()
        self.model = model or os.getenv('COHERE_RERANK_MODEL', 'rerank-v4.0-fast')
        self.transport = transport

    def rank(self, query, sources, check=lambda: None):
        meta = {'provider': 'cohere', 'model': self.model, 'inputCount': len(sources)}
        if not self.api_key or not sources:
            return sources, {**meta, 'status': 'not_configured' if not self.api_key else 'empty',
                             'outputCount': len(sources)}
        check()
        try:
            with httpx.Client(timeout=httpx.Timeout(15, connect=5), transport=self.transport) as client:
                response = client.post('https://api.cohere.com/v2/rerank',
                    headers={'Authorization': 'Bearer ' + self.api_key, 'X-Client-Name': 'lecture-lab'},
                    json={'model': self.model, 'query': query,
                          'documents': [s['text'] for s in sources], 'top_n': min(12, len(sources)),
                          'max_tokens_per_doc': 2048})
                response.raise_for_status()
                results = response.json()['results']
            if not isinstance(results, list) or len(results) != min(12, len(sources)):
                raise ValueError('Incomplete ranking')
            seen, ranked, scores = set(), [], []
            for result in results:
                index, score = result['index'], result['relevance_score']
                if (type(index) is not int or not 0 <= index < len(sources) or index in seen
                        or type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
                    raise ValueError('Invalid ranking')
                seen.add(index)
                # Only local indices resolve to authoritative sources; provider text is never evidence.
                ranked.append(sources[index])
                scores.append({'chunkId': sources[index]['id'], 'score': score})
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            reason = 'authentication' if code in (401, 403, 498) else 'rate_limit' if code == 429 else 'service_error'
            return sources, {**meta, 'status': 'fallback', 'reason': reason, 'outputCount': len(sources)}
        except httpx.RequestError:
            return sources, {**meta, 'status': 'fallback', 'reason': 'connection', 'outputCount': len(sources)}
        except (ValueError, KeyError, TypeError):
            return sources, {**meta, 'status': 'fallback', 'reason': 'invalid_response', 'outputCount': len(sources)}
        check()  # Cancellation after an in-flight request must not be treated as fallback.
        return ranked, {**meta, 'status': 'applied', 'outputCount': len(ranked), 'rankings': scores}
