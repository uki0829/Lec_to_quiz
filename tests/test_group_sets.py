import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app import create_app
from test_accounts_groups import social
from test_app import FakeAI, prepared_notes, generate


def test_duplicate_shares_are_blocked_by_identity_and_scoped_to_group(social):
    app,alice,bob=social;store=app.state.store
    mid=prepared_notes(alice,app.state.engine);quiz=generate(alice,app.state.engine,mid)
    group=alice.post('/api/groups',json={'name':'First group'}).json();gid=group['id']
    share=alice.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']})
    assert share.status_code==201
    assert alice.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).status_code==409
    assert alice.patch('/api/quizzes/'+quiz['id'],json={'title':'Renamed original'}).status_code==200
    assert alice.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).status_code==409
    assert alice.get(f'/api/groups/{gid}').json()['addedQuizIds']==[quiz['id']]
    bob.post('/api/groups/join',json={'code':group['invite_code']})
    assert bob.get(f'/api/groups/{gid}').json()['addedQuizIds']==[]
    assert all('originalQuizId' not in s for s in bob.get(f'/api/groups/{gid}').json()['sets'])
    other=alice.post('/api/groups',json={'name':'Other group'}).json()['id']
    assert alice.post(f'/api/groups/{other}/share',json={'quizId':quiz['id']}).status_code==201
    # Equal titles do not establish that two independently saved quizzes are duplicates.
    separate=store.add_quiz(mid,{**quiz,'title':'Renamed original'})
    assert alice.post(f'/api/groups/{gid}/share',json={'quizId':separate['id']}).status_code==201
    assert len(alice.get(f'/api/groups/{gid}').json()['sets'])==2


def test_only_group_owner_removes_copy_and_progress_preserving_original(social):
    app,alice,bob=social;store=app.state.store
    group=alice.post('/api/groups',json={'name':'Study circle'}).json();gid=group['id']
    bob.post('/api/groups/join',json={'code':group['invite_code']})
    mid=prepared_notes(bob,app.state.engine);quiz=generate(bob,app.state.engine,mid)
    sid=bob.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).json()['shareId']
    progress={'index':0,'answers':{quiz['questions'][0]['id']:{'submitted':True}}}
    for member in (alice,bob):
        assert member.put(f'/api/shared-sets/{sid}/progress',json=progress).status_code==200
    assert bob.delete(f'/api/groups/{gid}/sets/{sid}').status_code==403
    other=alice.post('/api/groups',json={'name':'Keep group'}).json()['id']
    assert alice.delete(f'/api/groups/{other}/sets/{sid}').status_code==404
    assert alice.delete(f'/api/groups/{gid}/sets/{sid}').status_code==200
    assert not store.all('SELECT * FROM group_sets WHERE id=?',(sid,))
    assert not store.all('SELECT * FROM shared_progress WHERE share_id=?',(sid,))
    assert alice.get(f'/api/groups/{gid}').json()['sets']==[]
    assert bob.get(f'/api/groups/{gid}').json()['addedQuizIds']==[]
    assert bob.get(f'/api/quizzes/{quiz["id"]}').status_code==200
    assert bob.get(f'/api/materials/{mid}').status_code==200
    assert bob.get(f'/api/shared-sets/{sid}').status_code==404
    assert bob.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).status_code==201
    assert alice.delete(f'/api/groups/{gid}/sets/{sid}').status_code==404


def test_owner_handoff_changes_set_deletion_permissions(social):
    app,alice,bob=social
    mid=prepared_notes(alice,app.state.engine);quiz=generate(alice,app.state.engine,mid)
    group=alice.post('/api/groups',json={'name':'Transfer'}).json();gid=group['id']
    sid=alice.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).json()['shareId']
    assert bob.delete(f'/api/groups/{gid}/sets/{sid}').status_code==404
    bob.post('/api/groups/join',json={'code':group['invite_code']})
    alice.post(f'/api/groups/{gid}/leave')
    alice.post('/api/groups/join',json={'code':group['invite_code']})
    assert alice.delete(f'/api/groups/{gid}/sets/{sid}').status_code==403
    assert bob.delete(f'/api/groups/{gid}/sets/{sid}').status_code==200
    bob.post('/api/auth/logout')
    assert bob.delete(f'/api/groups/{gid}/sets/{sid}').status_code==401


