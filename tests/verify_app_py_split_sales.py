# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：销售（sales）域路由迁移到 routes/sales.py。

register-on-app 模式（register_sales_routes(app)），endpoint 名与 URL 不变。

验收点：
S1. 核心 endpoint 已注册，且无 sales.xxx 前缀重复。
S2. URL 路径保持不变。
S3. 销售订单列表页可渲染（200）。
S4. 新增销售订单成功（需客户/物料/仓库）。
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
from app import db, SalesOrder  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "sales_order_list", "sales_order_add_page", "sales_order_add",
    "sales_order_detail", "sales_order_edit_page", "sales_order_edit",
    "confirm_sales_order", "cancel_sales_order", "delete_sales_order",
    "copy_sales_order", "batch_delete_sales_orders", "export_sales_orders",
    "sales_dashboard", "sales_report", "sales_outbound_list",
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


_CUSTOMER_ID = {"id": None}


def _seed_base():
    from app import Customer, Material, MaterialCategory, Unit, Warehouse
    cat = MaterialCategory(code="SCAT", name="销售分类")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="SWH", name="销售仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="SM1", name="销售物料", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    cust = Customer(code="SC1", name="测试客户", phone="13800000000")
    db.session.add_all([mat, cust])
    db.session.commit()
    _CUSTOMER_ID["id"] = cust.id


class TestSalesRegister:
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
                assert f"sales.{ep}" not in app_module.app.view_functions, f"sales.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("sales_order_list") == "/sales"
                assert url_for("sales_order_add_page") == "/sales/add"
                assert url_for("sales_order_add") == "/sales/add"
                assert url_for("sales_order_detail", id=1) == "/sales/1"
                assert url_for("confirm_sales_order", id=1) == "/sales/1/confirm"
                assert url_for("delete_sales_order", id=1) == "/sales/1/delete"
                assert url_for("export_sales_orders") == "/sales/export"

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/sales")
        assert resp.status_code == 200
        assert "销售" in resp.get_data(as_text=True)

    def test_add_sales_order(self):
        client = self._setup()
        _login(client)
        resp = client.post("/sales/add", json={
            "customer_id": _CUSTOMER_ID["id"],
            "warehouse": "销售仓",
            "items": [{"code": "SM1", "quantity": 2, "price": 10}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            order = db.session.get(SalesOrder, data["id"])
            assert order is not None
            assert order.status == "draft"
            assert len(order.items) == 1
            assert order.items[0].quantity == 2