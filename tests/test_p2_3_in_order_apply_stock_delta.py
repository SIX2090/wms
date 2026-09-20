# -*- coding: utf-8 -*-
"""P2-3 批 2：in_order 全量改道 apply_stock_delta 的回归锁（A9）。

收敛后 in_order 的 9 处库存写入（完成 / 自动下推领料 / 改已入库明细
增·删·改量 / 反提交 / 批量完成 / 批量反审）全部经唯一入口，本测试锁两层：

1. 结构锁（防回退）：in_order.py 不得再裸调 add_stock / deduct_stock /
   deduct_stock_atomic / update_location_inventory /
   deduct_location_inventory_atomic；5 个路由函数必须导入 apply_stock_delta。
2. 行为锁（防改坏）：开库位管理下真实走一遍完成/反提交/批量/改量，
   断言三账（①总账 + ③流水 + ②库位账）同增同减、方向对称。

函数名即 A9 锚点（lint 按 test_<函数名> 精确匹配）。
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
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder, InOrderItem, LocationInventory, Material, StockTransaction,
    Supplier, Unit, User, Warehouse, db, set_system_setting,
)
from werkzeug.security import generate_password_hash  # noqa: E402
from services.warehouse_stock_service import apply_stock_delta  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

IN_ORDER_SRC = (APP_DIR / "routes" / "in_order.py").read_text(encoding="utf-8")

WAREHOUSE = "收敛仓"
LOCATION = "A-01"
RAW_PRIMITIVES = (
    "add_stock(", "deduct_stock(", "deduct_stock_atomic(",
    "update_location_inventory(", "deduct_location_inventory_atomic(",
)
# 需要经入口写库存的路由函数（P2-3 批 2 收敛清单）
CONVERGED_ROUTES = (
    "complete_in_order", "update_completed_in_order", "revert_in_order",
    "batch_complete_in_order", "batch_revert_in_order",
)


def _route_source(func_name):
    """截取单个路由函数的源码块（到下一个 @app.route 为止），用于按函数断言。"""
    start = IN_ORDER_SRC.index(f"def {func_name}(")
    nxt = IN_ORDER_SRC.find("    @app.route", start)
    return IN_ORDER_SRC[start:nxt] if nxt != -1 else IN_ORDER_SRC[start:]


def _code_lines(text):
    """去掉注释行，避免把说明文字里的原语名误判为调用。"""
    return [ln for ln in text.splitlines() if not ln.strip().startswith("#")]


def _seed():
    db.drop_all()
    db.create_all()
    unit = Unit(code="PCS", name="个")
    warehouse = Warehouse(code="CONV_WH", name=WAREHOUSE, status="active", is_default=True)
    supplier = Supplier(code="CONV_SUP", name="收敛供应商")
    user = User(
        username="p23_admin", password_hash=generate_password_hash("admin"),
        role="admin", status="normal", must_change_password=False,
    )
    # 两个物料：批量用例必须避开「同日同供应商同物料」重复单据异常检测
    # （_check_in_order_anomalies 第 3 项，批量完成无 force 通道会直接跳过）。
    material = Material(code="CONV_MAT", name="收敛物料", unit=unit, stock=0, price=1)
    material2 = Material(code="CONV_MAT2", name="收敛物料二", unit=unit, stock=0, price=1)
    db.session.add_all([unit, warehouse, supplier, user, material, material2])
    db.session.commit()
    set_system_setting("location_management_enabled", "1")
    db.session.commit()
    return supplier.id


def _login(client):
    resp = client.post("/login", data={"username": "p23_admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code in (200, 302)


def _create_in_order(client, supplier_id, quantity=10, material_code="CONV_MAT"):
    """开库位管理时建单即要求库位（AGENTS.md 规则二），随建单传入。"""
    resp = client.post("/in_order/add", json={
        "business_type": "采购入库",
        "supplier_id": supplier_id,
        "warehouse": WAREHOUSE,
        "location": LOCATION,
        "auto_push_requisition": False,
        "items": [{"code": material_code, "quantity": quantity, "price": 1}],
    })
    body = resp.get_json()
    assert body["status"] == "success", body
    return body["id"]


def _assert_location_persisted(order_id):
    """确认建单接口真的落了库位（否则后续断言会被空库位掩盖）。"""
    order = db.session.get(InOrder, order_id)
    assert (order.location or '').strip() == LOCATION


def _material(code="CONV_MAT"):
    return Material.query.filter_by(code=code).one()


def _loc_qty(location=LOCATION, code="CONV_MAT"):
    wh = Warehouse.query.filter_by(name=WAREHOUSE).one()
    inv = LocationInventory.query.filter_by(
        material_id=_material(code).id, location=location, warehouse_id=wh.id).first()
    return inv.quantity if inv else None


def _ledger_qty(transaction_type, code="CONV_MAT"):
    m = _material(code)
    txns = StockTransaction.query.filter_by(
        material_id=m.id, transaction_type=transaction_type).all()
    return sum(t.quantity for t in txns)


@pytest.fixture()
def client():
    with app_module.app.app_context():
        supplier_id = _seed()
    c = app_module.app.test_client()
    _login(c)
    c.supplier_id = supplier_id
    yield c


# ---------------------------------------------------------------- 结构锁

def test_in_order_has_no_raw_stock_primitives():
    """in_order.py 不再裸调任何库存原语（P2-3 批 2 收敛结论）。"""
    for lineno, line in enumerate(_code_lines(IN_ORDER_SRC), start=1):
        for prim in RAW_PRIMITIVES:
            assert prim not in line, (
                f"in_order.py 第 {lineno} 行仍在裸调 {prim}，必须改道 apply_stock_delta")


def test_converged_routes_import_apply_stock_delta():
    """5 个库存写入路由函数都必须经唯一入口。"""
    for func in CONVERGED_ROUTES:
        src = _route_source(func)
        assert "apply_stock_delta" in src, f"{func} 未使用 apply_stock_delta"
        assert re.search(r"from services\.warehouse_stock_service import apply_stock_delta", src), (
            f"{func} 未按顶级包 services 导入（BUG-2026-09-06-003：生产布局 app 非包）")


# ---------------------------------------------------------------- 行为锁

def test_complete_in_order_writes_three_ledgers(client):
    """完成入库（开库位管理）：①总账 +10、③流水 +10、②库位账 +10。"""
    order_id = _create_in_order(client, client.supplier_id, quantity=10)
    with app_module.app.app_context():
        _assert_location_persisted(order_id)
    body = client.post(f"/in_order/{order_id}/complete?force=1").get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 10, '①总账未入账'
        assert _ledger_qty("in") == 10, '③流水未写或数量不符'
        assert _loc_qty() == 10, '②库位账未同步（P2-3 要治的静默分裂）'


def test_revert_in_order_reverses_three_ledgers(client):
    """反提交：与完成严格对称，三账同时归零。"""
    order_id = _create_in_order(client, client.supplier_id, quantity=10)
    with app_module.app.app_context():
        _assert_location_persisted(order_id)
    assert client.post(f"/in_order/{order_id}/complete?force=1").get_json()["status"] == "success"
    body = client.post(f"/in_order/{order_id}/revert").get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 0, '①总账未回退'
        assert _ledger_qty("in") + _ledger_qty("revert_in") == 0, '③流水未对称回退'
        assert _loc_qty() == 0, '②库位账未回退（反提交漏扣库位是历史 BUG 模式）'


def test_batch_complete_and_batch_revert_three_ledgers(client):
    """批量完成 / 批量反审：同样三账一致（批量路径最易漏写库位账）。"""
    ids = [
        _create_in_order(client, client.supplier_id, quantity=5, material_code="CONV_MAT"),
        _create_in_order(client, client.supplier_id, quantity=7, material_code="CONV_MAT2"),
    ]
    with app_module.app.app_context():
        for oid in ids:
            _assert_location_persisted(oid)
    body = client.post("/in_order/batch_complete", json={"ids": ids}).get_json()
    assert body["status"] == "success", body
    assert body.get("completed") == 2, body

    with app_module.app.app_context():
        db.session.refresh(_material())
        db.session.refresh(_material("CONV_MAT2"))
        assert _material().stock == 5 and _material("CONV_MAT2").stock == 7
        assert _loc_qty(code="CONV_MAT") == 5, '批量完成漏写库位账'
        assert _loc_qty(code="CONV_MAT2") == 7, '批量完成漏写库位账（第二张单）'

    body = client.post("/in_order/batch_revert", json={"ids": ids}).get_json()
    assert body["status"] == "success", body
    assert body.get("reverted") == 2, body

    with app_module.app.app_context():
        db.session.refresh(_material())
        db.session.refresh(_material("CONV_MAT2"))
        assert _material().stock == 0 and _material("CONV_MAT2").stock == 0
        assert _loc_qty(code="CONV_MAT") == 0, '批量反审漏还原库位账'
        assert _loc_qty(code="CONV_MAT2") == 0, '批量反审漏还原库位账（第二张单）'


def test_update_completed_in_order_delta_three_ledgers(client):
    """改已入库明细数量：增 5 / 减 3，三账随 delta 同步、方向正确。"""
    order_id = _create_in_order(client, client.supplier_id, quantity=10)
    with app_module.app.app_context():
        _assert_location_persisted(order_id)
    assert client.post(f"/in_order/{order_id}/complete?force=1").get_json()["status"] == "success"

    with app_module.app.app_context():
        item = InOrderItem.query.filter_by(in_order_id=order_id).one()
        item_id = item.id

    # 10 → 15（delta +5）
    body = client.post(f"/in_order/{order_id}/update_completed", json={
        "items": [{"id": item_id, "quantity": 15, "price": 1}],
    }).get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 15
        assert _loc_qty() == 15, '增量未同步库位账'

    # 15 → 12（delta -3）
    body = client.post(f"/in_order/{order_id}/update_completed", json={
        "items": [{"id": item_id, "quantity": 12, "price": 1}],
    }).get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 12
        assert _loc_qty() == 12, '减量未同步库位账'
        assert _ledger_qty("adjust_in_item") == 2, '增减两条流水净额应为 +2'


def test_delete_completed_in_order_item_three_ledgers(client):
    """删除已入库明细：三账按该行数量回退（含库位账）。"""
    order_id = _create_in_order(client, client.supplier_id, quantity=10)
    with app_module.app.app_context():
        _assert_location_persisted(order_id)
    assert client.post(f"/in_order/{order_id}/complete?force=1").get_json()["status"] == "success"

    with app_module.app.app_context():
        item_id = InOrderItem.query.filter_by(in_order_id=order_id).one().id

    body = client.post(f"/in_order/{order_id}/update_completed", json={
        "deleted_items": [item_id], "items": [],
    }).get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 0, '删除明细未回退总账'
        assert _loc_qty() == 0, '删除明细未回退库位账'
        assert _ledger_qty("delete_in_item") == -10
