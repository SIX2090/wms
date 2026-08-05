# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：单位/供应商的模板下载、导出、导入（unit_supplier_import）
域路由迁移到 routes/unit_supplier_import.py。

register-on-app 模式（register_unit_supplier_import_routes(app)），endpoint 名与 URL 不变。

验收点：
P1. 核心 endpoint 已注册，且无 unit_supplier_import.xxx 前缀重复。
P2. 模板下载（/unit/download_template、/supplier/download_template）返回可下载 xlsx（200）。
P3. 数据导出（/unit/export、/supplier/export）在登录后返回可下载 xlsx（200）。
P4. 导入（/unit/import、/supplier/import）POST 无文件时返回 api_error。
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
    "download_unit_template",
    "export_unit",
    "import_unit",
    "download_supplier_template",
    "export_supplier",
    "import_supplier",
]

DOWNLOAD_URLS = [
    "/unit/download_template",
    "/supplier/download_template",
]

EXPORT_URLS = [
    "/unit/export",
    "/supplier/export",
]

IMPORT_URLS = [
    "/unit/import",
    "/supplier/import",
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


def _seed_master():
    from app import Unit, Supplier
    db.session.add(Unit(code="U-001", name="个"))
    db.session.add(Unit(code="U-002", name="套"))
    db.session.add(Supplier(code="SUP-001", name="示例供应商A", contact="张三", phone="13800138000", address="广州市天河区"))
    db.session.add(Supplier(code="SUP-002", name="示例供应商B", contact="李四", phone="13900139000", address="深圳市南山区"))
    db.session.commit()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _setup(seed=True):
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        if seed:
            _seed_master()
    client = _make_client()
    _login(client)
    return client


def test_endpoints_registered():
    rules = {r.endpoint for r in app_module.app.url_map.iter_rules()}
    for ep in ENDPOINTS:
        assert ep in rules, f"endpoint {ep} 未注册"
    # register-on-app 模式不应产生 unit_supplier_import.xxx 前缀的 endpoint
    assert not any(ep.startswith("unit_supplier_import.") for ep in rules)


def test_download_template_returns_xlsx():
    client = _setup()
    for url in DOWNLOAD_URLS:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        assert "application" in resp.content_type or "octet-stream" in resp.content_type, f"{url} content_type={resp.content_type}"


def test_export_returns_xlsx():
    client = _setup()
    for url in EXPORT_URLS:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        assert "octet-stream" in resp.content_type or "xlsx" in resp.content_type or "spreadsheet" in resp.content_type


def test_import_without_file_returns_error():
    client = _setup()
    for url in IMPORT_URLS:
        resp = client.post(
            url,
            data={},
            content_type="application/x-www-form-urlencoded",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert resp.status_code == 400, f"{url} -> {resp.status_code}"
        assert resp.is_json, f"{url} 应返回 JSON api_error"
        payload = resp.get_json()
        assert payload.get("status") == "error", f"{url} payload={payload}"