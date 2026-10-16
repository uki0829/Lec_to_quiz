import json
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient
from app import create_app
from accounts import COOKIE, password_matches
from test_app import FakeAI, prepared_notes, generate


@pytest.fixture
def social(tmp_path):
    app=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(app) as alice:
        bob=TestClient(app)
        for client,name in [(alice,'Alice'),(bob,'Bob')]:
            result=client.post('/api/auth/register',json={'name':name,'email':name.lower()+'@example.test','password':'StudyDemo!123'})
            assert result.status_code==200
            assert 'httponly' in result.headers['set-cookie'].lower()
        yield app,alice,bob
        bob.close()


def test_signin_sessions_and_hashes(social):
    app,alice,bob=social;store=app.state.store
    user=alice.get('/api/auth/me').json()['user']
    row=store.one('SELECT * FROM users WHERE id=?',(user['id'],))
    assert row['password_hash']!='StudyDemo!123'
    assert password_matches('StudyDemo!123',row['password_hash'])
    assert not password_matches('WrongPassword',row['password_hash'])
    token=alice.cookies.get(COOKIE)
    assert store.one('SELECT token_hash FROM user_sessions WHERE user_id=?',(user['id'],))['token_hash']!=token
    assert 'password_hash' not in user and 'google_sub' not in user
    alice.post('/api/auth/logout')
    assert alice.get('/api/collections').status_code==401
    assert alice.get('/api/auth/me').json()['user'] is None
    assert alice.post('/api/auth/login',json={'email':'alice@example.test','password':'WrongPassword'}).status_code==401
    assert alice.post('/api/auth/login',json={'email':'alice@example.test','password':'StudyDemo!123'}).status_code==200


def test_rename_account_is_private_validated_and_persistent(social):
    app, alice, bob = social
    before = alice.get('/api/auth/me').json()['user']
    renamed = alice.patch('/api/auth/me', json={'name': '  Hefeng 张  ', 'id': bob.get('/api/auth/me').json()['user']['id']})
    assert renamed.status_code == 200
    user = renamed.json()['user']
    assert user['name'] == 'Hefeng 张'
    assert user['id'] == before['id'] and user['email'] == before['email']
    assert bob.get('/api/auth/me').json()['user']['name'] == 'Bob'
    for name in ['', '   ', 'x' * 81, 'Name\nOther']:
        assert alice.patch('/api/auth/me', json={'name': name}).status_code in (400, 422)
    assert alice.get('/api/auth/me').json()['user']['name'] == 'Hefeng 张'
    alice.post('/api/auth/logout')
    assert alice.patch('/api/auth/me', json={'name': 'Anonymous'}).status_code == 401
    result = alice.post('/api/auth/login', json={'email': 'alice@example.test', 'password': 'StudyDemo!123'})
    assert result.json()['user']['name'] == 'Hefeng 张'


def test_private_study_access_and_shared_progress(social):
    app,alice,bob=social;engine=app.state.engine
    mid=prepared_notes(alice,engine);quiz=generate(alice,engine,mid)
    cid=app.state.store.collection_for(mid)
    sid=app.state.store.sources(mid)[0]['id']
    assert len(alice.get('/api/collections').json()['collections'])==1
    assert bob.get('/api/collections').json()['collections']==[]
    assert bob.get('/api/quizzes').json()['quizzes']==[]
    assert bob.get('/api/materials').json()['materials']==[]
    for path in [f'/api/collections/{cid}',f'/api/materials/{mid}',f'/api/sources/{sid}',f'/api/quizzes/{quiz["id"]}']:
        assert bob.get(path).status_code==404
    assert bob.post('/api/materials',data={'collectionId':cid,'notes':'Wrong owner'}).status_code==404
    assert bob.post('/api/quizzes',json={'collectionId':cid,'prompt':'Generate a quiz'}).status_code==404
    group=alice.post('/api/groups',json={'name':'Exam buddies'}).json()
    share=alice.post(f'/api/groups/{group["id"]}/share',json={'quizId':quiz['id']}).json()['shareId']
    assert bob.get(f'/api/groups/{group["id"]}').status_code==404
    assert bob.get(f'/api/shared-sets/{share}').status_code==404
    assert bob.post('/api/groups/join',json={'code':group['invite_code']}).status_code==200
    shared=bob.get(f'/api/shared-sets/{share}').json()
    assert shared['mode']=='shared'
    assert 'request' not in shared and 'materialId' not in shared
    assert all('id' not in q['source'] for q in shared['questions'])
    assert bob.get(f'/api/quizzes/{quiz["id"]}').status_code==404
    progress={'index':0,'answers':{shared['questions'][0]['id']:{'submitted':True,'correct':True}}}
    assert bob.put(f'/api/shared-sets/{share}/progress',json=progress).status_code==200
    assert bob.get(f'/api/shared-sets/{share}').json()['progress']==progress
    assert alice.get(f'/api/shared-sets/{share}').json()['progress']=={}
    assert alice.get(f'/api/quizzes/{quiz["id"]}').json()['progress']=={}
    assert bob.put(f'/api/shared-sets/{share}/progress',json={'index':0,'answers':{'foreign':{}}}).status_code==400
    # The snapshot remains usable when its author changes their private quiz.
    app.state.store.execute('DELETE FROM quizzes WHERE id=?',(quiz['id'],))
    assert bob.get(f'/api/shared-sets/{share}').status_code==200


