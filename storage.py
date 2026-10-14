"""Local, transactional persistence. Provider keys are never stored here."""
import json
import sqlite3
import time
import uuid
from pathlib import Path


def uid():
    return uuid.uuid4().hex


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "lecture_lab.sqlite3"
        # Back up the original database before the first additive collections migration.
        if self.path.exists():
            with sqlite3.connect(self.path) as old:
                migrated = old.execute("SELECT name FROM sqlite_master WHERE name='collections'").fetchone()
                if not migrated:
                    with sqlite3.connect(self.root / 'lecture_lab.pre_collections.sqlite3') as backup:
                        old.backup(backup)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS materials (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, files TEXT NOT NULL,
                    notes TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, material_id TEXT NOT NULL,
                    unit_key TEXT NOT NULL, body TEXT NOT NULL,
                    UNIQUE(material_id, unit_key));
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, material_id TEXT NOT NULL,
                    status TEXT NOT NULL, stage TEXT NOT NULL, completed INTEGER NOT NULL,
                    total INTEGER NOT NULL, cancel INTEGER NOT NULL DEFAULT 0,
                    params TEXT NOT NULL, result TEXT, error TEXT, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS quizzes (
                    id TEXT PRIMARY KEY, material_id TEXT NOT NULL, body TEXT NOT NULL,
                    progress TEXT NOT NULL DEFAULT '{}', created REAL NOT NULL);
            """)
        self.migrate_collections()

    def migrate_collections(self):
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS collections (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS material_collections (
                    material_id TEXT PRIMARY KEY, collection_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, source_id TEXT NOT NULL, material_id TEXT NOT NULL,
                    collection_id TEXT NOT NULL, body TEXT NOT NULL, hash TEXT NOT NULL,
                    model TEXT NOT NULL, indexed INTEGER NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS chunks_collection ON chunks(collection_id,model,indexed);
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY, job_id TEXT UNIQUE, collection_id TEXT NOT NULL,
                    parent_quiz_id TEXT, submitted TEXT NOT NULL, resolved TEXT NOT NULL,
                    snapshot TEXT NOT NULL DEFAULT '[]', quiz_id TEXT, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS quiz_sources (
                    quiz_id TEXT NOT NULL, source_id TEXT NOT NULL, PRIMARY KEY(quiz_id,source_id));
                CREATE TABLE IF NOT EXISTS quiz_collections (quiz_id TEXT PRIMARY KEY, collection_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS vector_cleanup (id TEXT PRIMARY KEY);
            """)
            for row in db.execute('SELECT m.* FROM materials m LEFT JOIN material_collections c ON c.material_id=m.id WHERE c.material_id IS NULL').fetchall():
                cid = uid()
                db.execute('INSERT INTO collections VALUES(?,?,?)', (cid, row['title'], row['created']))
                db.execute('INSERT INTO material_collections VALUES(?,?)', (row['id'], cid))
            # Preserve old quizzes and recover their original request from completed jobs.
            for row in db.execute('SELECT * FROM quizzes').fetchall():
                body = json.loads(row['body'])
                owner = db.execute('SELECT collection_id FROM material_collections WHERE material_id=?', (row['material_id'],)).fetchone()
                if owner:
                    db.execute('INSERT OR IGNORE INTO quiz_collections VALUES(?,?)', (row['id'], owner['collection_id']))
                for q in body.get('questions', []) + body.get('sections', []):
                    sid = q.get('source', {}).get('id')
                    if sid:
                        db.execute('INSERT OR IGNORE INTO quiz_sources VALUES(?,?)', (row['id'], sid))
                if db.execute('SELECT id FROM requests WHERE quiz_id=?', (row['id'],)).fetchone():
                    continue
                owner = db.execute('SELECT collection_id FROM material_collections WHERE material_id=?', (row['material_id'],)).fetchone()
                if not owner:
                    continue
                for job in db.execute("SELECT * FROM jobs WHERE material_id=? AND kind='quiz' AND result IS NOT NULL", (row['material_id'],)).fetchall():
                    if json.loads(job['result']).get('quizId') == row['id']:
                        db.execute('INSERT OR IGNORE INTO requests(id,job_id,collection_id,submitted,resolved,quiz_id,created) VALUES(?,?,?,?,?,?,?)',
                                   (uid(), job['id'], owner['collection_id'], job['params'], job['params'], row['id'], job['created']))
                        break

    def collection_for(self, material_id):
        row = self.one('SELECT collection_id FROM material_collections WHERE material_id=?', (material_id,))
        return row['collection_id'] if row else None

    def add_collection(self, name):
        cid = uid()
        self.execute('INSERT INTO collections VALUES(?,?,?)', (cid, name, time.time()))
        return cid

    def collection_materials(self, cid):
        return self.all('SELECT m.* FROM materials m JOIN material_collections c ON c.material_id=m.id WHERE c.collection_id=? ORDER BY m.created', (cid,))

    def quiz_request(self, quiz_id):
        row = self.one('SELECT * FROM requests WHERE quiz_id=?', (quiz_id,))
        if row:
            for key in ('submitted', 'resolved', 'snapshot'):
                row[key] = json.loads(row[key])
        return row

    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        return db

    def execute(self, query, values=()):
        with self.connect() as db:
            return db.execute(query, values).rowcount

    def one(self, query, values=()):
        with self.connect() as db:
            row = db.execute(query, values).fetchone()
        return dict(row) if row else None

    def all(self, query, values=()):
        with self.connect() as db:
            return [dict(r) for r in db.execute(query, values).fetchall()]

    def material(self, material_id):
        row = self.one("SELECT * FROM materials WHERE id=?", (material_id,))
        if row:
            row["files"] = json.loads(row["files"])
        return row

    def add_material(self, material_id, files, notes, collection_id=None):
        title = ", ".join(f["name"] for f in files) or "Pasted lecture notes"
        self.execute("INSERT INTO materials VALUES (?,?,?,?,?,?)",
                     (material_id, title, json.dumps(files), notes, "queued", time.time()))
        cid = collection_id or self.add_collection(title)
        self.execute('INSERT INTO material_collections VALUES(?,?)', (material_id, cid))

    def sources(self, material_id):
        return [json.loads(r["body"]) for r in self.all(
            "SELECT body FROM sources WHERE material_id=? ORDER BY unit_key", (material_id,))]

    def has_unit(self, material_id, unit):
        return bool(self.one("SELECT id FROM sources WHERE material_id=? AND unit_key=?",
                             (material_id, unit)))

    def save_source(self, material_id, unit, source):
        source = {**source, "id": uid(), "materialId": material_id}
        self.execute("INSERT OR IGNORE INTO sources VALUES (?,?,?,?)",
                     (source["id"], material_id, unit, json.dumps(source)))
        return json.loads(self.one('SELECT body FROM sources WHERE material_id=? AND unit_key=?', (material_id, unit))['body'])

    def add_job(self, kind, material_id, params=None):
        job_id = uid()
        self.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            job_id, kind, material_id, "queued", "Waiting to start", 0, 0, 0,
            json.dumps(params or {}), None, None, time.time()))
        return job_id

    def job(self, job_id):
        row = self.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if row:
            row["params"] = json.loads(row["params"])
            row["result"] = json.loads(row["result"]) if row["result"] else None
        return row

    def update_job(self, job_id, **updates):
        allowed = {"status", "stage", "completed", "total", "cancel", "result", "error"}
        if not updates or not set(updates) <= allowed:
            raise ValueError("Invalid job update")
        if "result" in updates:
            updates["result"] = json.dumps(updates["result"])
        self.execute("UPDATE jobs SET " + ",".join(k + "=?" for k in updates) + " WHERE id=?",
                     (*updates.values(), job_id))

    def add_quiz(self, material_id, quiz):
        quiz_id = uid()
        quiz = {**quiz, "id": quiz_id, "materialId": material_id, "mode": "generated"}
        self.execute("INSERT INTO quizzes(id,material_id,body,created) VALUES(?,?,?,?)",
                     (quiz_id, material_id, json.dumps(quiz), time.time()))
        self.execute('INSERT INTO quiz_collections VALUES(?,?)', (quiz_id, self.collection_for(material_id)))
        return quiz

    def quiz(self, quiz_id):
        row = self.one("SELECT * FROM quizzes WHERE id=?", (quiz_id,))
        if not row:
            return None
        owner = self.one('SELECT collection_id FROM quiz_collections WHERE quiz_id=?', (quiz_id,))
        return {**json.loads(row["body"]), "collectionId": owner['collection_id'] if owner else self.collection_for(row['material_id']),
                "request": self.quiz_request(quiz_id), "progress": json.loads(row["progress"])}

    def recover_interrupted_jobs(self):
        self.execute("UPDATE jobs SET status='interrupted',stage='Interrupted by app restart', "
                     "error='Retry to reuse completed processing.' WHERE status IN ('queued','running')")
        self.execute("UPDATE materials SET status='interrupted' WHERE status IN ('queued','processing')")
