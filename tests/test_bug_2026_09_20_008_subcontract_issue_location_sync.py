# -*- coding: utf-8 -*-
"""BUG-2026-09-20-008 回归：`/api/subcontract/quick_issue` 必须同步②库位账。

侦察发现：全仓 23 个 `add_stock`/`deduct_stock_atomic` 业务调用点中 22 处已按
INVENTORY_TRUTH §2.1「两层同时写」正确双写，唯 `app.py` 的
`api_subcontract_quick_issue`（`/api/subcontract/quick_issue`）只扣①总账、
写③流水，**从不写②库位账** —— 开启库位管理时每发一笔料 ①减②不变，
恒等式 `① = Σ②` 被打破且**无任何报错**（与 BUG-2026-08-16-002 同型）。

修复后要求：
1. 开启库位管理：发料同步扣库位账，①=②（恒等式成立）；
2. 库位键与反提交端逐字一致（`issue.location or issue.warehouse`）——
   两边落在两个不同库位会立刻产生漂移；
3. 未开启库位管理：不改动库位账（向后兼容，与既有
   `test_disabled_location_management_skips_location_inventory` 同口径）；
4. 库位账不存在时**显式报错**，不得静默成功（防错账规则）。
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
    LocationInventory, Material, MaterialCategory, StockTransaction,
    SubcontractIssue, SubcontractOrder, Supplier, Unit, User, Warehouse, db,
    set_system_setting,
)

WAREHOUSE = "主仓"
LOCATION_KEY = "主仓"  # issue.location 为空时回退发料单仓库名（与反提交端一致）


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
            Warehouse(code="WH01", name=WAREHOUSE, is_default=True),
        ])
        db.session.commit()
        db.session.add(Material(
            code="M-SC", name="委外料", spec="S",
            category_id=1, unit_id=1, supplier_id=1, stock=10, price=1,
        ))
        db.session.commit()
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _ids():
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        wh = Warehouse.query.filter_by(name=WAREHOUSE).first()
        return m.id, wh.id


def _seed_stock(with_location_row=True):
    """给主仓造库存：入库流水（③）+ 可选库位账基线行（②）。"""
    mid, wh_id = _ids()
    with app_module.app.app_context():
        db.session.add(StockTransaction(
            material_id=mid, transaction_type="in", quantity=10,
            warehouse_id=wh_id, location=None, remark="主仓入库",
        ))
        if with_location_row:
            db.session.add(LocationInventory(
                material_id=mid, warehouse_id=wh_id,
                location=LOCATION_KEY, quantity=10))
        db.session.commit()


def _create_order():
    with app_module.app.app_context():
        order = SubcontractOrder(order_no="SC-001", supplier_id=1,
                                 warehouse=WAREHOUSE, status="pending")
        db.session.add(order)
        db.session.commit()
        return order.id


def _quick_issue(client, order_id, qty=5):
    mid, _ = _ids()
    return client.post(
        "/api/subcontract/quick_issue",
        json={"order_id": order_id, "items": [{"material_id": mid, "quantity": qty}]},
    )


def _enable_location_mgmt(enabled):
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1" if enabled else "0")
        db.session.commit()


def _stock():
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        db.session.expire(m, ["stock"])
        return m.stock or 0


def _loc_rows():
    mid, wh_id = _ids()
    with app_module.app.app_context():
        return LocationInventory.query.filter_by(
            material_id=mid, warehouse_id=wh_id).all()


def test_quick_issue_syncs_location_inventory_when_enabled(client):
    """开启库位管理：发料同步扣库位账，①总账 = ②库位账（恒等式成立）。"""
    _seed_stock(with_location_row=True)
    _enable_location_mgmt(True)
    oid = _create_order()
    resp = _quick_issue(client, oid, qty=5)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get("status") == "success", resp.get_json()
    assert abs(_stock() - 5) < 1e-6, "①总账应扣减到 5"
    rows = _loc_rows()
    assert len(rows) == 1, "②库位账应仍为单行（不新增、不分裂）"
    assert abs((rows[0].quantity or 0) - 5) < 1e-6, "②库位账必须同步扣减到 5"


def test_quick_issue_location_key_matches_revert_side(client):
    """库位键必须与反提交端逐字一致：issue.location 为空时回退发料单仓库名。"""
    _seed_stock(with_location_row=True)
    _enable_location_mgmt(True)
    oid = _create_order()
    assert _quick_issue(client, oid, qty=3).get_json().get("status") == "success"
    rows = _loc_rows()
    assert len(rows) == 1
    assert rows[0].location == LOCATION_KEY, \
        f"库位键应为「{LOCATION_KEY}」（与 subcontract.py 反提交端同键），实际 {rows[0].location}"
    # 发料单自身未带 location，反提交端 `issue.location or issue.warehouse`
    # 会解析成同一个键，扣减与回退不会落到两个库位。
    with app_module.app.app_context():
        issue = SubcontractIssue.query.order_by(SubcontractIssue.id.desc()).first()
        assert (issue.location or issue.warehouse) == LOCATION_KEY


def test_quick_issue_skips_location_inventory_when_disabled(client):
    """未开启库位管理：不改动库位账（向后兼容旧行为）。"""
    _seed_stock(with_location_row=True)
    _enable_location_mgmt(False)
    oid = _create_order()
    resp = _quick_issue(client, oid, qty=5)
    assert resp.get_json().get("status") == "success", resp.get_json()
    assert abs(_stock() - 5) < 1e-6, "①总账照常扣减"
    rows = _loc_rows()
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 10) < 1e-6, "关库位管理时②库位账保持不动"


def test_quick_issue_errors_instead_of_silent_when_location_missing(client):
    """库位账无对应行时显式报错，不得静默成功（防错账规则）。"""
    _seed_stock(with_location_row=False)  # 只有流水，无库位账基线
    _enable_location_mgmt(True)
    oid = _create_order()
    resp = _quick_issue(client, oid, qty=5)
    data = resp.get_json()
    assert data.get("status") == "error", f"库位账缺失必须报错，实际: {data}"
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M-SC").first()
        db.session.expire(m, ["stock"])
        assert abs((m.stock or 0) - 10) < 1e-6, "报错路径必须回滚，①总账不得被扣"
