# -*- coding: utf-8 -*-
"""BUG-2026-09-19-001 回归：售后出库完成按「单据仓库」口径校验库存。

修复前：complete_after_sale_out_order 用全局 Material.stock 校验，
导致 A 仓有库存即可掩护 B 仓售后出库单完成（超卖 B 仓），
与 BUG-2026-08-16-009（出库单同根因）属同一模式（A11 / R2）。

修复后：
1. 双仓场景：库存全部归属 B 仓时，主仓售后出库单完成必须被拒；
2. 兼容场景：库存全部来自无法归属仓库的历史遗留流水
   （warehouse_id/location 全空）时，回退全局口径放行，
   避免"有库存却拒绝完成"（BUG-2026-08-18-002 同类）。
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
    AfterSaleOutOrder, AfterSaleOutOrderItem, Material, MaterialCategory,
    StockTransaction, Supplier, Unit, User, Warehouse, db, generate_order_no,
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
            Warehouse(code="WH02", name="副仓", is_default=False),
        ])
        db.session.commit()
        db.session.add(Material(
            code="M-ASO", name="售后料", spec="S",
            category_id=1, unit_id=1, supplier_id=1, stock=10, price=1,
        ))
        db.session.commit()
        # 双仓隔离判定需要关闭库位管理（走流水净额口径）
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _create_pending_order(client, warehouse="主仓"):
    """通过 /after_sale_out/add 创建一个 pending 售后出库单，返回 id。"""
    with app_module.app.app_context():
        order_no = generate_order_no("ASO")
    payload = {
        "order_no": order_no,
        "date": "2026-09-19",
        "customer": "测试客户",
        "warehouse": warehouse,
        "location": "",
        "items": [{"code": "M-ASO", "quantity": 5, "price": 1}],
    }
    resp = client.post("/after_sale_out/add", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = AfterSaleOutOrder.query.filter_by(order_no=payload["order_no"]).first()
        return order.id


def test_complete_rejected_when_stock_only_in_other_warehouse(client):
    """库存全部归属副仓时，主仓售后出库单完成必须被拒（双仓隔离）。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-ASO").first()
        wh_b = Warehouse.query.filter_by(name="副仓").first()
        # 物料的 10 件库存全部来自副仓的入库流水
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=10,
            warehouse_id=wh_b.id, location=None, remark="副仓入库",
        ))
        db.session.commit()
    oid = _create_pending_order(client, warehouse="主仓")
    resp = client.post(f"/after_sale_out/{oid}/complete")
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "库存不足" in (data.get("msg") or ""), data
    with app_module.app.app_context():
        order = db.session.get(AfterSaleOutOrder, oid)
        assert order.status == "pending"
        m = Material.query.filter_by(code="M-ASO").first()
        assert m.stock == 10  # 总账未被扣减


def test_complete_allowed_when_stock_unattributed(client):
    """库存全部来自无归属历史遗留流水时，回退全局口径放行（R2 脏数据兼容）。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-ASO").first()
        # 历史遗留流水：warehouse_id/location 全空，无法归属任何仓库
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=10,
            warehouse_id=None, location=None, remark="历史遗留",
        ))
        db.session.commit()
    oid = _create_pending_order(client, warehouse="主仓")
    resp = client.post(f"/after_sale_out/{oid}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        order = db.session.get(AfterSaleOutOrder, oid)
        assert order.status == "completed"
        m = Material.query.filter_by(code="M-ASO").first()
        assert m.stock == 5  # 总账已扣减
