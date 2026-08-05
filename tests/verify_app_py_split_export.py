# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：导出（export）域路由迁移到 routes/export.py。

register-on-app 模式（register_export_routes(app)），endpoint 名与 URL 不变。

验收点：
P1. 核心 endpoint 已注册，且无 export.xxx 前缀重复。
P2. URL 路径保持不变（/export/... 与 /xxx/export 均在）。
P3. 模板导出（/export/template/*）返回可下载的 xlsx（200）。
P4. 数据导出（/export/in_order 等）在登录后返回 xlsx（200）。
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

ENDPOINTS = [
    "export_bom_template",
    "export_requisition_template",
    "export_subcontract_template",
    "export_subcontract_issue_template",
    "export_subcontract_receive_template",
    "export_adjustment_template",
    "export_check_template",
    "export_purchase_request_template",
    "export_purchase_order_template",
    "export_in_order",
    "export_purchase_request",
    "export_after_sale_out",
    "export_material_template",
    "export_in_order_template",
    "export_out_order_template",
]

TEMPLATE_URLS = [
    "/export/template/bom",
    "/export/template/requisition",
    "/export/template/subcontract",
    "/export/template/subcontract_issue",
    "/export/template/subcontract_receive",
    "/export/template/adjustment",
    "/export/template/check",
    "/export/template/purchase_request",
    "/export/template/purchase_order",
    "/export/template/material",
    "/export/template/in_order",
    "/export/template/out_order",
]

# 数据导出同时保留备用 URL（/xxx/export 兼容路由）
ALIAS_URLS = [
    "/export/in_order",
    "/in_order/export",
    "/export/purchase_request",
    "/purchase_request/export",
    "/export/after_sale_out",
    "/after_sale_out/export",
]


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


def test_endpoints_registered():
    rules = {r.endpoint for r in app_module.app.url_map.iter_rules()}
    for ep in ENDPOINTS:
        assert ep in rules, f"endpoint {ep} 未注册"
    # register-on-app 模式不应产生 export.xxx 前缀的 endpoint
    assert not any(ep.startswith("export.") for ep in rules)


def test_template_urls_return_xlsx():
    client = _setup()
    for url in TEMPLATE_URLS:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        assert "application" in resp.content_type or "octet-stream" in resp.content_type, f"{url} content_type={resp.content_type}"


def test_alias_urls_resolve():
    client = _setup()
    for url in ALIAS_URLS:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"


def test_export_in_order_returns_xlsx():
    client = _setup()
    resp = client.get("/export/in_order")
    assert resp.status_code == 200
    assert "octet-stream" in resp.content_type or "xlsx" in resp.content_type or "spreadsheet" in resp.content_type