def test_concurrent_share_requests_create_one_snapshot(social):
    app,alice,bob=social
    mid=prepared_notes(alice,app.state.engine);quiz=generate(alice,app.state.engine,mid)
    gid=alice.post('/api/groups',json={'name':'Concurrent clicks'}).json()['id']
    def share(_):
        client=TestClient(app);client.cookies.update(alice.cookies)
        try:return client.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).status_code
        finally:client.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(share,range(2)))==[201,409]
    assert len(alice.get(f'/api/groups/{gid}').json()['sets'])==1
    row=app.state.store.one('SELECT * FROM group_sets WHERE group_id=?',(gid,))
    with pytest.raises(sqlite3.IntegrityError),app.state.store.connect() as db:
        db.execute('INSERT INTO group_sets VALUES(?,?,?,?,?,?,?)',('forged',gid,row['author_id'],quiz['id'],row['body'],row['created'],0))


def test_existing_duplicates_merge_compatible_progress_with_backup(tmp_path):
    app=create_app(tmp_path,ai=FakeAI(),run_jobs=False);store=app.state.store
    with TestClient(app) as client:
        client.post('/api/auth/demo')
        mid=prepared_notes(client,app.state.engine);quiz=generate(client,app.state.engine,mid)
        gid=client.post('/api/groups',json={'name':'Existing duplicates'}).json()['id']
        sid=client.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).json()['shareId']
        row=store.one('SELECT * FROM group_sets WHERE id=?',(sid,))
        with store.connect() as db:
            db.execute('DROP INDEX group_set_original_unique')
            db.execute('INSERT INTO group_sets VALUES(?,?,?,?,?,?,?)',('repeat',gid,row['author_id'],quiz['id'],row['body'],row['created']+1,0))
        q0,q1=quiz['questions'][:2]
        client.put(f'/api/shared-sets/{sid}/progress',json={'index':0,'answers':{q0['id']:{'submitted':True,'value':0}}})
        client.put('/api/shared-sets/repeat/progress',json={'index':1,'answers':{q1['id']:{'submitted':True,'value':1}}})
    restarted=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(restarted) as client:
        client.post('/api/auth/demo')
        assert [s['id'] for s in client.get(f'/api/groups/{gid}').json()['sets']]==[sid]
        assert set(client.get(f'/api/shared-sets/{sid}').json()['progress']['answers'])=={q0['id'],q1['id']}
        assert client.get(f'/api/quizzes/{quiz["id"]}').status_code==200
        assert client.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).status_code==409
    with sqlite3.connect(tmp_path/'lecture_lab.pre_group_unique.sqlite3') as backup:
        assert backup.execute('SELECT count(*) FROM group_sets WHERE group_id=?',(gid,)).fetchone()[0]==2
        assert backup.execute("SELECT count(*) FROM shared_progress WHERE share_id='repeat'").fetchone()[0]==1


def test_trash_target_is_outside_hidden_library_and_group_panels():
    from html.parser import HTMLParser
    from pathlib import Path
    class Parents(HTMLParser):
        def __init__(self):
            super().__init__();self.stack=[];self.trash=None
        def handle_starttag(self,tag,attrs):
            ident=dict(attrs).get('id')
            if ident=='set-trash':self.trash=[i for _,i in self.stack]
            if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
                self.stack.append((tag,ident))
        def handle_endtag(self,tag):
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i][0]==tag:
                    self.stack=self.stack[:i];break
    parser=Parents();parser.feed((Path(__file__).parents[1]/'source/page.html').read_text())
    assert parser.trash and 'main-content' in parser.trash
    assert not set(parser.trash)&{'library-view','groups-view','study-view','sets-panel','materials-panel'}


def test_collection_picker_flags_existing_sets_for_selected_group_only(social):
    app,alice,bob=social;store=app.state.store
    mid=prepared_notes(alice,app.state.engine);quiz=generate(alice,app.state.engine,mid)
    cid=store.collection_for(mid)
    group=alice.post('/api/groups',json={'name':'Picker group'}).json();gid=group['id']
    other=alice.post('/api/groups',json={'name':'Another picker group'}).json()['id']
    sid=alice.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).json()['shareId']
    def listed(client,group_id):
        return client.get('/api/quizzes',params={'collectionId':cid,'groupId':group_id})
    assert listed(alice,gid).json()['quizzes'][0]['alreadyShared'] is True
    assert listed(alice,other).json()['quizzes'][0]['alreadyShared'] is False
    assert 'alreadyShared' not in alice.get('/api/quizzes',params={'collectionId':cid}).json()['quizzes'][0]
    assert bob.get('/api/quizzes',params={'groupId':gid}).status_code==404
    bob.post('/api/groups/join',json={'code':group['invite_code']})
    assert listed(bob,gid).status_code==404
    assert bob.get('/api/quizzes',params={'groupId':gid}).json()['quizzes']==[]
    assert alice.get(f'/api/shared-sets/{sid}').json()['groupId']==gid
    assert alice.delete(f'/api/groups/{gid}/sets/{sid}').status_code==200
    assert listed(alice,gid).json()['quizzes'][0]['alreadyShared'] is False
