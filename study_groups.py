"""Membership-scoped group libraries. Shared sets are explicit content snapshots."""
import json
import secrets
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
    body = json.loads(json.dumps(body))
    for q in body.get('questions',[]) + body.get('sections',[]):
        for key in ('hint','starred','originQuizId','originQuestionId','hintLoading','starLoading'):
            q.pop(key,None)
        source = q.get('source',{})
        q['source'] = {k:source[k] for k in ('name','locator','quote') if k in source}
    return body


class Groups:
    def __init__(self,store,accounts):
        self.store,self.accounts=store,accounts
        # The preview uses authored fixtures, never the user's private lecture files.
        with store.connect() as db:
            db.execute("INSERT OR IGNORE INTO study_groups VALUES('demo-study-group','Machine Learning Study Group','demo-hefeng','LECTURELAB',?,1)",(time.time(),))
            for user in ('demo-hefeng','demo-mia'):
                db.execute("INSERT OR IGNORE INTO group_members VALUES('demo-study-group',?,?)",(user,time.time()))
            fixtures=json.loads((Path(__file__).parent/'fixtures/demo-group-sets.json').read_text())
            for i,body in enumerate(fixtures):
                db.execute("INSERT OR IGNORE INTO group_sets VALUES(?,'demo-study-group',?,NULL,?,?,1)",
                           ('demo-shared-'+str(i),'demo-mia' if i!=1 else DEMO_USER,json.dumps(snapshot(body)),time.time()-i*60))

    def member(self,gid):
        user=CURRENT_USER.get()
        group=self.store.one('SELECT g.* FROM study_groups g JOIN group_members m ON m.group_id=g.id WHERE g.id=? AND m.user_id=?',(gid,user['id']))
        if not group:raise HTTPException(404,'Study group not found.')
        return group

    def shared(self,sid):
        row=self.store.one('SELECT * FROM group_sets WHERE id=?',(sid,))
        if not row:raise HTTPException(404,'Shared set not found.')
        self.member(row['group_id'])
        return row

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
            group=self.store.one('SELECT * FROM study_groups WHERE invite_code=?',(body.code.strip(),))
            if not group:raise HTTPException(404,'Check the invite code and try again.')
            self.store.execute('INSERT OR IGNORE INTO group_members VALUES(?,?,?)',(group['id'],CURRENT_USER.get()['id'],time.time()))
            return self.member(group['id'])

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
            return {**group,'members':members,'sets':sets}

        @app.post('/api/groups/{gid}/share',status_code=201)
        def share(gid:str,body:ShareQuiz):
            self.member(gid)
            quiz=self.store.quiz(body.quizId)
            if not quiz or not self.accounts.owns_collection(quiz['collectionId']):
                raise HTTPException(404,'Choose one of your saved sets.')
            sid=uid()
            self.store.execute('INSERT INTO group_sets VALUES(?,?,?,?,?,?,0)',(sid,gid,CURRENT_USER.get()['id'],body.quizId,json.dumps(snapshot(quiz)),time.time()))
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
            self.store.execute('INSERT OR REPLACE INTO shared_progress VALUES(?,?,?)',(sid,CURRENT_USER.get()['id'],json.dumps(body)))
            return {'saved':True}
