import copy
import json
import sqlite3
import threading

import pytest
import tiktoken
from fastapi.testclient import TestClient

from app import create_app
from retrieval import Retriever, split_text
from storage import Store
from test_app import FakeAI, NOTES, complete, setup, generate, prepared_notes


def collection(client, name='Machine Learning'):
    r=client.post('/api/collections', json={'name':name})
    assert r.status_code==201,r.text
    return r.json()['id']


def add(client, engine, cid, text=NOTES):
    result,_=complete(client,engine,client.post('/api/materials',data={'notes':text,'collectionId':cid}))
    return result['materialId']


def quiz_request(client,engine,cid,**kwargs):
    data={'collectionId':cid,'prompt':'Practice gradient descent','format':'mcq','count':6,'difficulty':'beginner',**kwargs}
    _,job=complete(client,engine,client.post('/api/quizzes',json=data))
    return client.get('/api/quizzes/'+job['result']['quizId']).json()


class CrossSourceAI(FakeAI):
    embedding_model='fixture-embedding'
    def __init__(self):
        super().__init__();self.embedded=[];self.selections=[];self.params=[];self.embedding_failure=False
    def embed(self,texts):
        if self.embedding_failure:
            raise ValueError('Fixture indexing failed')
        self.embedded.extend(texts)
        return [[1.0,0.0] for _ in texts]
    def select(self,prompt,sources):
        self.selections.append((prompt,copy.deepcopy(sources)))
        return {'status':'ready','message':'','sourceIds':[s['id'] for s in sources][:12]}
    def generate(self,params,sources,validation_feedback=''):
        self.params.append(copy.deepcopy(params))
        result=super().generate(params,sources,validation_feedback)
        for i,q in enumerate(result['questions']):
            source=sources[i%len(sources)]
            q['sourceId']=source['id'];q['quote']=source['text']
            if params.get('followupContext'):
                q['prompt']='A new example: '+q['prompt']
        return result


@pytest.fixture
def rag(tmp_path):
    ai=CrossSourceAI();app=create_app(tmp_path,ai=ai,run_jobs=False)
    with TestClient(app) as client:
        yield client,app.state.store,app.state.engine,ai


def test_collection_growth_isolation_and_dependencies(rag):
    client,store,engine,ai=rag
    cid=collection(client);other=collection(client,'History')
    m1=add(client,engine,cid);q1=quiz_request(client,engine,cid)
    source1=store.sources(m1)[0]['id'];before=len(ai.embedded)
    m2=add(client,engine,cid,'A smaller learning rate takes smaller parameter steps. '+NOTES)
    add(client,engine,other,'Unrelated history material')
    q2=quiz_request(client,engine,cid)
    assert len(ai.embedded)>before
    assert source1==store.sources(m1)[0]['id']
    assert client.get('/api/quizzes/'+q1['id']).status_code==200
    material_ids={s['materialId'] for s in ai.selections[-1][1]}
    assert material_ids=={m1,m2}
    assert {s['sourceId'] for s in q2['request']['snapshot']}=={store.sources(m1)[0]['id'],store.sources(m2)[0]['id']}
    assert {q['source']['id'] for q in q2['questions']}=={store.sources(m1)[0]['id'],store.sources(m2)[0]['id']}
    for q in q2['questions']:
        assert client.get(q['source']['url']).status_code==200
    assert len(client.get('/api/quizzes?collectionId='+other).json()['quizzes'])==0
    impact=client.get('/api/materials/'+m2+'/deletion-impact').json()['quizzes']
    assert [q['id'] for q in impact]==[q2['id']]
    deletion=client.delete('/api/materials/'+m2).json()
    assert deletion['deletedQuizIds']==[q2['id']]
    assert client.get('/api/quizzes/'+q1['id']).status_code==200
    assert not store.all('SELECT * FROM chunks WHERE material_id=?',(m2,))
    assert not engine.retriever.vectors().get(where={'materialId':m2})['ids']


def test_followup_inherits_and_overrides_and_ready_snapshot(rag):
    client,store,engine,ai=rag;cid=collection(client);m1=add(client,engine,cid)
    first=quiz_request(client,engine,cid,format='flashcard',count=4,difficulty='advanced')
    m2=add(client,engine,cid,'The learning rate eta controls the step size. '+NOTES)
    pending=client.post('/api/materials',data={'collectionId':cid,'notes':'Pending material'}).json()
    _,job=complete(client,engine,client.post('/api/quizzes',json={'collectionId':cid,'parentQuizId':first['id'],'prompt':'Make another quiz with a numerical example','difficulty':'beginner'}))
    q=client.get('/api/quizzes/'+job['result']['quizId']).json()
    params=ai.params[-1]
    assert params['count']==4 and params['format']=='flashcard' and params['difficulty']=='beginner'
    assert params['followupContext']['questions']==[x['prompt'] for x in first['questions']]
    assert set(params['materialSnapshot'])=={m1,m2}
    assert q['request']['parent_quiz_id']==first['id']
    assert q['request']['submitted']['prompt']=='Make another quiz with a numerical example'
    assert client.post('/api/quizzes',json={'collectionId':collection(client,'Another course'),'parentQuizId':first['id'],'prompt':'harder'}).status_code==400
    client.post('/api/jobs/'+pending['jobId']+'/cancel');engine.run(pending['jobId'])


