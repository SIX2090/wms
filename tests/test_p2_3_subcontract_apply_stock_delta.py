# -*- coding: utf-8 -*-
"""P2-3 批 4：subcontract 全量改道 apply_stock_delta 的回归锁（A9）。

收敛后 subcontract 6 处写入点（quick_issue / quick_receive / complete_issue /
revert_issue / complete_receive / revert_receive，含 1 处旧包装 deduct_stock）
全部经唯一入口。本测试锁两层：

1. 结构锁（防回退）：subcontract.py 不得再裸调 add_stock / deduct_stock /
   deduct_stock_atomic / update_location_inventory /
   deduct_location_inventory_atomic；6 个路由函数必须导入 apply_stock_delta。
2. 行为锁（防改坏）：开库位管理下真实路由发料/收货/反提交，
   断言三账（①总账 + ③流水 + ②库位账）同增同减、方向对称。
   库位键口径与 BUG-2026-08-16-001 / BUG-2026-09-20-008 锁定的
   `issue.location or issue.warehouse` 逐字一致。

函数名即 A9 锚点（lint 按 test_<函数名> 精确匹配）。
"""
from __future__ import annotations

import os
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
    LocationInventory, Material, StockTransaction, SubcontractIssue,
    SubcontractIssueItem, SubcontractOrder, SubcontractItem,
    SubcontractReceive, SubcontractReceiveItem, Supplier, Unit, User,
    Warehouse, db, generate_order_no, set_system_setting,
)
from werkzeug.security import generate_password_hash  # noqa: E402
from services.warehouse_stock_service import apply_stock_delta  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

SRC = (APP_DIR / "routes" / "subcontract.py").read_text(encoding="utf-8")

WAREHOUSE = "委外仓"
LOCATION = "C-01"
RAW_PRIMITIVES = (
    "add_stock(", "deduct_stock(", "deduct_stock_atomic(",
    "update_location_inventory(", "deduct_location_inventory_atomic(",
)
CONVERGED_ROUTES = (
    "quick_issue_subcontract", "quick_receive_subcontract",
    "complete_subcontract_issue", "revert_subcontract_issue",
    "complete_subcontract_receive", "revert_subcontract_receive",
)


def _seed():
    db.drop_all()
    db.create_all()
    unit = Unit(code="PCS", name="个")
    warehouse = Warehouse(code="SC_WH", name=WAREHOUSE, status="active", is_default=True)
    supplier = Supplier(code="SC_SUP", name="委外供应商")
    user = User(
        username="p23b4_admin", password_hash=generate_password_hash("admin"),
        role="admin", status="normal", must_change_password=False,
    )
    material = Material(code="SC_MAT", name="委外物料", unit=unit, stock=0, price=1)
    db.session.add_all([unit, warehouse, supplier, user, material])
    db.session.commit()
    set_system_setting("location_management_enabled", "1")
    db.session.commit()
    return supplier.id, unit.id


