# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：采购订单（purchase_order）域路由迁移到 routes/purchase_order.py。

register-on-app 模式（register_purchase_order_routes(app)），endpoint 名与 URL 不变。

验收点：
P1. 核心 endpoint 已注册，且无 purchase_order.xxx 前缀重复。
P2. URL 路径保持不变。
P3. 采购订单列表页可渲染（200）。
P4. 新增采购订单成功（需供应商/物料/仓库）。
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
    "purchase_order_list",
    "export_purchase_order",
    "import_purchase_order",
    "purchase_order_add_page",
    "purchase_order_edit_page",
    "save_purchase_order",
    "purchase_order_detail",
    "print_purchase_order",
    "create_in_order_from_purchase_order_selection",
    "copy_purchase_order",
    "create_in_order_from_purchase_order",
    "close_purchase_order",
    "reopen_purchase_order",
    "delete_purchase_order",
    "batch_delete_purchase_order",
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


_SUPPLIER_ID = {"id": None}
_MATERIAL_ID = {"id": None}


def _seed_base():
    from app import Material, MaterialCategory, Supplier, Unit, Warehouse
    cat = MaterialCategory(code="PCAT", name="采购分类")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="PWH", name="采购仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="PM1", name="采购物料", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    sup = Supplier(code="PS1", name="测试供应商")
    db.session.add_all([mat, sup])
    db.session.commit()
    _SUPPLIER_ID["id"] = sup.id
    _MATERIAL_ID["id"] = mat.id


class TestPurchaseOrderRegister:
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
                assert f"purchase_order.{ep}" not in app_module.app.view_functions, f"purchase_order.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("purchase_order_list") == "/purchase_order"
                assert url_for("purchase_order_add_page") == "/purchase_order/add"
                assert url_for("save_purchase_order") == "/purchase_order/save"
                assert url_for("purchase_order_detail", id=1) == "/purchase_order/1"
                assert url_for("purchase_order_edit_page", id=1) == "/purchase_order/1/edit"
                assert url_for("export_purchase_order") == "/purchase_order/export"
                assert url_for("close_purchase_order", id=1) == "/purchase_order/1/close"
                assert url_for("delete_purchase_order", id=1) == "/purchase_order/1/delete"
                assert url_for("batch_delete_purchase_order") == "/purchase_order/batch_delete"

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/purchase_order")
        assert resp.status_code == 200
        assert "采购" in resp.get_data(as_text=True)

    def test_add_purchase_order(self):
        from app import PurchaseOrder
        client = self._setup()
        _login(client)
        resp = client.post("/purchase_order/save", json={
            "order_no": "PO-TEST-001",
            "date": "2026-08-04",
            "expected_date": "2026-08-10",
            "supplier_id": _SUPPLIER_ID["id"],
            "items": [{"material_id": _MATERIAL_ID["id"], "quantity": 5, "price": 10}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            order = db.session.get(PurchaseOrder, data["id"])
            assert order is not None
            assert order.order_no == "PO-TEST-001"
            assert order.status == "pending"
            assert len(order.items) == 1
            assert order.items[0].quantity == 5
            assert order.total_amount == 50