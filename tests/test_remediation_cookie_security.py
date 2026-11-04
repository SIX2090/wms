"""IA-02: real login cookies, HTTPS/intranet modes and two independent users."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
from werkzeug.security import generate_password_hash

import app as m

ROOT = Path(__file__).resolve().parents[1]


def cookie_config(secure, testing=False):
    # A fresh config import avoids leaking reloads into other modules' fixtures.
    env = dict(os.environ, SESSION_COOKIE_SECURE='true' if secure else 'false',
               PYTHONPATH=str(ROOT / 'app'), PYTHONIOENCODING='utf-8')
    source = ('import config,json; c=config.' + ('TestingConfig' if testing else 'ProductionConfig') +
              '; print(json.dumps({k:getattr(c,k,None) for k in '
              '["SESSION_COOKIE_SECURE","REMEMBER_COOKIE_SECURE",'
              '"REMEMBER_COOKIE_HTTPONLY","REMEMBER_COOKIE_SAMESITE"]}))')
    result = subprocess.run([sys.executable, '-c', source], env=env, cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('secure', [True, False])
def test_remember_cookie_matches_session_transport(secure):
    values = cookie_config(secure)
    assert values == {'SESSION_COOKIE_SECURE': secure, 'REMEMBER_COOKIE_SECURE': secure,
                      'REMEMBER_COOKIE_HTTPONLY': True, 'REMEMBER_COOKIE_SAMESITE': 'Lax'}


def test_testing_config_keeps_http_login_even_when_host_uses_https():
    assert cookie_config(True, testing=True)['REMEMBER_COOKIE_SECURE'] is False


@pytest.fixture
def users(monkeypatch):
    for key, value in {'TESTING': True, 'WTF_CSRF_ENABLED': True,
                       'PROPAGATE_EXCEPTIONS': False}.items():
        monkeypatch.setitem(m.app.config, key, value)
    with m.app.app_context():
        assert str(m.db.engine.url) == 'sqlite:///:memory:'
        m.db.session.remove()
        m.db.drop_all()
        m.db.create_all()
        for name in ('cookie-a', 'cookie-b'):
            m.db.session.add(m.User(username=name, role='warehouse', must_change_password=False,
                                   password_hash=generate_password_hash('Cookie-Test-Only!')))
        m.db.session.commit()
    yield
    with m.app.app_context():
        m.db.session.remove()


def login(client, base_url, name, remember=True):
    page = client.get('/login', base_url=base_url)
    token = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page.get_data(as_text=True))
    assert token
    result = client.post('/login', base_url=base_url, headers={'Referer': base_url + '/login'}, data={
        'username': name, 'password': 'Cookie-Test-Only!',
        'csrf_token': token.group(1), 'remember': '1' if remember else ''})
    assert result.status_code == 302
    assert '/login' not in result.location
    return result


@pytest.mark.parametrize('secure', [True, False])
def test_two_account_login_refresh_remember_and_logout(users, monkeypatch, secure):
    for key, value in cookie_config(secure).items():
        if value is not None:
            monkeypatch.setitem(m.app.config, key, value)
    origin = ('https' if secure else 'http') + '://localhost'
    clients = [m.app.test_client(), m.app.test_client()]
    identities = []
    for client, name in zip(clients, ('cookie-a', 'cookie-b')):
        login(client, origin, name)
        for key in ('session', 'remember_token'):
            cookie = client.get_cookie(key)
            assert cookie is not None
            assert cookie.secure is secure and cookie.http_only is True
            assert cookie.same_site == 'Lax'
        with client.session_transaction(base_url=origin) as session:
            identities.append(session['_user_id'])
        assert client.get('/material?embedded=1', base_url=origin).status_code == 200
        client.delete_cookie('session')
        assert client.get('/material?embedded=1', base_url=origin).status_code == 200
        assert client.get('/material?embedded=1', base_url=origin).status_code == 200
    assert identities[0] != identities[1]
    clients[0].get('/logout', base_url=origin)
    assert clients[0].get_cookie('remember_token') is None
    assert clients[0].get('/material?embedded=1', base_url=origin).status_code == 302
    assert clients[1].get('/material?embedded=1', base_url=origin).status_code == 200


def test_expired_session_without_remember_requires_login(users, monkeypatch):
    from itsdangerous.timed import TimestampSigner
    for key, value in cookie_config(True).items():
        if value is not None:
            monkeypatch.setitem(m.app.config, key, value)
    client = m.app.test_client()
    original = TimestampSigner.get_timestamp
    with monkeypatch.context() as clock:
        clock.setattr(TimestampSigner, 'get_timestamp', lambda self: original(self) - 28801)
        login(client, 'https://localhost', 'cookie-a', remember=False)
    assert client.get_cookie('remember_token') is None
    assert client.get('/material?embedded=1', base_url='https://localhost').status_code == 302
