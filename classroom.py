"""Persistent personal tutor identities and membership-scoped collaborative teaching."""
import hashlib
import json
import math
import re
import time

from fastapi import HTTPException
from pydantic import BaseModel, Field

from accounts import CURRENT_USER
from schemas import validate_quiz
from storage import uid

AVATARS = [
    {'id': 'explorer', 'name': 'Page', 'description': 'Curious explorer'},
    {'id': 'cloud', 'name': 'Mochi', 'description': 'Patient companion'},
    {'id': 'fox', 'name': 'Sage', 'description': 'Thoughtful scholar'},
    {'id': 'pig', 'name': 'Pip', 'description': 'Playful inventor'},
]
STYLES = {'guide': 'Explain clearly, then offer a small example.',
          'coach': 'Ask a useful guiding question and offer a hint.',
          'analyst': 'Check assumptions, compare ideas, and explain the reasoning.'}


class TutorSettings(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    avatar: str
    style: str


class ClassroomRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    agentIds: list[str] = Field(min_length=1, max_length=2)
    action: str = 'explain'
    count: int = 4
    requestId: str = Field(min_length=8, max_length=80)


def cosine(left, right):
    if len(left) != len(right) or not left:
        return -1
    norm = math.sqrt(sum(x*x for x in left)*sum(x*x for x in right))
    return sum(a*b for a, b in zip(left, right))/norm if norm else 0


def display_text(text):
    # References are rendered as source buttons, never opaque database IDs.
    return re.sub(r'\[?[0-9a-f]{32}:\d+\]?', '', text).strip()


class Classroom:
    def __init__(self, store, engine, accounts, groups):
        self.store, self.engine, self.accounts, self.groups = store, engine, accounts, groups
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS agent_profiles(
                    user_id TEXT PRIMARY KEY,name TEXT NOT NULL,avatar TEXT NOT NULL,
                    style TEXT NOT NULL,updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS classroom_turns(
                    id TEXT PRIMARY KEY,group_id TEXT NOT NULL,user_id TEXT NOT NULL,
                    request_key TEXT NOT NULL,job_id TEXT NOT NULL,body TEXT NOT NULL,
                    created REAL NOT NULL,UNIQUE(group_id,user_id,request_key));
                CREATE TABLE IF NOT EXISTS classroom_vectors(
                    group_id TEXT NOT NULL,source_id TEXT NOT NULL,model TEXT NOT NULL,
                    hash TEXT NOT NULL,vector TEXT NOT NULL,PRIMARY KEY(group_id,source_id,model));
            ''')
        for user in store.all('SELECT id,name FROM users'):
            self.profile(user)
        accounts.agents = self
        engine.classroom = self

    def profile(self, user):
        if not user:
            raise HTTPException(401, 'Sign in to choose your agent.')
        default = int(hashlib.sha256(user['id'].encode()).hexdigest()[:4], 16) % len(AVATARS)
        avatar = AVATARS[default]
        self.store.execute('INSERT OR IGNORE INTO agent_profiles VALUES(?,?,?,?,?)',
            (user['id'], avatar['name'], avatar['id'], 'guide', time.time()))
        row = self.store.one('SELECT * FROM agent_profiles WHERE user_id=?', (user['id'],))
        return {'id': row['user_id'], 'name': row['name'], 'avatar': row['avatar'],
                'style': row['style'], 'ownerName': user['name']}

    def roster(self, gid):
        members = self.store.all('SELECT u.id,u.name FROM users u JOIN group_members m ON m.user_id=u.id '
                                 'WHERE m.group_id=? ORDER BY m.joined,m.rowid', (gid,))
        return [self.profile(user) for user in members]

    def check(self, job_id, params):
        self.engine.check(job_id)
        if not self.store.one('SELECT user_id FROM group_members WHERE group_id=? AND user_id=?',
                              (params['groupId'], params['requesterId'])):
            raise ValueError('The requesting student has left this group.')
        for ident in params['agentIds']:
            if not self.store.one('SELECT user_id FROM group_members WHERE group_id=? AND user_id=?',
                                  (params['groupId'], ident)):
                raise ValueError('A selected teacher has left this group. Choose again.')
        for sid in params['sharedSnapshot']:
            if not self.store.one('SELECT id FROM group_sets WHERE group_id=? AND id=?', (params['groupId'], sid)):
                raise ValueError('A shared source was removed. Send a new request.')

    def sources(self, gid, shared_ids):
        sources = []
        for sid in shared_ids:
            row = self.store.one('SELECT body FROM group_sets WHERE group_id=? AND id=?', (gid, sid))
            if not row:
                continue
            body = json.loads(row['body'])
            for i, item in enumerate(body.get('questions', []) + body.get('sections', [])):
                if 'prompt' in item:
                    text = '\n'.join([item['prompt'], 'Answer: '+item['answer'], item['explanation'], *item.get('steps', [])])
                else:
                    text = '\n'.join([item['heading'], *item['points'], *item['formulas']])
                sources.append({'id': sid+':'+str(i), 'shareId': sid, 'name': body['title'],
                    'locator': ('Section ' if 'heading' in item else 'Question ')+str(i+1),
                    'kind': 'group', 'text': text[:6000], 'summary': text[:300], 'uncertainty': ''})
        return sources

    def retrieve(self, job_id, params):
        sources = self.sources(params['groupId'], params['sharedSnapshot'])
        if not sources:
            return []
        # Cache embeddings of explicitly shared content only. Membership and current
        # shared rows, never the cache, determine what can enter a prompt.
        self.engine.stage(job_id, 'Searching shared study sets', 0, 4)
        model = self.engine.retriever.model
        missing, vectors = [], {}
        for source in sources:
            digest = hashlib.sha256(source['text'].encode()).hexdigest()
            row = self.store.one('SELECT hash,vector FROM classroom_vectors WHERE group_id=? AND source_id=? AND model=?',
                                  (params['groupId'], source['id'], model))
            if row and row['hash'] == digest:
                vectors[source['id']] = json.loads(row['vector'])
            else:
                missing.append((source, digest))
        for offset in range(0, len(missing), 32):
            self.check(job_id, params)
            batch = missing[offset:offset+32]
            embedded = self.engine.ai.embed([source['text'] for source, _ in batch])
            if len(embedded) != len(batch):
                raise ValueError('Shared-content indexing was incomplete. Try again.')
            self.check(job_id, params)
            for (source, digest), vector in zip(batch, embedded):
                vectors[source['id']] = vector
                self.store.execute('INSERT OR REPLACE INTO classroom_vectors VALUES(?,?,?,?,?)',
                    (params['groupId'], source['id'], model, digest, json.dumps(vector)))
        query = self.engine.ai.embed([params['prompt']])[0]
        self.check(job_id, params)
        ranked = sorted(sources, key=lambda s: cosine(query, vectors[s['id']]), reverse=True)[:24]
        ranked, _ = self.engine.reranker.rank(params['prompt'], ranked, lambda: self.check(job_id, params))
        selected = self.engine.ai.select(params['prompt'], ranked)
        self.check(job_id, params)
        if selected['status'] == 'insufficient_source':
            return []
        if selected['status'] != 'ready':
            raise ValueError(selected.get('message') or 'Please clarify the topic.')
        ids = selected['sourceIds']
        mapping = {s['id']: s for s in ranked}
        if not ids or len(ids)>12 or not set(ids)<=mapping.keys():
            raise ValueError('The teachers selected invalid shared references. Try again.')
        return [mapping[i] for i in dict.fromkeys(ids)]

    def save_body(self, turn_id, body):
        self.store.execute('UPDATE classroom_turns SET body=? WHERE id=?', (json.dumps(body), turn_id))

    def process(self, job_id, params):
        self.check(job_id, params)
        sources = self.retrieve(job_id, params)
        roster = {a['id']: a for a in self.roster(params['groupId'])}
        body = {'prompt': params['prompt'], 'action': params['action'], 'replies': [],
                'grounding': 'shared' if sources else 'general', 'takeaway': '', 'shareId': None}
        prior = self.store.all('SELECT body FROM classroom_turns WHERE group_id=? AND id<>? ORDER BY created DESC LIMIT 3',
                               (params['groupId'], params['turnId']))
        history = [{'prompt': b.get('prompt'), 'takeaway': b.get('takeaway')} for row in reversed(prior) if (b:=json.loads(row['body']))]
        for number, ident in enumerate(params['agentIds']):
            self.check(job_id, params)
            teacher = roster[ident]
            self.engine.stage(job_id, teacher['name']+' is teaching', number+1, 4)
            body['activeAgentId'] = ident
            self.save_body(params['turnId'], body)
            teaching_prompt = params['prompt']
            if params['action'] != 'explain':
                teaching_prompt = ('We are preparing a '+params['action']+' study set. Discuss the central concept '
                    'and one useful teaching approach in under 70 words. Do not write the questions, options, '
                    'flashcards, or guide yourself: the generation tool will create the interactive artifact. '
                    'Student topic request: '+params['prompt'])
            reply = self.engine.ai.teach_classroom(teaching_prompt, teacher, STYLES[teacher['style']], sources,
                body['replies'], history)
            self.check(job_id, params)
            ids = reply.get('sourceIds', [])
            mapping = {s['id']: s for s in sources}
            if not set(ids)<=mapping.keys() or (sources and not ids):
                raise ValueError('A teacher response needs valid shared-set references.')
            if not reply.get('text', '').strip() or len(reply['text'])>5000 or len(reply.get('takeaway',''))>1000:
                raise ValueError('The teacher response was incomplete. Try again.')
            reply['text'], reply['takeaway'] = display_text(reply['text']), display_text(reply['takeaway'])
            body['replies'].append({'agent': teacher, 'text': reply['text'], 'takeaway': reply['takeaway'],
                'sources': [{k: mapping[s][k] for k in ('shareId','name','locator')} for s in dict.fromkeys(ids)]})
            body['takeaway'] = reply['takeaway']
            body['activeAgentId'] = None
            self.save_body(params['turnId'], body)
        if params['action'] != 'explain':
            self.engine.stage(job_id, 'Teachers are creating your study set', 3, 4)
            settings = {'prompt': params['prompt'], 'format': params['action'], 'count': params['count'],
                        'difficulty': 'intermediate', 'teacher': roster[params['agentIds'][0]],
                        'teacherDiscussion': [{'name':r['agent']['name'],'takeaway':r['takeaway']} for r in body['replies']]}
            feedback = ''
            for attempt in range(2):
                self.check(job_id, params)
                raw = self.engine.ai.generate(settings, sources, feedback) if sources else self.engine.ai.generate_general(settings, feedback)
                self.check(job_id, params)
                try:
                    artifact = validate_quiz(raw, sources, params['action'], params['count'], general=not sources)
                    if artifact['status'] != 'ready':
                        raise ValueError(artifact.get('message') or 'Clarify the practice topic.')
                    break
                except ValueError as exc:
                    if attempt: raise
                    feedback = json.dumps({'error': str(exc), 'previousAttempt': raw})
            # Persist a group artifact directly, never into an agent owner's private library.
            self.check(job_id, params)
            for item in artifact.get('questions', []) + artifact.get('sections', []):
                item['source'] = {k: item['source'][k] for k in ('name','locator','quote','kind') if k in item['source']}
            artifact.update(format=params['action'], grounding=body['grounding'],
                            teachers=[roster[i]['name'] for i in params['agentIds']])
            sid = uid()
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.check(job_id, params)
                db.execute('INSERT INTO group_sets VALUES(?,?,?,?,?,?,0)',
                    (sid, params['groupId'], params['requesterId'], None, json.dumps(artifact), time.time()))
                body['shareId'] = sid
                db.execute('UPDATE classroom_turns SET body=? WHERE id=?', (json.dumps(body), params['turnId']))
        return {'turnId': params['turnId'], 'shareId': body['shareId'], 'status': 'ready'}

    def history(self, gid):
        rows = self.store.all('SELECT t.*,u.name AS requester_name FROM classroom_turns t '
            'JOIN users u ON u.id=t.user_id WHERE t.group_id=? ORDER BY t.created DESC LIMIT 30', (gid,))
        result = []
        for row in reversed(rows):
            job = self.store.job(row['job_id'])
            body = json.loads(row['body'])
            for reply in body.get('replies', []):
                reply['text'] = display_text(reply['text'])
            if body.get('shareId') and not self.store.one('SELECT id FROM group_sets WHERE id=? AND group_id=?', (body['shareId'], gid)):
                body['shareId'] = None
            result.append({**body, 'id': row['id'], 'userId': row['user_id'], 'userName': row['requester_name'],
                'jobId': row['job_id'] if row['user_id']==CURRENT_USER.get()['id'] else None,
                'status': job['status'] if job else 'interrupted',
                'stage': job['stage'] if job else 'Send a new request.',
                'error': (job.get('error') or 'This request was cancelled.') if job and job['status'] in ('failed','cancelled','interrupted') else None})
        return result

    def routes(self, app, mutation_lock, run_jobs):
        @app.get('/api/agents/me')
        def mine():
            return {'agent': self.profile(CURRENT_USER.get()), 'avatars': AVATARS, 'styles': list(STYLES)}

        @app.patch('/api/agents/me')
        def update(body: TutorSettings):
            user = CURRENT_USER.get()
            self.profile(user)
            if body.avatar not in {a['id'] for a in AVATARS} or body.style not in STYLES or not body.name.strip():
                raise HTTPException(400, 'Choose a name, avatar, and teaching style.')
            self.store.execute('UPDATE agent_profiles SET name=?,avatar=?,style=?,updated=? WHERE user_id=?',
                              (body.name.strip(), body.avatar, body.style, time.time(), user['id']))
            return {'agent': self.profile(user)}

        @app.get('/api/groups/{gid}/classroom')
        def room(gid: str):
            self.groups.member(gid)
            return {'agents': self.roster(gid), 'turns': self.history(gid),
                    'sharedCount': self.store.one('SELECT count(*) AS n FROM group_sets WHERE group_id=?',(gid,))['n']}

        @app.post('/api/groups/{gid}/classroom', status_code=202)
        def ask(gid: str, body: ClassroomRequest):
            with mutation_lock, self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.groups.member(gid, db)
                user = CURRENT_USER.get()
                old = db.execute('SELECT id,job_id FROM classroom_turns WHERE group_id=? AND user_id=? AND request_key=?',
                                 (gid, user['id'], body.requestId)).fetchone()
                if old:
                    return {'turnId': old['id'], 'jobId': old['job_id']}
                if body.action not in ('explain','mcq','flashcard','calculation','cheatsheet') or body.count not in (4,6,8,10) or not body.message.strip():
                    raise HTTPException(400, 'Enter a topic and choose a supported study format.')
                ids = list(dict.fromkeys(body.agentIds))
                members = {r['user_id'] for r in db.execute('SELECT user_id FROM group_members WHERE group_id=?',(gid,))}
                if not set(ids)<=members:
                    raise HTTPException(400, 'Choose teachers who belong to this group.')
                if db.execute("SELECT id FROM jobs WHERE kind='classroom' AND status IN ('queued','running') AND json_extract(params,'$.groupId')=?",(gid,)).fetchone():
                    raise HTTPException(409, 'The teachers are busy. Wait or cancel your request.')
                shared = [r['id'] for r in db.execute('SELECT id FROM group_sets WHERE group_id=? ORDER BY created DESC LIMIT 40',(gid,))]
                turn_id, job_id = uid(), uid()
                params = {'turnId': turn_id, 'groupId': gid, 'requesterId': user['id'], 'prompt': body.message.strip(),
                          'agentIds': ids, 'action': body.action, 'count': body.count, 'sharedSnapshot': shared}
                db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (job_id,'classroom','','queued','Teachers are preparing',0,4,0,json.dumps(params),None,None,time.time()))
                db.execute('INSERT INTO classroom_turns VALUES(?,?,?,?,?,?,?)',
                    (turn_id,gid,user['id'],body.requestId,job_id,json.dumps({'prompt':body.message.strip(),'action':body.action,'replies':[]}),time.time()))
            if run_jobs:
                self.engine.submit(job_id)
            return {'turnId':turn_id, 'jobId':job_id}
