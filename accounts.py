"""Local accounts and server-side sessions; Google uses verified OpenID Connect."""
import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import time
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from storage import uid, CURRENT_USER

COOKIE = 'lecture_lab_session'
DEMO_USER = 'demo-hefeng'
logger = logging.getLogger(__name__)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def public_user(row):
    return {k: row[k] for k in ('id', 'name', 'email', 'provider', 'demo')}


def password_hash(password):
    salt = secrets.token_bytes(16)
    value = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return salt.hex() + ':' + value.hex()


def password_matches(password, stored):
    if not stored:
        return False
    salt, expected = stored.split(':')
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return hmac.compare_digest(actual.hex(), expected)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default='', max_length=80)


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class Accounts:
    def __init__(self, store):
        self.store = store

    def session_user(self, request):
        token = request.cookies.get(COOKIE, '')
        row = self.store.one('SELECT u.* FROM users u JOIN user_sessions s ON s.user_id=u.id WHERE s.token_hash=? AND s.expires>?',
                             (digest(token), time.time())) if token else None
        return public_user(row) if row else None

    def login_response(self, user, redirect=False):
        if getattr(self, 'agents', None):
            self.agents.profile(user)
        token = secrets.token_urlsafe(32)
        self.store.execute('DELETE FROM user_sessions WHERE expires<?', (time.time(),))
        self.store.execute('INSERT INTO user_sessions VALUES(?,?,?)', (digest(token), user['id'], time.time()+7*86400))
        response = RedirectResponse('/', status_code=303) if redirect else JSONResponse({'user': public_user(user)})
        response.set_cookie(COOKIE, token, max_age=7*86400, httponly=True, samesite='lax', secure=False)
        return response

    def owns_collection(self, cid, user=None):
        user = user or CURRENT_USER.get()
        return bool(user and self.store.one('SELECT collection_id FROM collection_owners WHERE collection_id=? AND user_id=?', (cid, user['id'])))

    def authorize_path(self, request, user):
        parts = request.url.path.strip('/').split('/')
        cid = request.query_params.get('collectionId')
        if len(parts) >= 3:
            kind, ident = parts[1:3]
            if kind == 'collections':
                cid = ident
            elif kind in ('materials', 'files'):
                cid = self.store.collection_for(ident)
            elif kind == 'quizzes':
                row = self.store.one('SELECT collection_id FROM quiz_collections WHERE quiz_id=?', (ident,))
                cid = row['collection_id'] if row else None
            elif kind == 'jobs':
                row = self.store.job(ident)
                if row and row['kind'] == 'classroom':
                    params = row['params']
                    if params.get('requesterId') != user['id'] or not self.store.one(
                        'SELECT user_id FROM group_members WHERE group_id=? AND user_id=?', (params['groupId'],user['id'])):
                        raise HTTPException(404, 'Classroom request not found.')
                    return
                cid = (row['params'].get('collectionId') or self.store.collection_for(row['material_id'])) if row else None
            elif kind == 'sources':
                row = self.store.one('SELECT material_id FROM sources WHERE id=?', (ident,))
                cid = self.store.collection_for(row['material_id']) if row else None
            else:
                return
            if kind in ('collections', 'materials', 'files', 'quizzes', 'jobs', 'sources') and not cid:
                raise HTTPException(404, 'Study item not found.')
        if cid and not self.owns_collection(cid, user):
            raise HTTPException(404, 'Study item not found.')

    def throttle(self, request, email):
        key = digest((request.client.host if request.client else 'local') + ':' + email)
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM auth_attempts WHERE key=?', (key,)).fetchone()
            count = row['count'] if row and row['started'] > time.time()-900 else 0
            if count >= 10:
                raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')
            db.execute('INSERT OR REPLACE INTO auth_attempts VALUES(?,?,?)', (key, count+1, row['started'] if count else time.time()))

    def routes(self, app):
        @app.get('/api/auth/me')
        def me(request: Request):
            return {'user': self.session_user(request), 'googleConfigured': bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))}

        @app.patch('/api/auth/me')
        def rename(body: ProfileUpdate, request: Request):
            user = self.session_user(request)
            if not user:
                raise HTTPException(401, 'Sign in to continue.')
            name = body.name.strip()
            if not name or any(ord(char) < 32 or ord(char) == 127 for char in name):
                raise HTTPException(400, 'Enter a name using 1–80 characters.')
            self.store.execute('UPDATE users SET name=? WHERE id=?', (name, user['id']))
            return {'user': public_user(self.store.one('SELECT * FROM users WHERE id=?', (user['id'],)))}

        @app.post('/api/auth/register', status_code=201)
        def register(body: Credentials, request: Request):
            email = body.email.strip().lower()
            self.throttle(request, email)
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or not body.name.strip():
                raise HTTPException(400, 'Enter your name and a valid email.')
            user_id = uid()
            try:
                self.store.execute('INSERT INTO users(id,email,name,password_hash,provider,created,demo) VALUES(?,?,?,?,?,?,0)',
                                   (user_id, email, body.name.strip(), password_hash(body.password), 'email', time.time()))
            except sqlite3.IntegrityError:
                raise HTTPException(409, 'This email already has an account. Sign in instead.')
            return self.login_response(self.store.one('SELECT * FROM users WHERE id=?', (user_id,)))

        @app.post('/api/auth/login')
        def login(body: Credentials, request: Request):
            email = body.email.strip().lower()
            self.throttle(request, email)
            row = self.store.one('SELECT * FROM users WHERE email=?', (email,))
            if not row or not password_matches(body.password, row['password_hash']):
                raise HTTPException(401, 'Email or password is incorrect.')
            return self.login_response(row)

        @app.post('/api/auth/demo')
        def demo():
            return self.login_response(self.store.one('SELECT * FROM users WHERE id=?', (DEMO_USER,)))

        @app.post('/api/auth/logout')
        def logout(request: Request):
            self.store.execute('DELETE FROM user_sessions WHERE token_hash=?', (digest(request.cookies.get(COOKIE, '')),))
            response = JSONResponse({'signedOut': True})
            response.delete_cookie(COOKIE)
            return response

        @app.get('/api/auth/google/start')
        def google_start(request: Request):
            if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
                return RedirectResponse('/?authError=google-setup', status_code=303)
            state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
            redirect = str(request.base_url).rstrip('/')+'/api/auth/google/callback'
            user = self.session_user(request)
            self.store.execute('DELETE FROM oauth_states WHERE created<?', (time.time()-600,))
            self.store.execute('INSERT INTO oauth_states VALUES(?,?,?,?,?,?,?)',
                               (digest(state), nonce, verifier, redirect, user['id'] if user else None, time.time(), digest(state)))
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
            url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urlencode({'client_id': os.environ['GOOGLE_CLIENT_ID'],
                'redirect_uri': redirect, 'response_type': 'code', 'scope': 'openid email profile',
                'state': state, 'nonce': nonce, 'code_challenge': challenge, 'code_challenge_method': 'S256', 'prompt': 'select_account'})
            response = RedirectResponse(url, status_code=303)
            response.set_cookie('lecture_lab_oauth', state, max_age=600, httponly=True, samesite='lax')
            return response

        @app.get('/api/auth/google/callback')
        async def google_callback(request: Request):
            state = request.query_params.get('state', '')
            cookie = request.cookies.get('lecture_lab_oauth', '')
            row = None
            if state and cookie and hmac.compare_digest(state, cookie):
                with self.store.connect() as db:
                    row = db.execute('SELECT * FROM oauth_states WHERE state_hash=? AND created>?', (digest(state), time.time()-600)).fetchone()
                    db.execute('DELETE FROM oauth_states WHERE state_hash=?', (digest(state),))
            stage = 'state'
            try:
                if not row or request.query_params.get('error') or not request.query_params.get('code'):
                    raise ValueError('OAuth state invalid')
                stage = 'token'
                async with httpx.AsyncClient(timeout=20) as client:
                    response = await client.post('https://oauth2.googleapis.com/token', data={
                        'code': request.query_params['code'], 'client_id': os.environ['GOOGLE_CLIENT_ID'],
                        'client_secret': os.environ['GOOGLE_CLIENT_SECRET'], 'redirect_uri': row['redirect_uri'],
                        'grant_type': 'authorization_code', 'code_verifier': row['verifier']})
                    response.raise_for_status()
                stage = 'identity'
                from google.oauth2 import id_token
                from google.auth.transport.requests import Request as GoogleRequest
                from starlette.concurrency import run_in_threadpool
                # Google can issue a token a few seconds ahead of the local clock.
                # Keep full verification, allowing only bounded timestamp drift.
                identity = await run_in_threadpool(id_token.verify_oauth2_token, response.json()['id_token'], GoogleRequest(), os.environ['GOOGLE_CLIENT_ID'], clock_skew_in_seconds=30)
                if identity.get('nonce') != row['nonce'] or not identity.get('email_verified') or not identity.get('sub'):
                    raise ValueError('Google identity invalid')
                stage = 'account'
                user = self.store.one('SELECT * FROM users WHERE google_sub=?', (identity['sub'],))
                if not user:
                    existing = self.store.one('SELECT * FROM users WHERE email=?', (identity['email'].lower(),))
                    if existing and existing['id'] != row['user_id']:
                        return RedirectResponse('/?authError=google-link', status_code=303)
                    user_id = existing['id'] if existing else uid()
                    if existing:
                        self.store.execute('UPDATE users SET google_sub=? WHERE id=?', (identity['sub'], user_id))
                    else:
                        self.store.execute('INSERT INTO users(id,email,name,google_sub,provider,created,demo) VALUES(?,?,?,?,?,?,0)',
                                           (user_id, identity['email'].lower(), identity.get('name', identity['email'].split('@')[0]), identity['sub'], 'google', time.time()))
                    user = self.store.one('SELECT * FROM users WHERE id=?', (user_id,))
                result = self.login_response(user, redirect=True)
            except Exception as exc:
                # Never log provider response bodies, authorization codes, tokens,
                # email addresses, or exception strings containing request URLs.
                error = 'google-signin'
                reason = type(exc).__name__
                if isinstance(exc, httpx.RequestError):
                    error = 'google-network'
                elif isinstance(exc, httpx.HTTPStatusError):
                    try:
                        provider_error = exc.response.json().get('error')
                    except (ValueError, AttributeError):
                        provider_error = None
                    if provider_error in ('invalid_client', 'unauthorized_client', 'invalid_grant', 'redirect_uri_mismatch'):
                        reason = provider_error
                    error = 'google-setup' if provider_error in ('invalid_client', 'unauthorized_client', 'redirect_uri_mismatch') else 'google-retry'
                elif stage == 'identity':
                    error = 'google-verify'
                    for prefix, label in (('Token used too early', 'clock-ahead'), ('Token expired', 'token-expired'), ('Token has wrong audience', 'wrong-audience'), ('Wrong issuer', 'wrong-issuer')):
                        if str(exc).startswith(prefix):
                            reason = label
                            break
                elif stage == 'state':
                    error = 'google-session'
                logger.warning('Google sign-in failed: stage=%s reason=%s', stage, reason)
                result = RedirectResponse('/?authError='+error, status_code=303)
            result.delete_cookie('lecture_lab_oauth')
            return result
