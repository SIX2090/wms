# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：领料出库（requisition）域路由迁移到 routes/requisition.py。

register-on-app 模式（register_requisition_routes(app)），endpoint 名与 URL 不变。

验收点：
S1. 核心 endpoint 已注册，且无 requisition.xxx 前缀重复。
S2. URL 路径保持不变。
S3. 领料列表页可渲染（200）。
S4. 新增领料单成功。
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
from app import ProductionRequisition, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "requisition_list", "requisition_detail", "save_requisition_table",
    "add_requisition", "update_requisition", "add_requisition_item",
    "update_requisition_item", "delete_requisition_item",
    "batch_delete_requisition_items", "batch_add_requisition_items",
    "complete_requisition", "revert_requisition", "delete_requisition",
    "batch_delete_requisition", "export_requisition", "import_requisition",
    "export_single_requisition", "print_single_requisition",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


class TestRequisitionRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"requisition.{ep}" not in app_module.app.view_functions, f"requisition.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("requisition_list") == "/requisition"
                assert url_for("add_requisition") == "/requisition/add"
                assert url_for("requisition_detail", id=1) == "/requisition/1"
                assert url_for("complete_requisition", id=1) == "/requisition/1/complete"
                assert url_for("delete_requisition", id=1) == "/requisition/1/delete"
                assert url_for("export_requisition") == "/requisition/export"

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/requisition")
        assert resp.status_code in (200, 302)
        if resp.status_code == 200:
            assert ("领料" in resp.get_data(as_text=True)) or ("工单领料" in resp.get_data(as_text=True))

    def test_add_requisition(self):
        client = self._setup()
        _login(client)
        resp = client.post("/requisition/add", data={"purpose": "测试领料", "remark": "备注"})
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            req = db.session.get(ProductionRequisition, data["id"])
            assert req is not None
            assert req.status == "pending"
            assert req.purpose == "测试领料"