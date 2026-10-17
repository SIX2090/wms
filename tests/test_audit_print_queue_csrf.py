# -*- coding: utf-8 -*-
"""BUG-2026-10-17-013-F07：/print_queue/jobs 的 CSRF 豁免只服务 Bearer。

审计 S3：该端点 @csrf.exempt 却接受 Web 会话鉴权，第三方站点可借登录态塞打印任务。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import app as app_module  # noqa: E402
from app import User, db  # noqa: E402

app_module.app.config['TESTING'] = True


@pytest.fixture()
def client(monkeypatch):
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        user = User(username='admin', password_hash=generate_password_hash('admin'),
                    role='admin', must_change_password=False)
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    monkeypatch.setitem(app_module.app.config, 'WTF_CSRF_ENABLED', True)
    yield client
    with app_module.app.app_context():
        db.session.remove()


def test_web_session_without_csrf_token_is_rejected(client, monkeypatch):
    import flask_wtf.csrf as csrf_mod

    def _boom(token):
        raise csrf_mod.ValidationError('bad token')

    monkeypatch.setattr(csrf_mod, 'validate_csrf', _boom)
    resp = client.post('/print_queue/jobs', json={})
    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert 'CSRF' in (resp.get_json() or {}).get('msg', '')


def test_bearer_request_skips_web_csrf_branch(client, monkeypatch):
    import flask_wtf.csrf as csrf_mod

    called = {'n': 0}

    def _boom(token):
        called['n'] += 1
        raise csrf_mod.ValidationError('bad token')

    monkeypatch.setattr(csrf_mod, 'validate_csrf', _boom)
    resp = client.post('/print_queue/jobs', json={},
                       headers={'Authorization': 'Bearer invalid-token'})
    assert called['n'] == 0
    assert resp.status_code in (400, 401, 403)