def test_all_formats_share_without_raw_files(social):
    app,alice,bob=social;store=app.state.store
    mid=prepared_notes(alice,app.state.engine)
    group=alice.post('/api/groups',json={'name':'Course group'}).json()
    fixtures=json.loads((__import__('pathlib').Path(__file__).parents[1]/'fixtures/demo-group-sets.json').read_text())
    for fixture in fixtures:
        q=store.add_quiz(mid,fixture)
        result=alice.post(f'/api/groups/{group["id"]}/share',json={'quizId':q['id']})
        assert result.status_code==201
        payload=alice.get('/api/shared-sets/'+result.json()['shareId']).json()
        assert payload['format']==fixture['format']
        assert 'original_quiz_id' not in payload
    assert len(alice.get('/api/groups/'+group['id']).json()['sets'])==3
    assert bob.post(f'/api/groups/{group["id"]}/share',json={'quizId':q['id']}).status_code==404


def test_demo_and_google_configuration(tmp_path,monkeypatch):
    monkeypatch.delenv('GOOGLE_CLIENT_ID',raising=False);monkeypatch.delenv('GOOGLE_CLIENT_SECRET',raising=False)
    app=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(app) as client:
        assert client.get('/api/config').status_code==401
        assert not client.get('/api/auth/me').json()['googleConfigured']
        response=client.get('/api/auth/google/start',follow_redirects=False)
        assert response.headers['location']=='/?authError=google-setup'
        assert client.get('/api/auth/google/callback?state=invalid&code=invalid',follow_redirects=False).headers['location']=='/?authError=google-session'
        assert client.post('/api/auth/demo').json()['user']['demo']==1
        group=client.get('/api/groups').json()['groups'][0]
        assert group['demo']==1 and group['setCount']==3
        member=client.get('/api/groups/'+group['id']).json()['members']
        assert all(m['demo'] for m in member)


def test_google_start_uses_state_nonce_and_pkce(tmp_path,monkeypatch):
    from urllib.parse import urlparse,parse_qs
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','test-secret')
    app=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(app) as client:
        response=client.get('/api/auth/google/start',follow_redirects=False)
        query=parse_qs(urlparse(response.headers['location']).query)
        assert query['scope']==['openid email profile']
        assert query['code_challenge_method']==['S256']
        assert query['state'][0]==client.cookies.get('lecture_lab_oauth')
        assert query['nonce'][0]
        assert 'test-secret' not in response.headers['location']
        assert app.state.store.one('SELECT state_hash FROM oauth_states')['state_hash']!=query['state'][0]


