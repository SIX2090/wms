# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：采购入库（in_order）域路由迁移到 routes/in_order.py。

register-on-app 模式（register_in_order_routes(app)），endpoint 名与 URL 不变。

验收点：
I1. 核心 endpoint 已注册，且无 in_order.xxx 前缀重复。
I2. URL 路径保持不变。
I3. 新增采购入库单成功（需供应商/物料/仓库）。
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
from app import db, InOrder  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "in_order_list", "in_order_detail", "in_order_push_page",
    "create_in_order_push", "update_in_order", "in_order_add_page",
    "add_in_order", "add_in_order_item", "batch_add_in_order_items",
    "delete_in_order_item", "in_order_item_delete_alias", "update_in_order_item",
    "copy_in_order_to_out", "copy_in_order", "check_in_order_anomalies",
    "complete_in_order", "update_completed_in_order", "delete_in_order",
    "revert_in_order", "convert_in_order_to_out_order", "batch_delete_in_order",
    "batch_complete_in_order", "batch_revert_in_order", "preview_in_order_template",
    "print_in_order_with_template", "print_in_order", "print_in_order_direct",
    "print_in_order_labels", "in_order_print_template_list",
    "add_in_order_print_template", "set_default_in_order_print_template",
    "delete_in_order_print_template", "export_single_in_order",
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


def _seed_base():
    from app import Material, MaterialCategory, Supplier, Unit, Warehouse
    cat = MaterialCategory(code="ICAT", name="入库分类")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="IWH", name="入库仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="IM1", name="入库物料", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    sup = Supplier(code="IS1", name="测试供应商")
    db.session.add_all([mat, sup])
    db.session.commit()
    _SUPPLIER_ID["id"] = sup.id


class TestInOrderRegister:
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
                assert f"in_order.{ep}" not in app_module.app.view_functions, f"in_order.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("in_order_list") in ("/in_order", "/other_in_order")
                assert url_for("in_order_detail", id=1) == "/in_order/1"
                assert url_for("in_order_add_page") in ("/in_order/add", "/other_in_order/add")
                assert url_for("add_in_order") in ("/in_order/add", "/other_in_order/add")
                assert url_for("complete_in_order", id=1) == "/in_order/1/complete"
                assert url_for("delete_in_order", id=1) == "/in_order/1/delete"

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/in_order")
        assert resp.status_code == 200
        assert "入库" in resp.get_data(as_text=True)

    def test_add_in_order(self):
        client = self._setup()
        _login(client)
        resp = client.post("/in_order/add", json={
            "business_type": "采购入库",
            "supplier_id": _SUPPLIER_ID["id"],
            "warehouse": "入库仓",
            "items": [{"code": "IM1", "quantity": 2, "price": 10}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            order = db.session.get(InOrder, data["id"])
            assert order is not None
            assert order.status == "pending"
            assert order.business_type == "采购入库"
            assert order.warehouse == "入库仓"
            assert len(order.items) == 1
            assert order.items[0].quantity == 2

    def test_reverted_draft_can_load_edit_page_with_items(self):
        client = self._setup()
        _login(client)
        created = client.post("/in_order/add", json={
            "business_type": "采购入库",
            "supplier_id": _SUPPLIER_ID["id"],
            "warehouse": "入库仓",
            "items": [{
                "code": "IM1", "quantity": 3, "price": 12,
                "contract_no": "HT-IN-001", "project_name": "入库工程",
            }],
        }).get_json()
        page = client.get(f"/in_order/add?order_id={created['id']}")
        assert page.status_code == 200
        content = page.get_data(as_text=True)
        assert '"contract_no": "HT-IN-001"' in content
        assert '"material_code": "IM1"' in content
        assert '"source_purchase_order_item_id": null' in content
        with app_module.app.app_context():
            order = db.session.get(InOrder, created["id"])
            order.status = "completed"
            db.session.commit()
        assert client.get(f"/in_order/add?order_id={created['id']}").status_code == 409