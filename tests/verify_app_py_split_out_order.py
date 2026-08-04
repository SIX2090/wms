# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：销售出库（out_order）域路由迁移到 routes/out_order.py。

register-on-app 模式（register_out_order_routes(app)），endpoint 名与 URL 不变。

验收点：
S1. 核心 endpoint 已注册，且无 out_order.xxx 前缀重复。
S2. URL 路径保持不变。
S3. 出库单列表页可渲染（200）。
S4. 新增领料出库单成功（需物料/仓库）。
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
from app import OutOrder, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "out_order_list", "out_order_detail", "out_order_add_page",
    "add_out_order", "add_out_order_item", "delete_out_order_item",
    "update_out_order_item", "check_out_order_anomalies", "complete_out_order",
    "revert_out_order", "delete_out_order", "batch_delete_out_order",
    "batch_complete_out_order", "export_out_order", "export_single_out_order",
    "out_order_print_template_list", "print_out_order",
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


def _seed_base():
    from app import Material, MaterialCategory, Unit, Warehouse
    cat = MaterialCategory(code="OCAT", name="出库分类")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="OWH", name="出库仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="OM1", name="出库物料", category_id=cat.id, unit_id=unit.id, stock=100, price=5)
    db.session.add(mat)
    db.session.commit()


class TestOutOrderRegister:
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
                assert f"out_order.{ep}" not in app_module.app.view_functions, f"out_order.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                # 原 app.py 中 out_order_list 同时注册 /out_order 与 /other_out_order，
                # url_for 返回先注册的规则（/other_out_order），拆分后保持该行为不变。
                assert url_for("out_order_list") == "/other_out_order"
                assert url_for("out_order_list", _external=False) in ("/out_order", "/other_out_order")
                assert url_for("add_out_order") == "/out_order/add"
                assert url_for("out_order_detail", id=1) == "/out_order/1"
                assert url_for("complete_out_order", id=1) == "/out_order/1/complete"
                assert url_for("delete_out_order", id=1) == "/out_order/1/delete"
                assert url_for("export_out_order") == "/out_order/export"

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/out_order")
        assert resp.status_code == 200
        assert ("出库" in resp.get_data(as_text=True)) or ("领料" in resp.get_data(as_text=True))

    def test_add_out_order(self):
        client = self._setup()
        _login(client)
        resp = client.post("/out_order/add", json={
            "business_type": "领料单",
            "date": "2026-08-04",
            "warehouse": "出库仓",
            "items": [{"code": "OM1", "quantity": 2, "price": 5}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            order = db.session.get(OutOrder, data["id"])
            assert order is not None
            assert order.status == "pending"
            assert order.business_type == "领料单"
            assert len(order.items) == 1
            assert order.items[0].quantity == 2