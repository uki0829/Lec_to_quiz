"""Conversational planning over the existing collection-scoped generation pipeline."""
import json
import time
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field

from accounts import CURRENT_USER
from schemas import AgentPlan


class AgentRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    requestId: str = Field(min_length=8, max_length=80)


class StudyAgent:
    def __init__(self, store, engine):
        self.store, self.engine = store, engine
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS agent_threads(
                    id TEXT PRIMARY KEY,collection_id TEXT NOT NULL,user_id TEXT NOT NULL,
                    created REAL NOT NULL,UNIQUE(collection_id,user_id));
                CREATE TABLE IF NOT EXISTS agent_messages(
                    id TEXT PRIMARY KEY,thread_id TEXT NOT NULL,role TEXT NOT NULL,
                    body TEXT NOT NULL,state TEXT NOT NULL,job_id TEXT,quiz_id TEXT,
                    request_key TEXT,created REAL NOT NULL,UNIQUE(thread_id,request_key));
                CREATE INDEX IF NOT EXISTS agent_thread_messages ON agent_messages(thread_id,created);
            ''')

    def recover(self):
        self.store.execute("UPDATE agent_messages SET state='failed',body=? WHERE state='planning'",
            (json.dumps({'text': 'Planning was interrupted. Send your request again.'}),))

    def thread(self, cid, create=False):
        user = CURRENT_USER.get()
        user_id = user['id'] if user else 'demo-hefeng'
        if create:
            self.store.execute('INSERT OR IGNORE INTO agent_threads VALUES(?,?,?,?)',
                (uuid.uuid4().hex, cid, user_id, time.time()))
        return self.store.one('SELECT * FROM agent_threads WHERE collection_id=? AND user_id=?', (cid, user_id))

    def update(self, ident, state, body, job_id=None, quiz_id=None):
        self.store.execute('UPDATE agent_messages SET state=?,body=?,job_id=?,quiz_id=? WHERE id=?',
            (state, json.dumps(body), job_id, quiz_id, ident))

    def original_request(self, job_id, text):
        row = self.store.one('SELECT submitted FROM requests WHERE job_id=?', (job_id,))
        if row:
            self.store.execute('UPDATE requests SET submitted=? WHERE job_id=?',
                (json.dumps({**json.loads(row['submitted']), 'prompt': text, 'origin': 'agent'}), job_id))

    def history(self, cid):
        thread = self.thread(cid)
        if not thread:
            return []
        rows = self.store.all('SELECT * FROM agent_messages WHERE thread_id=? ORDER BY created,id', (thread['id'],))
        for row in rows:
            body = json.loads(row['body'])
            job = self.store.job(row['job_id']) if row['job_id'] else None
            if row['role'] == 'assistant' and row['state'] == 'pending':
                if not job:
                    self.update(row['id'], 'failed', {'text': 'The generation job is unavailable. Send a new request.'})
                elif job['status'] in ('failed', 'interrupted', 'cancelled'):
                    text = job.get('error') or ('Generation was cancelled.' if job['status'] == 'cancelled' else 'Generation was interrupted.')
                    self.update(row['id'], 'failed', {**body, 'text': text}, job_id=job['id'])
                elif job['status'] == 'completed':
                    result = job.get('result') or {}
                    if result.get('status') == 'ready' and result.get('quizId'):
                        self.update(row['id'], 'ready', {**body, 'text': 'Your study set is ready.'},
                                    job_id=job['id'], quiz_id=result['quizId'])
                    else:
                        self.update(row['id'], 'clarify', {**body, 'text': result.get('message') or 'Choose another topic or add clearer lecture material.'})
        rows = self.store.all('SELECT * FROM agent_messages WHERE thread_id=? ORDER BY created,id', (thread['id'],))
        result = []
        for row in rows[-100:]:
            body = json.loads(row['body'])
            message = {'id': row['id'], 'role': row['role'], 'state': row['state'], 'text': body.get('text', ''),
                       'jobId': row['job_id'], 'quizId': row['quiz_id']}
            if row['job_id'] and row['state'] == 'pending':
                job = self.store.job(row['job_id'])
                if job:
                    message['stage'] = job['stage']
            if row['quiz_id']:
                quiz = self.store.quiz(row['quiz_id'])
                if quiz and quiz.get('collectionId') == cid:
                    items = quiz.get('sections', []) if quiz['format'] == 'cheatsheet' else quiz['questions']
                    sources = {item['source']['id']: {k: item['source'][k] for k in ('id', 'name', 'locator')}
                               for item in items if item.get('source', {}).get('id')}
                    message['set'] = {'id': quiz['id'], 'title': quiz['title'], 'format': quiz['format'],
                                      'count': len(items), 'sources': list(sources.values()), 'grounding': quiz.get('grounding', 'lecture')}
                else:
                    message.update(state='removed', text='This study set was removed.', quizId=None, jobId=None)
            result.append(message)
        return result

    def routes(self, app, make_quiz, retry_quiz, require_collection, mutation_lock):
        @app.get('/api/collections/{cid}/agent')
        def messages(cid: str):
            require_collection(cid)
            return {'messages': self.history(cid)}

        @app.post('/api/collections/{cid}/agent/messages')
        def send(cid: str, request: AgentRequest):
            require_collection(cid)
            text = request.message.strip()
            if not text:
                raise HTTPException(400, 'Enter a study request.')
            with mutation_lock:
                thread = self.thread(cid, create=True)
                self.history(cid)
                existing = self.store.one('SELECT id FROM agent_messages WHERE thread_id=? AND request_key=?',
                                           (thread['id'], request.requestId))
                if existing:
                    return {'messageId': existing['id'], 'messages': self.history(cid)}
                if self.store.one("SELECT id FROM agent_messages WHERE thread_id=? AND state IN ('planning','pending')", (thread['id'],)):
                    raise HTTPException(409, 'Finish or cancel the current agent request first.')
                ident = uuid.uuid4().hex
                now = time.time()
                with self.store.connect() as db:
                    db.execute('INSERT INTO agent_messages VALUES(?,?,?,?,?,?,?,?,?)',
                        (uuid.uuid4().hex, thread['id'], 'user', json.dumps({'text': text}), 'ready', None, None, None, now))
                    db.execute('INSERT INTO agent_messages VALUES(?,?,?,?,?,?,?,?,?)',
                        (ident, thread['id'], 'assistant', json.dumps({'text': 'Understanding your request…', 'request': text}),
                         'planning', None, None, request.requestId, now+.0001))
            try:
                mids = self.engine.retriever.snapshot(cid)
                history = self.history(cid)
                previous = None
                for item in reversed(history):
                    if item.get('set'):
                        previous = self.store.quiz(item['set']['id'])
                        break
                previous_context = None
                if previous:
                    settings = (previous.get('request') or {}).get('resolved') or {}
                    previous_context = {'title': previous['title'], 'prompt': settings.get('prompt', previous['title']),
                        'format': previous['format'], 'count': settings.get('count', 6),
                        'difficulty': settings.get('difficulty', 'intermediate')}
                materials = [{'name': self.store.material(mid)['title']} for mid in mids]
                conversation = [{'role': m['role'], 'text': m['text'][:1600]} for m in history[-12:-2]]
                plan = AgentPlan.model_validate(self.engine.ai.plan_study(text, conversation, materials, previous_context))
                if len(plan.message) > 2000 or len(plan.prompt) > 4000:
                    raise ValueError('The agent request was too long. Please shorten it.')
                if plan.action == 'clarify':
                    self.update(ident, 'clarify', {'text': plan.message})
                else:
                    if not plan.prompt.strip():
                        raise ValueError('The agent needs a topic for this study set.')
                    with mutation_lock:
                        require_collection(cid)
                        inherited = previous_context if plan.buildOnPrevious and previous else {}
                        params = {'collectionId': cid, 'prompt': plan.prompt,
                                  'format': plan.format or inherited.get('format', 'mcq'),
                                  'count': plan.count or inherited.get('count', 6),
                                  'difficulty': plan.difficulty or inherited.get('difficulty', 'intermediate')}
                        if plan.buildOnPrevious and previous:
                            params['parentQuizId'] = previous['id']
                        job = make_quiz(params)
                        self.original_request(job['jobId'], text)
                        self.update(ident, 'pending', {'text': plan.message or 'Creating your study set.', 'request': text},
                                    job_id=job['jobId'])
            except Exception as exc:
                self.update(ident, 'failed', {'text': str(exc) if isinstance(exc, ValueError) else
                    (str(exc.detail) if isinstance(exc, HTTPException) else 'The agent could not complete this request. Try again.'), 'request': text})
            return {'messageId': ident, 'messages': self.history(cid)}

        @app.post('/api/collections/{cid}/agent/messages/{message_id}/retry')
        def retry(cid: str, message_id: str):
            require_collection(cid)
            with mutation_lock:
                thread = self.thread(cid)
                row = self.store.one('SELECT * FROM agent_messages WHERE id=? AND thread_id=? AND role=\'assistant\'',
                                     (message_id, thread['id'])) if thread else None
                if not row or not row['job_id']:
                    raise HTTPException(404, 'Send a new request to try planning again.')
                self.history(cid)
                row = self.store.one('SELECT * FROM agent_messages WHERE id=?', (message_id,))
                if row['state'] != 'failed':
                    raise HTTPException(409, 'This request does not need a retry.')
                job = retry_quiz(row['job_id'])
                original = self.store.one('SELECT submitted FROM requests WHERE job_id=?', (row['job_id'],))
                if original:
                    self.original_request(job['jobId'], json.loads(original['submitted']).get('prompt', ''))
                self.update(message_id, 'pending', {'text': 'Retrying your study set.'}, job_id=job['jobId'])
            return {'messageId': message_id, 'messages': self.history(cid)}
