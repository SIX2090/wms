# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：待办单据（pending_documents）域路由迁移到 routes/pending_documents.py。

register-on-app 模式（register_pending_documents_routes(app)），endpoint 名与 URL 不变。

验收点：
P1. 核心 endpoint 已注册，且无 pending_documents.xxx 前缀重复。
P2. URL 路径保持不变（/pending_documents 在）。
P3. /pending_documents 页面登录后 GET 返回 200。
P4. 带 module/status/search 查询参数仍返回 200。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

URL = "/pending_documents"


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _setup():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    client = _make_client()
    _login(client)
    return client


def test_pending_documents_endpoint_registered():
    rules = {r.endpoint for r in app_module.app.url_map.iter_rules()}
    assert "pending_documents" in rules, "endpoint pending_documents 未注册"
    # register-on-app 模式不应产生 pending_documents.xxx 前缀的 endpoint
    assert not any(ep.startswith("pending_documents.") for ep in rules)


def test_pending_documents_page_returns_200():
    client = _setup()
    resp = client.get(URL)
    assert resp.status_code == 200, f"{URL} -> {resp.status_code}"


def test_pending_documents_with_query_params_returns_200():
    client = _setup()
    for qs in (
        "?module=purchase_request",
        "?status=pending",
        "?search=轴承",
        "?module=purchase_request&status=approved&search=6204",
        "?module=invalid&status=invalid",
    ):
        resp = client.get(f"{URL}{qs}")
        assert resp.status_code == 200, f"{URL}{qs} -> {resp.status_code}"