def _login(client):
    resp = client.post("/login", data={"username": "p23b4_admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code in (200, 302)


def _material():
    return Material.query.filter_by(code="SC_MAT").one()


def _loc_qty():
    wh = Warehouse.query.filter_by(name=WAREHOUSE).one()
    inv = LocationInventory.query.filter_by(
        material_id=_material().id, location=LOCATION, warehouse_id=wh.id).first()
    return inv.quantity if inv else None


def _ledger_net(transaction_types):
    m = _material()
    txns = StockTransaction.query.filter(
        StockTransaction.material_id == m.id,
        StockTransaction.transaction_type.in_(transaction_types)).all()
    return sum(t.quantity for t in txns)


def _stock_in(quantity):
    """铺底库存（原语内部读 current_user，需请求上下文提供匿名用户）。"""
    with app_module.app.test_request_context():
        ok, err = apply_stock_delta(
            _material(), quantity, transaction_type="in",
            warehouse=WAREHOUSE, location=LOCATION)
        assert ok, err
        db.session.commit()


def _create_subcontract_order(supplier_id):
    order = SubcontractOrder(
        order_no=generate_order_no("WW"), supplier_id=supplier_id,
        warehouse=WAREHOUSE, status="pending",
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(SubcontractItem(
        subcontract_order_id=order.id, material_id=_material().id, quantity=10))
    db.session.commit()
    return order.id


@pytest.fixture()
def client():
    with app_module.app.app_context():
        supplier_id, _unit_id = _seed()
    c = app_module.app.test_client()
    _login(c)
    c.supplier_id = supplier_id
    yield c


# ---------------------------------------------------------------- 结构锁

def test_subcontract_has_no_raw_stock_primitives():
    """subcontract.py 不再裸调任何库存原语（P2-3 批 4 收敛结论）。"""
    for lineno, line in enumerate(SRC.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        for prim in RAW_PRIMITIVES:
            assert prim not in line, (
                f"subcontract.py 第 {lineno} 行仍在裸调 {prim}，必须改道 apply_stock_delta")


def test_converged_routes_import_apply_stock_delta():
    """6 个库存写入路由函数都必须经唯一入口（顶级包 services 导入）。"""
    for func in CONVERGED_ROUTES:
        start = SRC.index(f"def {func}(")
        nxt = SRC.find("    @app.route", start)
        body = SRC[start:nxt] if nxt != -1 else SRC[start:]
        assert "from services.warehouse_stock_service import apply_stock_delta" in body, (
            f"{func} 未按顶级包 services 导入 apply_stock_delta")


# ---------------------------------------------------------------- 行为锁

def test_quick_issue_subcontract_deducts_three_ledgers(client):
    """委外快速发料（表单）：①总账 -6、③流水 -6、②库位账 -6。"""
    with app_module.app.app_context():
        _stock_in(20)
        oid = _create_subcontract_order(client.supplier_id)
    resp = client.post(f"/subcontract/{oid}/issue", data={
        "material_code": "SC_MAT", "quantity": "6", "location": LOCATION,
    })
    body = resp.get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 14, '①总账未扣减'
        assert _ledger_net(["in", "subcontract_issue"]) == 14, '③流水净额不符'
        assert _loc_qty() == 14, '②库位账未同步扣减（BUG-2026-09-20-008 同型）'


def test_complete_and_revert_subcontract_issue_three_ledgers(client):
    """发料单完成 + 反提交：三账同减同增、方向对称。"""
    with app_module.app.app_context():
        _stock_in(20)
        issue = SubcontractIssue(
            issue_no=generate_order_no("SF"), subcontract_order_id=None,
            supplier_id=client.supplier_id, warehouse=WAREHOUSE,
            location=LOCATION, status="pending",
        )
        db.session.add(issue)
        db.session.flush()
        db.session.add(SubcontractIssueItem(
            issue_id=issue.id, material_id=_material().id, quantity=5,
            unit_id=_material().unit_id,
        ))
        db.session.commit()
        issue_id = issue.id

    body = client.post(f"/subcontract/issue/{issue_id}/complete").get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 15 and _loc_qty() == 15

    body = client.post(f"/subcontract/issue/{issue_id}/revert").get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 20, '①总账未恢复'
        assert _loc_qty() == 20, '②库位账未恢复'
        assert _ledger_net(["in", "subcontract_issue", "revert_subcontract_issue"]) == 20


def test_complete_and_revert_subcontract_receive_three_ledgers(client):
    """委外收货完成 + 反提交：三账同增同减、方向对称。"""
    with app_module.app.app_context():
        receive = SubcontractReceive(
            receive_no=generate_order_no("SR"), subcontract_order_id=None,
            supplier_id=client.supplier_id, warehouse=WAREHOUSE,
            location=LOCATION, status="pending",
        )
        db.session.add(receive)
        db.session.flush()
        db.session.add(SubcontractReceiveItem(
            receive_id=receive.id, material_id=_material().id, quantity=7,
            scrap_quantity=0, unit_id=_material().unit_id, price=1, amount=7,
        ))
        db.session.commit()
        receive_id = receive.id

    body = client.post(f"/subcontract/receive/{receive_id}/complete").get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 7, '①总账未入账'
        assert _loc_qty() == 7, '②库位账未同步（收货方向漏写是历史 BUG 模式）'

    # 反提交扣回：先确认库存充足（7 全在本仓）
    body = client.post(f"/subcontract/receive/{receive_id}/revert").get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 0, '①总账未回退'
        assert _loc_qty() == 0, '②库位账未回退'
        assert _ledger_net(["subcontract_receive", "revert_subcontract_receive"]) == 0


def test_quick_receive_subcontract_adds_three_ledgers(client):
    """委外快速收货（表单）：三账同增。"""
    with app_module.app.app_context():
        oid = _create_subcontract_order(client.supplier_id)
    resp = client.post(f"/subcontract/{oid}/receive", data={
        "material_code": "SC_MAT", "quantity": "4", "price": "1",
        "location": LOCATION,
    })
    body = resp.get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 4, '①总账未入账'
        assert _ledger_net(["subcontract_receive"]) == 4, '③流水未写'
        assert _loc_qty() == 4, '②库位账未同步'