def test_google_callback_verifies_identity_and_rejects_replay(tmp_path,monkeypatch):
    from google.oauth2 import id_token
    from urllib.parse import urlparse,parse_qs
    import accounts
    monkeypatch.setenv('GOOGLE_CLIENT_ID','test-client');monkeypatch.setenv('GOOGLE_CLIENT_SECRET','test-secret')
    app=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    class TokenResponse:
        def raise_for_status(self):pass
        def json(self):return {'id_token':'fixture-token'}
    class TokenClient:
        def __init__(self,*args,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,data):
            assert url=='https://oauth2.googleapis.com/token'
            assert data['code_verifier']
            return TokenResponse()
    monkeypatch.setattr(accounts.httpx,'AsyncClient',TokenClient)
    with TestClient(app) as client:
        location=client.get('/api/auth/google/start',follow_redirects=False).headers['location']
        query=parse_qs(urlparse(location).query)
        def verify(token,request,audience,clock_skew_in_seconds=0):
            assert token=='fixture-token' and audience=='test-client'
            assert clock_skew_in_seconds == 30
            return {'sub':'fixture-google-user','email':'verified@example.test','name':'Verified student','email_verified':True,'nonce':query['nonce'][0]}
        monkeypatch.setattr(id_token,'verify_oauth2_token',verify)
        callback='/api/auth/google/callback?state='+query['state'][0]+'&code=fixture-code'
        assert client.get(callback,follow_redirects=False).headers['location']=='/'
        user=client.get('/api/auth/me').json()['user']
        assert user['provider']=='google' and user['email']=='verified@example.test'
        assert client.get(callback,follow_redirects=False).headers['location']=='/?authError=google-session'
        assert app.state.store.one('SELECT * FROM oauth_states') is None


def test_throttle_and_existing_database_migration(tmp_path):
    from storage import Store
    store=Store(tmp_path)
    cid=store.add_collection('Earlier lecture')
    app=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(app) as client:
        for _ in range(10):
            assert client.post('/api/auth/login',json={'email':'missing@example.test','password':'WrongPassword'}).status_code==401
        assert client.post('/api/auth/login',json={'email':'missing@example.test','password':'WrongPassword'}).status_code==429
        client.post('/api/auth/demo')
        assert any(c['id']==cid for c in client.get('/api/collections').json()['collections'])
        user=client.get('/api/auth/me').json()['user']['id']
        group=client.post('/api/groups',json={'name':'Persistent group'}).json()['id']
        session=client.cookies.get(COOKIE)
    second=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(second) as client:
        client.cookies.set(COOKIE,session)
        assert client.get('/api/auth/me').json()['user']['id']==user
        assert client.get('/api/groups/'+group).status_code==200



def test_owner_leaves_and_transfers_group_preserving_shared_work(social):
    app,alice,bob=social;store=app.state.store
    mid=prepared_notes(alice,app.state.engine);quiz=generate(alice,app.state.engine,mid)
    group=alice.post('/api/groups',json={'name':'Keep studying'}).json();gid=group['id']
    shared=alice.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).json()['shareId']
    bob.post('/api/groups/join',json={'code':group['invite_code']})
    bob_id=bob.get('/api/auth/me').json()['user']['id']
    progress={'index':0,'answers':{quiz['questions'][0]['id']:{'submitted':True}}}
    for client in (alice,bob):
        assert client.put(f'/api/shared-sets/{shared}/progress',json=progress).status_code==200
    result=alice.post(f'/api/groups/{gid}/leave')
    assert result.status_code==200
    assert result.json()=={'left':True,'groupId':gid,'ownerId':bob_id,'groupRemoved':False,'deletedShareIds':[]}
    assert alice.get(f'/api/groups/{gid}').status_code==404
    assert alice.get(f'/api/shared-sets/{shared}').status_code==404
    assert alice.get('/api/groups').json()['groups']==[]
    assert len(bob.get(f'/api/groups/{gid}').json()['members'])==1
    assert bob.get(f'/api/shared-sets/{shared}').json()['progress']==progress
    assert len(store.all('SELECT * FROM shared_progress WHERE share_id=?',(shared,)))==2
    assert alice.get(f'/api/quizzes/{quiz["id"]}').status_code==200
    assert alice.get(f'/api/materials/{mid}').status_code==200
    # Leaving is reversible through the unchanged invite code, without reclaiming ownership.
    assert alice.post('/api/groups/join',json={'code':group['invite_code']}).status_code==200
    assert alice.get(f'/api/groups/{gid}').json()['owner_id']==bob_id
    assert alice.get(f'/api/shared-sets/{shared}').json()['progress']==progress


