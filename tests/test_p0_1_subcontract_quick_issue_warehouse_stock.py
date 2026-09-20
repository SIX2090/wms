# -*- coding: utf-8 -*-
"""P0-1 回归：委外快速发料预校验按「委外单仓库」口径校验库存。

修复前：api_subcontract_quick_issue 用全局 Material.stock 预校验，
导致 A 仓有库存即可掩护 B 仓委外单发料（扣减在 B 仓打负账面），
与 BUG-2026-08-16-009（出库单）/ BUG-2026-09-19-001（售后出库 /
deduct_stock_atomic 扣减端）属同一根因（A11 / R2）。

修复后（预校验与扣减端 deduct_stock_atomic 口径严格对齐）：
1. 双仓场景：库存全部归属副仓时，主仓委外单发料必须被拒；
2. 正常场景：库存归属本仓时发料放行并正确扣减；
3. 兼容场景：库存全部来自无法归属仓库的历史遗留流水
   （warehouse_id/location 全空）时，回退全局口径放行；
4. 数据质量：委外单仓库名无法解析时必须提前拒绝，
   不再落到扣减端才报"请选择有效仓库"。
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
    Material, MaterialCategory, StockTransaction, SubcontractOrder,
    Supplier, Unit, User, Warehouse, db, set_system_setting,
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
            code="M-SC", name="委外料", spec="S",
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


def _create_subcontract_order(warehouse="主仓"):
    """直接在库中创建一张委外单，返回 id。"""
    with app_module.app.app_context():
        order = SubcontractOrder(
            order_no=f"SC-{warehouse}-001",
            supplier_id=1,
            warehouse=warehouse,
            status="pending",
        )
        db.session.add(order)
        db.session.commit()
        return order.id


def _quick_issue(client, order_id, qty=5):
    return client.post(
        "/api/subcontract/quick_issue",
        json={"order_id": order_id, "items": [{"material_id": 1, "quantity": qty}]},
    )


def _add_inbound_tx(warehouse_name, qty=10):
    """给指定仓库加一条入库流水（库存归属该仓）。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        wh = Warehouse.query.filter_by(name=warehouse_name).first()
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=qty,
            warehouse_id=wh.id, location=None, remark=f"{warehouse_name}入库",
        ))
        db.session.commit()


def test_issue_rejected_when_stock_only_in_other_warehouse(client):
    """库存全部归属副仓时，主仓委外单发料必须被拒（双仓隔离）。"""
    _add_inbound_tx("副仓")
    oid = _create_subcontract_order(warehouse="主仓")
    resp = _quick_issue(client, oid)
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "库存不足" in (data.get("msg") or ""), data
    assert "主仓" in (data.get("msg") or ""), data
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        assert m.stock == 10  # 总账未被扣减


def test_issue_allowed_when_stock_in_same_warehouse(client):
    """库存归属本仓时发料放行并正确扣减（控制组）。"""
    _add_inbound_tx("主仓")
    oid = _create_subcontract_order(warehouse="主仓")
    resp = _quick_issue(client, oid)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        assert m.stock == 5  # 总账已扣减


def test_issue_allowed_when_stock_unattributed(client):
    """库存全部来自无归属历史遗留流水时，回退全局口径放行（R2 脏数据兼容，
    与 deduct_stock_atomic 的 BUG-2026-09-19-001 兜底同口径）。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        db.session.add(StockTransaction(
            material_id=m.id, transaction_type="in", quantity=10,
            warehouse_id=None, location=None, remark="历史遗留",
        ))
        db.session.commit()
    oid = _create_subcontract_order(warehouse="主仓")
    resp = _quick_issue(client, oid)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        assert m.stock == 5  # 总账已扣减


def test_issue_rejected_when_warehouse_invalid(client):
    """委外单仓库名无法解析时提前拒绝（数据质量守门）。"""
    _add_inbound_tx("主仓")
    oid = _create_subcontract_order(warehouse="不存在仓")
    resp = _quick_issue(client, oid)
    assert resp.status_code in (200, 400)
    data = resp.get_json()
    assert data.get("status") == "error", data
    assert "仓库无效" in (data.get("msg") or ""), data
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        assert m.stock == 10  # 总账未被扣减
