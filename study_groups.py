"""Membership-scoped group libraries. Shared sets are explicit content snapshots."""
import json
import secrets
import sqlite3
import time
from pathlib import Path
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from accounts import DEMO_USER
from storage import CURRENT_USER, uid


class GroupName(BaseModel):
    name: str = Field(min_length=1,max_length=100)


class JoinCode(BaseModel):
    code: str = Field(min_length=1,max_length=80)


class ShareQuiz(BaseModel):
    quizId: str = Field(min_length=1,max_length=100)


def snapshot(quiz):
    # Share only learning content, never the owner's requests, progress, or raw files.
    body = {k:quiz[k] for k in ('title','description','format','questions','sections') if k in quiz}
    if quiz.get('grounding') == 'general':
        body['grounding'] = 'general'
    body = json.loads(json.dumps(body))
    for q in body.get('questions',[]) + body.get('sections',[]):
        for key in ('hint','starred','originQuizId','originQuestionId','hintLoading','starLoading'):
            q.pop(key,None)
        source = q.get('source',{})
        q['source'] = {k:source[k] for k in ('name','locator','quote') if k in source}
        if source.get('kind') == 'general':
            q['source']['kind'] = 'general'
    return body


class Groups:
    def __init__(self,store,accounts):
        self.store,self.accounts=store,accounts
        self.ensure_unique_shares()
        # The preview uses authored fixtures, never the user's private lecture files.
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS group_seed_state (id TEXT PRIMARY KEY)')
            if db.execute("SELECT id FROM group_seed_state WHERE id='demo-v1'").fetchone():
                return
            db.execute("INSERT OR IGNORE INTO study_groups VALUES('demo-study-group','Machine Learning Study Group','demo-hefeng','LECTURELAB',?,1)",(time.time(),))
            for user in ('demo-hefeng','demo-mia'):
                db.execute("INSERT OR IGNORE INTO group_members VALUES('demo-study-group',?,?)",(user,time.time()))
            fixtures=json.loads((Path(__file__).parent/'fixtures/demo-group-sets.json').read_text())
            for i,body in enumerate(fixtures):
                db.execute("INSERT OR IGNORE INTO group_sets VALUES(?,'demo-study-group',?,NULL,?,?,1)",
                           ('demo-shared-'+str(i),'demo-mia' if i!=1 else DEMO_USER,json.dumps(snapshot(body)),time.time()-i*60))
            db.execute("INSERT INTO group_seed_state VALUES('demo-v1')")

    def ensure_unique_shares(self):
        if self.store.one("SELECT name FROM sqlite_master WHERE type='index' AND name='group_set_original_unique'"):
            return
        duplicates=self.store.all('SELECT group_id,original_quiz_id FROM group_sets WHERE original_quiz_id IS NOT NULL GROUP BY group_id,original_quiz_id HAVING count(*)>1')
        if duplicates:
            backup=self.store.root/'lecture_lab.pre_group_unique.sqlite3'
            if not backup.exists():
                with sqlite3.connect(self.store.path) as source, sqlite3.connect(backup) as target:
                    source.backup(target)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for duplicate in duplicates:
                rows=db.execute('SELECT * FROM group_sets WHERE group_id=? AND original_quiz_id=? ORDER BY created,rowid',
                                (duplicate['group_id'],duplicate['original_quiz_id'])).fetchall()
                if not rows:continue
                kept=rows[0];questions={q['id']:q for q in json.loads(kept['body']).get('questions',[])}
                for removed in rows[1:]:
                    other_questions={q['id']:q for q in json.loads(removed['body']).get('questions',[])}
                    compatible={qid for qid,q in questions.items() if other_questions.get(qid)==q}
                    for progress in db.execute('SELECT * FROM shared_progress WHERE share_id=?',(removed['id'],)).fetchall():
                        existing=db.execute('SELECT progress FROM shared_progress WHERE share_id=? AND user_id=?',(kept['id'],progress['user_id'])).fetchone()
                        base=json.loads(existing['progress']) if existing else {'index':0,'answers':{}}
                        incoming=json.loads(progress['progress'])
                        answers=base.setdefault('answers',{})
                        for qid,answer in incoming.get('answers',{}).items():
                            if qid in compatible and (qid not in answers or (answer.get('submitted') and not answers[qid].get('submitted'))):
                                answers[qid]=answer
                        db.execute('INSERT OR REPLACE INTO shared_progress VALUES(?,?,?)',(kept['id'],progress['user_id'],json.dumps(base)))
                    db.execute('DELETE FROM shared_progress WHERE share_id=?',(removed['id'],))
                    db.execute('DELETE FROM group_sets WHERE id=?',(removed['id'],))
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS group_set_original_unique ON group_sets(group_id,original_quiz_id) WHERE original_quiz_id IS NOT NULL')

    def member(self,gid,db=None):
        user=CURRENT_USER.get()
        sql='SELECT g.* FROM study_groups g JOIN group_members m ON m.group_id=g.id WHERE g.id=? AND m.user_id=?'
        group=db.execute(sql,(gid,user['id'])).fetchone() if db else self.store.one(sql,(gid,user['id']))
        if not group:raise HTTPException(404,'Study group not found.')
        return dict(group)

    def shared(self,sid,db=None):
        row=db.execute('SELECT * FROM group_sets WHERE id=?',(sid,)).fetchone() if db else self.store.one('SELECT * FROM group_sets WHERE id=?',(sid,))
        if not row:raise HTTPException(404,'Shared set not found.')
        self.member(row['group_id'],db)
        return dict(row)

    def routes(self,app):
        @app.get('/api/groups')
        def listing():
            rows=self.store.all('SELECT g.*,(SELECT count(*) FROM group_members WHERE group_id=g.id) AS memberCount,(SELECT count(*) FROM group_sets WHERE group_id=g.id) AS setCount FROM study_groups g JOIN group_members m ON m.group_id=g.id WHERE m.user_id=? ORDER BY g.created DESC',(CURRENT_USER.get()['id'],))
            return {'groups':rows}

        @app.post('/api/groups',status_code=201)
        def create(body:GroupName):
            if not body.name.strip():raise HTTPException(400,'Enter a group name.')
            gid=uid();user=CURRENT_USER.get()['id']
            with self.store.connect() as db:
                db.execute('INSERT INTO study_groups VALUES(?,?,?,?,?,0)',(gid,body.name.strip(),user,secrets.token_urlsafe(7),time.time()))
                db.execute('INSERT INTO group_members VALUES(?,?,?)',(gid,user,time.time()))
            return self.member(gid)

        @app.post('/api/groups/join')
        def join(body:JoinCode):
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                group=db.execute('SELECT * FROM study_groups WHERE invite_code=?',(body.code.strip(),)).fetchone()
                if not group:raise HTTPException(404,'Check the invite code and try again.')
                db.execute('INSERT OR IGNORE INTO group_members VALUES(?,?,?)',(group['id'],CURRENT_USER.get()['id'],time.time()))
                return self.member(group['id'],db)

        # The old DELETE route also leaves membership, so cached clients cannot
        # remove a group that still has other members.
        @app.delete('/api/groups/{gid}', include_in_schema=False)
        @app.post('/api/groups/{gid}/leave')
        def leave(gid:str):
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                group=self.member(gid,db)
                user_id=CURRENT_USER.get()['id']
                db.execute('DELETE FROM group_members WHERE group_id=? AND user_id=?',(gid,user_id))
                successor=db.execute('SELECT user_id FROM group_members WHERE group_id=? ORDER BY joined,rowid LIMIT 1',(gid,)).fetchone()
                owner_id=group['owner_id'];shares=[]
                if successor:
                    if owner_id==user_id:
                        owner_id=successor['user_id']
                        db.execute('UPDATE study_groups SET owner_id=? WHERE id=?',(owner_id,gid))
                else:
                    owner_id=None
                    shares=[r['id'] for r in db.execute('SELECT id FROM group_sets WHERE group_id=?',(gid,))]
                    db.execute('DELETE FROM shared_progress WHERE share_id IN (SELECT id FROM group_sets WHERE group_id=?)',(gid,))
                    db.execute('DELETE FROM group_sets WHERE group_id=?',(gid,))
                    db.execute('DELETE FROM study_groups WHERE id=?',(gid,))
                    if getattr(self.accounts, 'agents', None):
                        db.execute('DELETE FROM classroom_turns WHERE group_id=?',(gid,))
                        db.execute('DELETE FROM classroom_vectors WHERE group_id=?',(gid,))
            return {'left':True,'groupId':gid,'ownerId':owner_id,'groupRemoved':successor is None,'deletedShareIds':shares}

        @app.get('/api/groups/{gid}')
        def detail(gid:str):
            group=self.member(gid)
            members=self.store.all('SELECT u.id,u.name,u.demo FROM users u JOIN group_members m ON m.user_id=u.id WHERE m.group_id=? ORDER BY m.joined',(gid,))
            rows=self.store.all('SELECT s.*,u.name AS authorName FROM group_sets s JOIN users u ON u.id=s.author_id WHERE s.group_id=? ORDER BY s.created DESC',(gid,))
            sets=[]
            for row in rows:
                body=json.loads(row['body'])
                sets.append({'id':row['id'],'title':body['title'],'format':body['format'],'count':len(body.get('sections',[]) if body['format']=='cheatsheet' else body['questions']),
                             'authorName':row['authorName'],'authorId':row['author_id'],'demo':row['demo'],'created':row['created']})
            added=self.store.all('SELECT s.original_quiz_id AS id FROM group_sets s JOIN quiz_collections qc ON qc.quiz_id=s.original_quiz_id JOIN collection_owners o ON o.collection_id=qc.collection_id WHERE s.group_id=? AND o.user_id=?',(gid,CURRENT_USER.get()['id']))
            return {**group,'members':members,'sets':sets,'addedQuizIds':[r['id'] for r in added]}

        @app.delete('/api/groups/{gid}/sets/{sid}')
        def delete_shared(gid:str,sid:str):
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                group=self.member(gid,db)
                if group['owner_id']!=CURRENT_USER.get()['id']:
                    raise HTTPException(403,'Only the group owner can remove shared sets.')
                if not db.execute('SELECT id FROM group_sets WHERE id=? AND group_id=?',(sid,gid)).fetchone():
                    raise HTTPException(404,'Shared set not found.')
                if db.execute("SELECT id FROM jobs WHERE kind='classroom' AND status IN ('queued','running') "
                    "AND json_extract(params,'$.groupId')=? AND EXISTS (SELECT 1 FROM json_each(params,'$.sharedSnapshot') WHERE value=?)",(gid,sid)).fetchone():
                    raise HTTPException(409,'Wait for classroom teaching to finish before removing this set.')
                db.execute('DELETE FROM shared_progress WHERE share_id=?',(sid,))
                db.execute('DELETE FROM group_sets WHERE id=?',(sid,))
                if getattr(self.accounts, 'agents', None):
                    db.execute('DELETE FROM classroom_vectors WHERE group_id=? AND source_id LIKE ?', (gid,sid+':%'))
            return {'deleted':True,'shareId':sid,'groupId':gid}

        @app.post('/api/groups/{gid}/share',status_code=201)
        def share(gid:str,body:ShareQuiz):
            quiz=self.store.quiz(body.quizId)
            if not quiz or not self.accounts.owns_collection(quiz['collectionId']):
                raise HTTPException(404,'Choose one of your saved sets.')
            sid=uid()
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.member(gid,db)
                if db.execute('SELECT id FROM group_sets WHERE group_id=? AND original_quiz_id=?',(gid,body.quizId)).fetchone():
                    raise HTTPException(409,'This set is already in the group.')
                db.execute('INSERT INTO group_sets VALUES(?,?,?,?,?,?,0)',(sid,gid,CURRENT_USER.get()['id'],body.quizId,json.dumps(snapshot(quiz)),time.time()))
            return {'shareId':sid,'groupId':gid}

        @app.get('/api/shared-sets/{sid}')
        def open_shared(sid:str):
            row=self.shared(sid)
            progress=self.store.one('SELECT progress FROM shared_progress WHERE share_id=? AND user_id=?',(sid,CURRENT_USER.get()['id']))
            return {**json.loads(row['body']),'id':'shared-'+sid,'shareId':sid,'groupId':row['group_id'],'mode':'shared','demo':bool(row['demo']),
                    'progress':json.loads(progress['progress']) if progress else {}}

        @app.put('/api/shared-sets/{sid}/progress')
        async def progress(sid:str,request:Request):
            row=self.shared(sid);quiz=json.loads(row['body'])
            if quiz['format']=='cheatsheet':raise HTTPException(400,'Cheat sheets do not use progress.')
            raw=await request.body()
            if len(raw)>100000:raise HTTPException(413,'Progress is too large.')
            try:
                body=json.loads(raw);answers=body.get('answers',{})
                if not isinstance(body,dict) or not isinstance(answers,dict) or not set(answers)<={q['id'] for q in quiz['questions']} or not all(isinstance(a,dict) for a in answers.values()):raise ValueError()
                if not isinstance(body.get('index',0),int) or not 0<=body.get('index',0)<len(quiz['questions']):raise ValueError()
            except (ValueError,TypeError,AttributeError):raise HTTPException(400,'Invalid practice progress.')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                self.shared(sid,db)
                db.execute('INSERT OR REPLACE INTO shared_progress VALUES(?,?,?)',(sid,CURRENT_USER.get()['id'],json.dumps(body)))
            return {'saved':True}
