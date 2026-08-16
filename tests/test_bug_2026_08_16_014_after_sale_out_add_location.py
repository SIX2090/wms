# -*- coding: utf-8 -*-
"""BUG-2026-08-16-014 回归：售后出库新增路由补 库位必填 + 仓库 active 校验。

开启库位管理时，/after_sale_out/add 必须拒绝未填 location 的草稿（否则完成路由的
库位门禁会卡死工作流、草稿无法完成）；未开启库位管理时不得误报（向后兼容）。
同时新增路由必须校验仓库处于启用状态（assert_warehouse_active）。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    AfterSaleOutOrder, Material, MaterialCategory, Supplier, Unit, User,
    Warehouse, db, generate_order_no, set_system_setting,
)


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="供应商"),
            Warehouse(code="WH01", name="主仓", is_default=True),
        ])
        db.session.commit()
        db.session.add(Material(
            code="M-ASO", name="售后料", spec="S",
            category_id=1, unit_id=1, supplier_id=1, stock=10, price=1,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _payload(location=""):
    with app_module.app.app_context():
        order_no = generate_order_no("ASO")
    return {
        "order_no": order_no,
        "date": "2026-08-16",
        "customer": "测试客户",
        "warehouse": "主仓",
        "location": location,
        "items": [{"code": "M-ASO", "quantity": 1, "price": 1}],
    }


def test_add_rejects_missing_location_when_enabled(client):
    """开启库位管理时，新增路由必须拒绝未填 location 的草稿。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = client.post("/after_sale_out/add", json=_payload(location=""))
    assert resp.status_code == 400, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "库位" in (data.get("msg") or ""), data
    # 不得产生草稿
    with app_module.app.app_context():
        assert AfterSaleOutOrder.query.filter_by(customer="测试客户").first() is None


def test_add_succeeds_with_location_when_enabled(client):
    """开启库位管理且填写 location 时，新增应成功并持久化。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    resp = client.post("/after_sale_out/add", json=_payload(location="主仓-A1"))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = AfterSaleOutOrder.query.filter_by(customer="测试客户").first()
        assert order is not None
        assert (order.location or "") == "主仓-A1"


def test_add_allows_empty_location_when_disabled(client):
    """未开启库位管理时，location 留空也能新增（向后兼容）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    resp = client.post("/after_sale_out/add", json=_payload(location=""))
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data