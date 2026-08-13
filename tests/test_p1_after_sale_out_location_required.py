# -*- coding: utf-8 -*-
"""P1 回归：售后出库库位必填（AGENTS.md 规则二）。

S8 修复：开启库位管理后，AfterSaleOutOrder.location 必填，
complete_after_sale_out_order 必须拒绝未填 location 的草稿；
未开启库位管理时不得误报（向后兼容）。
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
    AfterSaleOutOrder, AfterSaleOutOrderItem, LocationInventory, Material,
    MaterialCategory, Supplier, Unit, User, Warehouse, db, generate_order_no,
    set_system_setting,
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


def _create_pending_after_sale_out_order(client, *, location=""):
    """通过 /after_sale_out/add 创建一个 pending 售后出库单，返回 id。"""
    with app_module.app.app_context():
        order_no = generate_order_no("ASO")
    payload = {
        "order_no": order_no,
        "date": "2026-08-13",
        "customer": "测试客户",
        "warehouse": "主仓",
        "location": location,
        "items": [
            {"code": "M-ASO", "quantity": 1, "price": 1}
        ],
    }
    resp = client.post("/after_sale_out/add", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = AfterSaleOutOrder.query.filter_by(order_no=payload["order_no"]).first()
        return order.id


def test_after_sale_out_location_field_exists():
    """模型必须含 location 列（S8 模型变更）。"""
    with app_module.app.app_context():
        col = AfterSaleOutOrder.__table__.columns.get("location")
        assert col is not None, "AfterSaleOutOrder 缺少 location 列"


def test_add_after_sale_out_persists_location(client):
    """add 路由必须把 location 持久化到数据库。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    oid = _create_pending_after_sale_out_order(client, location="主仓-A1")
    with app_module.app.app_context():
        order = db.session.get(AfterSaleOutOrder, oid)
        assert (order.location or "") == "主仓-A1"


def test_complete_after_sale_out_rejects_missing_location_when_enabled(client):
    """开启库位管理时，未填 location 的草稿不得被完成。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        db.session.commit()
    oid = _create_pending_after_sale_out_order(client, location="")
    resp = client.post(f"/after_sale_out/{oid}/complete")
    # api_error 默认 400
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "库位" in (data.get("msg") or ""), data
    # 状态必须仍是 pending
    with app_module.app.app_context():
        order = db.session.get(AfterSaleOutOrder, oid)
        assert order.status == "pending"


def test_complete_after_sale_out_succeeds_with_location_when_enabled(client):
    """开启库位管理且填写 location 时，完成应成功。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1")
        # 为物料在 主仓-A1 库位预置库存，避免库位库存扣减失败。
        # INV-AUDIT-002 修复后，LocationInventory 按 (material_id, warehouse_id, location)
        # 精确匹配，必须显式设置 warehouse_id 才能被 complete_after_sale_out_order
        # 带仓库维度的扣减命中。
        m = Material.query.filter_by(code="M-ASO").first()
        wh = Warehouse.query.filter_by(name="主仓").first()
        db.session.add(LocationInventory(
            material_id=m.id, warehouse_id=wh.id, location="主仓-A1", quantity=10))
        db.session.commit()
    oid = _create_pending_after_sale_out_order(client, location="主仓-A1")
    resp = client.post(f"/after_sale_out/{oid}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = db.session.get(AfterSaleOutOrder, oid)
        assert order.status == "completed"


def test_complete_after_sale_out_allows_empty_location_when_disabled(client):
    """未开启库位管理时，location 留空也能完成（向后兼容）。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    oid = _create_pending_after_sale_out_order(client, location="")
    resp = client.post(f"/after_sale_out/{oid}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
