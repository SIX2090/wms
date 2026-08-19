# -*- coding: utf-8 -*-
"""AI-LOGIN-F02 回归测试：网页登录持久化（记住我，手机一直登录）。

覆盖：
- 登录成功后下发 remember_token 持久 Cookie（有效期 REMEMBER_COOKIE_DURATION）
- 会话 Cookie 过期/丢失后，仅凭 remember_token 自动恢复登录态（手机浏览器重开免登录）
- 退出登录同时清除 remember_token（下次必须重新输密码）
- REMEMBER_COOKIE_DURATION 已按配置生效（默认 365 天）
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import User, db  # noqa: E402


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    yield c


def _login(c):
    return c.post("/login", data={"username": "admin", "password": "admin"},
                  content_type="application/x-www-form-urlencoded")


def _cookie_names(c):
    # Werkzeug 3.x test client 用 _cookies 字典存 Cookie，Cookie 字段名为 key
    return {cookie.key for cookie in (c._cookies or {}).values()}


def _drop_session_cookie(c):
    """模拟 8 小时会话过期/手机浏览器丢弃会话 Cookie，只保留 remember_token。"""
    for dict_key, cookie in list((c._cookies or {}).items()):
        if cookie.key == "session":
            c._cookies.pop(dict_key, None)


def test_remember_cookie_duration_configured():
    """长登录默认 365 天（WMS_REMEMBER_LOGIN_DAYS 可调）。"""
    assert app_module.app.config["REMEMBER_COOKIE_DURATION"] == timedelta(days=365)


def test_login_sets_remember_cookie(client):
    resp = _login(client)
    assert resp.status_code == 302
    assert "remember_token" in _cookie_names(client)


def test_remember_cookie_restores_login_after_session_expiry(client):
    """会话过期后凭 remember_token 自动恢复登录，不再跳登录页。"""
    _login(client)
    _drop_session_cookie(client)
    resp = client.get("/print_routing")
    assert resp.status_code == 200


def test_logout_clears_remember_cookie(client):
    """退出登录必须同时清除 remember_token，防止共用手机退出后仍长登录。"""
    _login(client)
    assert "remember_token" in _cookie_names(client)
    client.get("/logout")
    assert "remember_token" not in _cookie_names(client)
    _drop_session_cookie(client)
    resp = client.get("/print_routing")
    assert resp.status_code == 302  # 未登录 → 跳转登录页