def test_member_leave_keeps_owner_and_rejoining_changes_succession_order(social):
    app,alice,bob=social;store=app.state.store
    group=alice.post('/api/groups',json={'name':'Ordered group'}).json();gid=group['id']
    bob.post('/api/groups/join',json={'code':group['invite_code']})
    with TestClient(app) as charlie:
        charlie.post('/api/auth/register',json={'name':'Charlie','email':'charlie@example.test','password':'StudyDemo!123'})
        charlie_id=charlie.get('/api/auth/me').json()['user']['id']
        charlie.post('/api/groups/join',json={'code':group['invite_code']})
        # Compatibility DELETE means leave, including for ordinary members.
        response=bob.delete(f'/api/groups/{gid}')
        assert response.status_code==200 and response.json()['ownerId']==group['owner_id']
        assert len(alice.get(f'/api/groups/{gid}').json()['members'])==2
        assert bob.post('/api/groups/join',json={'code':group['invite_code']}).status_code==200
        assert alice.post(f'/api/groups/{gid}/leave').json()['ownerId']==charlie_id
        assert bob.get(f'/api/groups/{gid}').json()['owner_id']==charlie_id


def test_owner_handoff_uses_join_order_with_stable_ties(social):
    app,alice,bob=social;store=app.state.store
    group=alice.post('/api/groups',json={'name':'Join order'}).json();gid=group['id']
    bob.post('/api/groups/join',json={'code':group['invite_code']})
    bob_id=bob.get('/api/auth/me').json()['user']['id']
    with TestClient(app) as charlie:
        charlie.post('/api/auth/register',json={'name':'Charlie','email':'charlie@example.test','password':'StudyDemo!123'})
        charlie.post('/api/groups/join',json={'code':group['invite_code']})
        store.execute('UPDATE group_members SET joined=100 WHERE group_id=?',(gid,))
        assert alice.post(f'/api/groups/{gid}/leave').json()['ownerId']==bob_id


def test_leaving_requires_authenticated_membership(social):
    app,alice,bob=social
    group=alice.post('/api/groups',json={'name':'Members only'}).json();gid=group['id']
    assert bob.post(f'/api/groups/{gid}/leave').status_code==404
    assert bob.delete(f'/api/groups/{gid}').status_code==404
    assert alice.get(f'/api/groups/{gid}').status_code==200
    bob.post('/api/auth/logout')
    assert bob.post(f'/api/groups/{gid}/leave').status_code==401


def test_last_member_leave_cleans_empty_group_only(social):
    app,alice,bob=social;store=app.state.store
    mid=prepared_notes(alice,app.state.engine);quiz=generate(alice,app.state.engine,mid)
    group=alice.post('/api/groups',json={'name':'Solo group'}).json();gid=group['id']
    other=alice.post('/api/groups',json={'name':'Another group'}).json()['id']
    shared=alice.post(f'/api/groups/{gid}/share',json={'quizId':quiz['id']}).json()['shareId']
    progress={'index':0,'answers':{}}
    alice.put(f'/api/shared-sets/{shared}/progress',json=progress)
    result=alice.post(f'/api/groups/{gid}/leave').json()
    assert result['groupRemoved'] and result['ownerId'] is None
    for table,column in [('study_groups','id'),('group_members','group_id'),('group_sets','group_id')]:
        assert not store.all(f'SELECT * FROM {table} WHERE {column}=?',(gid,))
    assert not store.all('SELECT * FROM shared_progress WHERE share_id=?',(shared,))
    assert alice.get(f'/api/quizzes/{quiz["id"]}').status_code==200
    assert alice.get(f'/api/materials/{mid}').status_code==200
    assert alice.get(f'/api/groups/{other}').status_code==200
    assert alice.post('/api/groups/join',json={'code':group['invite_code']}).status_code==404
    assert alice.post(f'/api/groups/{gid}/leave').status_code==404


def test_demo_leave_and_ownership_transfer_persist_after_restart(tmp_path):
    app=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(app) as client:
        client.post('/api/auth/demo')
        response=client.post('/api/groups/demo-study-group/leave')
        assert response.status_code==200 and response.json()['ownerId']=='demo-mia'
        assert client.get('/api/groups').json()['groups']==[]
    restarted=create_app(tmp_path,ai=FakeAI(),run_jobs=False)
    with TestClient(restarted) as client:
        client.post('/api/auth/demo')
        assert client.get('/api/groups').json()['groups']==[]
        store=restarted.state.store
        assert store.one("SELECT owner_id FROM study_groups WHERE id='demo-study-group'")['owner_id']=='demo-mia'
        assert len(store.all("SELECT * FROM group_members WHERE group_id='demo-study-group'"))==1
        assert len(store.all("SELECT * FROM group_sets WHERE group_id='demo-study-group'"))==3