def test_index_retry_reuses_extraction_and_preserves_quiz(rag):
    client,store,engine,ai=rag;cid=collection(client);mid=add(client,engine,cid);q=quiz_request(client,engine,cid)
    ai.embedding_failure=True
    upload=client.post('/api/materials',data={'collectionId':cid,'notes':NOTES+' More examples.'}).json()
    engine.run(upload['jobId']);assert store.job(upload['jobId'])['status']=='failed'
    old=store.sources(upload['materialId']);assert old
    assert client.get('/api/quizzes/'+q['id']).status_code==200
    ai.embedding_failure=False
    complete(client,engine,client.post('/api/jobs/'+upload['jobId']+'/retry'))
    assert old==store.sources(upload['materialId'])
    embedded=len(ai.embedded)
    complete(client,engine,client.post('/api/materials/'+mid+'/index'))
    assert len(ai.embedded)==embedded


def test_persistence_model_change_and_cleanup_authority(rag):
    client,store,engine,ai=rag;cid=collection(client);mid=add(client,engine,cid)
    retriever=Retriever(Store(store.root),ai)
    assert retriever.is_ready(mid)
    assert retriever.search(cid,[mid],'update rule')[0]['materialId']==mid
    ai.embedding_model='fixture-embedding-v2';new=Retriever(store,ai)
    assert not new.is_ready(mid)
    new.index(mid);assert new.is_ready(mid)
    # Simulate unavailable Chroma cleanup: SQLite immediately excludes stale vectors.
    engine.retriever.cleanup=lambda:None
    client.delete('/api/materials/'+mid)
    assert store.all('SELECT id FROM vector_cleanup')
    assert retriever.search(cid,[mid],'update rule')==[]
    retriever.cleanup();assert not store.all('SELECT id FROM vector_cleanup')


def test_snapshot_and_delete_blocked_during_job(rag):
    client,store,engine,ai=rag;cid=collection(client);mid=add(client,engine,cid)
    result=client.post('/api/quizzes',json={'collectionId':cid,'prompt':'gradient descent'}).json()
    newer=add(client,engine,cid,'An extra lecture: '+NOTES)
    assert client.delete('/api/materials/'+mid).status_code==409
    engine.run(result['jobId']);assert store.job(result['jobId'])['status']=='completed'
    assert set(ai.params[-1]['materialSnapshot'])=={mid}
    client.post('/api/jobs/'+result['jobId']+'/cancel')
    assert client.delete('/api/materials/'+newer).status_code==200


def test_unicode_chunk_offsets_and_token_limit():
    text=('Gradient descent 更新参数 w ← w − η ∇L(w).\n'*400)
    windows=list(split_text(text));enc=tiktoken.get_encoding('cl100k_base')
    assert len(windows)>1 and windows[0][0]==0 and windows[-1][1]==len(text)
    for start,end,body in windows:
        assert text[start:end]==body
        assert len(enc.encode(body))<=800
    for a,b in zip(windows,windows[1:]):
        assert b[0]<a[1] and b[0]>a[0]


def test_legacy_migration_backup_and_progress(tmp_path):
    path=tmp_path/'lecture_lab.sqlite3'
    body={'id':'q','mode':'generated','title':'Saved quiz','format':'mcq','questions':[{'source':{'id':'s'}}]}
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE materials(id TEXT PRIMARY KEY,title TEXT,files TEXT,notes TEXT,status TEXT,created REAL);
        CREATE TABLE sources(id TEXT PRIMARY KEY,material_id TEXT,unit_key TEXT,body TEXT);
        CREATE TABLE jobs(id TEXT PRIMARY KEY,kind TEXT,material_id TEXT,status TEXT,stage TEXT,completed INTEGER,total INTEGER,cancel INTEGER,params TEXT,result TEXT,error TEXT,created REAL);
        CREATE TABLE quizzes(id TEXT PRIMARY KEY,material_id TEXT,body TEXT,progress TEXT,created REAL);''')
        db.execute('INSERT INTO materials VALUES(?,?,?,?,?,?)',('m','Lecture','[]',NOTES,'ready',1))
        db.execute('INSERT INTO sources VALUES(?,?,?,?)',('s','m','notes',json.dumps({'id':'s','text':NOTES})))
        db.execute('INSERT INTO quizzes VALUES(?,?,?,?,?)',('q','m',json.dumps(body),'{"index":0}',2))
        db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',('j','quiz','m','completed','Ready',1,1,0,'{"prompt":"Original request"}','{"quizId":"q"}',None,2))
    s=Store(tmp_path);q=s.quiz('q')
    assert q['id']=='q' and q['progress']=={'index':0}
    assert q['request']['submitted']['prompt']=='Original request'
    assert len(s.all('SELECT * FROM collections'))==1
    assert (tmp_path/'lecture_lab.pre_collections.sqlite3').exists()
    Store(tmp_path);assert len(s.all('SELECT * FROM collections'))==1


def test_library_card_metadata_and_failed_request_editing(rag):
    client,store,engine,ai=rag;cid=collection(client);add(client,engine,cid)
    q=quiz_request(client,engine,cid)
    row=client.get('/api/quizzes?collectionId='+cid).json()['quizzes'][0]
    assert row['questionCount']==6 and row['answeredCount']==0
    ai.fail_generate=True
    queued=client.post('/api/quizzes',json={'collectionId':cid,'prompt':'Create four flashcards','format':'mcq','count':4,'difficulty':'beginner'}).json()
    engine.run(queued['jobId'])
    assert store.job(queued['jobId'])['status']=='failed'
    assert client.get('/api/collections/'+cid).json()['latestQuizJob']['id']==queued['jobId']
    exposed=client.get('/api/jobs/'+queued['jobId']+'/request').json()['request']
    assert exposed['format']=='mcq' and exposed['count']==4
    assert set(exposed)<= {'collectionId','parentQuizId','prompt','format','count','difficulty'}
    assert client.get('/api/quizzes/'+q['id']).status_code==200
