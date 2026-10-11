# -*- coding: utf-8 -*-
"""F2.1 回归：admin 默认弱密码强制改密。

- 未设 WMS_BOOTSTRAP_PASSWORD 且 admin 密码仍为默认 'admin' → must_change_password 置位。
- 已显式设置 WMS_BOOTSTRAP_PASSWORD（可信密码）→ 不强制。
- 已自行改过密码 → 幂等，不再被重复置位。
- 置位后登录被强制导向改密页（/user/change_password）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed_admin(password, must_change):
    db.drop_all()
    db.create_all()
    db.session.add(User(
        username="admin", password_hash=generate_password_hash(password),
        role="admin", status="normal", must_change_password=must_change,
    ))
    db.session.commit()


def test_default_password_forces_change(monkeypatch):
    """未设 WMS_BOOTSTRAP_PASSWORD + 密码仍为 'admin' → 强制改密。"""
    monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
    with app_module.app.app_context():
        _seed_admin("admin", False)
        app_module.ensure_admin_user_exists()
        u = User.query.filter_by(username="admin").first()
        assert u.must_change_password is True


def test_explicit_bootstrap_password_not_forced(monkeypatch):
    """显式设置 WMS_BOOTSTRAP_PASSWORD（可信）→ 不强制改密。"""
    monkeypatch.setenv("WMS_BOOTSTRAP_PASSWORD", "S3cret-Strong-1")
    with app_module.app.app_context():
        _seed_admin("S3cret-Strong-1", False)
        app_module.ensure_admin_user_exists()
        u = User.query.filter_by(username="admin").first()
        assert u.must_change_password is False


def test_already_changed_password_is_idempotent(monkeypatch):
    """已自行改过密码（不再是默认 'admin'）→ 不被重复置位。"""
    monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
    with app_module.app.app_context():
        _seed_admin("MyOwnPass-9", False)
        app_module.ensure_admin_user_exists()
        u = User.query.filter_by(username="admin").first()
        assert u.must_change_password is False


def test_login_redirects_to_change_password_when_forced(monkeypatch):
    """must_change_password=True 时登录被强制导向改密页。"""
    monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
    with app_module.app.app_context():
        _seed_admin("admin", True)
    client = app_module.app.test_client()
    resp = client.post("/login", data={"username": "admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code == 302
    assert "/user/change_password" in resp.headers.get("Location", "")
