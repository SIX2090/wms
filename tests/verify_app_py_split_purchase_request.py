# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：采购申请（purchase_request）域路由迁移到 routes/purchase_request.py。

register-on-app 模式（register_purchase_request_routes(app)），endpoint 名与 URL 不变。

验收点：
S1. 核心 endpoint 已注册，且无 purchase_request.xxx 前缀重复。
S2. URL 路径保持不变。
S3. 迁移模块可正常加载（register_purchase_request_routes 可调用）。
S4. 新增采购申请成功（需物料，按 app.py add_purchase_request 真实入参）。
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
from app import db, PurchaseRequest  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "purchase_request_list", "purchase_request_detail", "print_purchase_request",
    "create_purchase_order_from_request", "purchase_request_add_page",
    "purchase_request_edit_page", "add_purchase_request", "approve_purchase_request",
    "reject_purchase_request", "revert_purchase_request", "complete_purchase_request",
    "delete_purchase_request", "batch_delete_purchase_request", "import_purchase_request",
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


_MATERIAL_ID = {"id": None}


def _seed_base():
    from app import Material, MaterialCategory, Unit
    cat = MaterialCategory(code="PRCAT", name="采购分类")
    unit = Unit(code="PCS", name="个")
    db.session.add_all([cat, unit])
    db.session.flush()
    mat = Material(code="PRM1", name="采购物料", category_id=cat.id, unit_id=unit.id, stock=100, price=5)
    db.session.add(mat)
    db.session.commit()
    _MATERIAL_ID["id"] = mat.id


class TestPurchaseRequestRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_base()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"purchase_request.{ep}" not in app_module.app.view_functions, f"purchase_request.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("purchase_request_list") == "/purchase_request"
                assert url_for("purchase_request_detail", id=1) == "/purchase_request/1"
                assert url_for("print_purchase_request", id=1) == "/purchase_request/1/print"
                assert url_for("purchase_request_add_page") == "/purchase_request/add"
                assert url_for("purchase_request_edit_page", id=1) == "/purchase_request/1/edit"
                assert url_for("add_purchase_request") == "/purchase_request/add"
                assert url_for("approve_purchase_request", id=1) == "/purchase_request/1/approve"
                assert url_for("reject_purchase_request", id=1) == "/purchase_request/1/reject"
                assert url_for("revert_purchase_request", id=1) == "/purchase_request/1/revert"
                assert url_for("complete_purchase_request", id=1) == "/purchase_request/1/complete"
                assert url_for("delete_purchase_request", id=1) == "/purchase_request/1/delete"
                assert url_for("create_purchase_order_from_request", id=1) == "/purchase_request/1/create_purchase_order"
                assert url_for("batch_delete_purchase_request") == "/purchase_request/batch_delete"
                assert url_for("import_purchase_request") == "/purchase_request/import"

    def test_route_module_loads(self):
        # 迁移模块可正常加载，且暴露注册辅助函数（不导入 app，避免循环导入）
        from routes.purchase_request import register_purchase_request_routes
        assert callable(register_purchase_request_routes)

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/purchase_request")
        assert resp.status_code == 200
        assert "采购申请" in resp.get_data(as_text=True)

    def test_add_purchase_request(self):
        client = self._setup()
        _login(client)
        resp = client.post("/purchase_request/add", json={
            "request_no": "PR-TEST-001",
            "date": "2026-08-04",
            "applicant": "张三",
            "department": "采购部",
            "urgency": "normal",
            "expected_date": "2026-08-10",
            "reason": "测试采购",
            "remark": "",
            "items": [{"material_id": _MATERIAL_ID["id"], "quantity": 10, "estimated_price": 5}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            req = db.session.get(PurchaseRequest, data["id"])
            assert req is not None
            assert req.status == "pending"
            assert req.request_no == "PR-TEST-001"
            assert len(req.items) == 1
            assert req.items[0].quantity == 10
            assert req.total_amount == 50