@pytest.mark.parametrize('failure,expected', [
    ('network', 'google-network'),
    ('invalid_client', 'google-setup'),
    ('invalid_grant', 'google-retry'),
    ('identity', 'google-verify'),
])
def test_google_failure_details_are_actionable_and_logs_exclude_secrets(tmp_path, monkeypatch, caplog, failure, expected):
    from urllib.parse import urlparse, parse_qs
    from google.oauth2 import id_token
    import accounts
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'fixture-client')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'secret-must-not-be-logged')
    app = create_app(tmp_path, ai=FakeAI(), run_jobs=False)
    class TokenClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, data):
            request = accounts.httpx.Request('POST', url)
            if failure == 'network':
                raise accounts.httpx.ConnectError('secret-must-not-be-logged', request=request)
            if failure == 'identity':
                return accounts.httpx.Response(200, json={'id_token': 'private-token'}, request=request)
            return accounts.httpx.Response(400, json={'error': failure, 'error_description': 'secret-must-not-be-logged'}, request=request)
    monkeypatch.setattr(accounts.httpx, 'AsyncClient', TokenClient)
    def failed_identity(*args, **kwargs):
        raise ValueError('private-token secret-must-not-be-logged')
    monkeypatch.setattr(id_token, 'verify_oauth2_token', failed_identity)
    with TestClient(app) as client:
        start = client.get('/api/auth/google/start', follow_redirects=False)
        state = parse_qs(urlparse(start.headers['location']).query)['state'][0]
        with caplog.at_level('WARNING', logger='accounts'):
            result = client.get('/api/auth/google/callback', params={'state': state, 'code': 'private-code'}, follow_redirects=False)
        assert result.headers['location'] == '/?authError=' + expected
        assert client.get('/api/auth/me').json()['user'] is None
        assert app.state.store.one('SELECT * FROM oauth_states') is None
        assert 'Google sign-in failed: stage=' in caplog.text
        for secret in ('private-token', 'private-code', 'secret-must-not-be-logged'):
            assert secret not in caplog.text


@pytest.mark.parametrize('issued_offset,audience,expected', [
    (2, 'fixture-client', '/'),
    (120, 'fixture-client', '/?authError=google-verify'),
    (2, 'wrong-client', '/?authError=google-verify'),
    (-4000, 'fixture-client', '/?authError=google-verify'),
])
def test_google_real_token_verifier_bounds_clock_drift(tmp_path, monkeypatch, issued_offset, audience, expected):
    import datetime
    import time
    from urllib.parse import urlparse, parse_qs
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from google.auth import crypt, jwt, _helpers
    from google.oauth2 import id_token
    import accounts
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    now = int(time.time())
    monkeypatch.setattr(_helpers, 'utcnow', lambda: datetime.datetime.fromtimestamp(now, datetime.timezone.utc).replace(tzinfo=None))
    monkeypatch.setattr(id_token, '_fetch_certs', lambda *args: {'fixture-key': public})
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'fixture-client')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'fixture-secret')
    token = None
    class TokenClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, data):
            return accounts.httpx.Response(200, json={'id_token': token}, request=accounts.httpx.Request('POST', url))
    monkeypatch.setattr(accounts.httpx, 'AsyncClient', TokenClient)
    app = create_app(tmp_path, ai=FakeAI(), run_jobs=False)
    with TestClient(app) as client:
        start = client.get('/api/auth/google/start', follow_redirects=False)
        query = parse_qs(urlparse(start.headers['location']).query)
        token = jwt.encode(crypt.RSASigner.from_string(private, key_id='fixture-key'), {
            'iss': 'https://accounts.google.com', 'aud': audience, 'sub': 'fixture-sub',
            'email': 'clock@example.test', 'email_verified': True, 'nonce': query['nonce'][0],
            'iat': now + issued_offset, 'exp': now + issued_offset + 3600,
        }).decode()
        result = client.get('/api/auth/google/callback', params={'state': query['state'][0], 'code': 'fixture-code'}, follow_redirects=False)
        assert result.headers['location'] == expected
        user = client.get('/api/auth/me').json()['user']
        assert bool(user) == (expected == '/')
