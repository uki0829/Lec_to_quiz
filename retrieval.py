"""Persistent, collection-scoped retrieval. SQLite decides which vectors are eligible."""
import hashlib
import json
import os
import threading

import chromadb
from chromadb.config import Settings
import tiktoken


def split_text(text, target=800, overlap=100):
    """Token-bounded windows with exact character offsets, including Unicode text."""
    encoding = tiktoken.get_encoding('cl100k_base')
    start = 0
    while start < len(text):
        low, high = start + 1, min(len(text), start + target * 8)
        while low < high:
            middle = (low + high + 1) // 2
            if len(encoding.encode(text[start:middle], disallowed_special=())) <= target:
                low = middle
            else:
                high = middle - 1
        end = low
        if text[start:end].strip():
            yield start, end, text[start:end]
        if end == len(text):
            break
        low, high = start + 1, end
        while low < high:
            middle = (low + high) // 2
            if len(encoding.encode(text[middle:end], disallowed_special=())) > overlap:
                low = middle + 1
            else:
                high = middle
        start = max(start + 1, low)


class Retriever:
    def __init__(self, store, ai):
        self.store, self.ai = store, ai
        self.model = getattr(ai, 'embedding_model', os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'))
        self._client = None
        self.lock = threading.RLock()

    def vectors(self):
        with self.lock:
            if self._client is None:
                self._client = chromadb.PersistentClient(path=str(self.store.root / 'chroma'), settings=Settings(anonymized_telemetry=False))
            name = 'lectures-' + hashlib.sha256(self.model.encode()).hexdigest()[:16]
            return self._client.get_or_create_collection(
                name, embedding_function=None, configuration={'hnsw': {'space': 'cosine'}})

    def cleanup(self):
        pending = self.store.all('SELECT id FROM vector_cleanup')
        if not pending:
            return
        try:
            with self.lock:
                # Old embedding-model collections can contain the same deleted source.
                self.vectors()
                for collection in self._client.list_collections():
                    self._client.get_collection(collection.name, embedding_function=None).delete(ids=[r['id'] for r in pending])
                with self.store.connect() as db:
                    db.executemany('DELETE FROM vector_cleanup WHERE id=?', [(r['id'],) for r in pending])
        except Exception:
            # Tombstones remain for restart/retry; retrieval never trusts vector metadata alone.
            return

    def is_ready(self, material_id):
        row = self.store.material(material_id)
        if not row or row['status'] != 'ready':
            return False
        sources = [s for s in self.store.sources(material_id) if s['text'].strip()]
        if not sources:
            return False
        for source in sources:
            chunks = self.store.all('SELECT indexed FROM chunks WHERE source_id=? AND model=?', (source['id'], self.model))
            if not chunks or any(not c['indexed'] for c in chunks):
                return False
        return True

    def index(self, material_id, check=lambda: None, stage=lambda *a: None):
        cid = self.store.collection_for(material_id)
        for source in self.store.sources(material_id):
            for start, end, text in split_text(source['text']):
                digest = hashlib.sha256(text.encode()).hexdigest()
                chunk_id = hashlib.sha256(f'{source["id"]}:{start}:{end}:{self.model}:{digest}'.encode()).hexdigest()
                body = {**source, 'id': chunk_id, 'originalSourceId': source['id'], 'text': text,
                        'textStart': start, 'textEnd': end, 'summary': text}
                self.store.execute('INSERT OR IGNORE INTO chunks(id,source_id,material_id,collection_id,body,hash,model) VALUES(?,?,?,?,?,?,?)',
                                   (chunk_id, source['id'], material_id, cid, json.dumps(body), digest, self.model))
        rows = self.store.all('SELECT * FROM chunks WHERE material_id=? AND model=? ORDER BY id', (material_id, self.model))
        remaining = [r for r in rows if not r['indexed']]
        done = len(rows) - len(remaining)
        stage('Indexing lecture sections for search', done, len(rows))
        for offset in range(0, len(remaining), 64):
            check()
            batch = remaining[offset:offset+64]
            embeddings = self.ai.embed([json.loads(r['body'])['text'] for r in batch])
            check()
            if len(embeddings) != len(batch):
                raise ValueError('The embedding provider returned incomplete results. Retry indexing.')
            with self.lock:
                self.vectors().upsert(ids=[r['id'] for r in batch], embeddings=embeddings,
                                      metadatas=[{'collectionId': cid, 'materialId': material_id} for r in batch])
            with self.store.connect() as db:
                db.executemany('UPDATE chunks SET indexed=1 WHERE id=?', [(r['id'],) for r in batch])
            done += len(batch)
            stage('Indexing lecture sections for search', done, len(rows))

    def snapshot(self, cid):
        return [r['id'] for r in self.store.collection_materials(cid) if self.is_ready(r['id'])]

    def search(self, cid, material_ids, query, check=lambda: None):
        # Limit vectors by exact IDs from SQLite, not just potentially stale metadata.
        if not material_ids:
            return []
        marks = ','.join('?' for _ in material_ids)
        rows = self.store.all(f'SELECT c.* FROM chunks c JOIN sources s ON s.id=c.source_id JOIN materials m ON m.id=c.material_id '
                              f'WHERE c.collection_id=? AND c.model=? AND c.indexed=1 AND m.status=\'ready\' AND c.material_id IN ({marks})',
                              (cid, self.model, *material_ids))
        if not rows:
            return []
        check()
        vector = self.ai.embed([query])[0]
        check()
        mapping = {r['id']: json.loads(r['body']) for r in rows}
        with self.lock:
            result = self.vectors().query(query_embeddings=[vector], ids=list(mapping), n_results=min(24, len(rows)), include=['distances'])
        # Recheck existence after any in-flight provider request.
        return [mapping[i] for i in result['ids'][0] if i in mapping and self.store.one('SELECT id FROM sources WHERE id=?', (mapping[i]['originalSourceId'],))]
