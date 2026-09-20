# -*- coding: utf-8 -*-
"""P2-3 批 3：out_order + after_sale_out 全量改道 apply_stock_delta 的回归锁（A9）。

收敛后 out_order 3 处（complete / revert / batch_complete）与 after_sale_out
2 处（complete / revert）全部经唯一入口。本测试锁两层：

1. 结构锁（防回退）：两个路由文件不得再裸调 add_stock / deduct_stock /
   deduct_stock_atomic / update_location_inventory /
   deduct_location_inventory_atomic；5 个路由函数必须导入 apply_stock_delta。
2. 行为锁（防改坏）：开库位管理下真实路由完成/反提交/批量完成，
   断言三账（①总账 + ③流水 + ②库位账）同增同减、方向对称。

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
    AfterSaleOutOrder, InOrder, LocationInventory, Material, MaterialCategory,
    OutOrder, OutOrderItem, StockTransaction, Supplier, Unit, User, Warehouse,
    db, generate_order_no, set_system_setting,
)
from datetime import date  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402
from services.warehouse_stock_service import apply_stock_delta  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

OUT_SRC = (APP_DIR / "routes" / "out_order.py").read_text(encoding="utf-8")
ASO_SRC = (APP_DIR / "routes" / "after_sale_out.py").read_text(encoding="utf-8")

WAREHOUSE = "批三仓"
LOCATION = "B-01"
RAW_PRIMITIVES = (
    "add_stock(", "deduct_stock(", "deduct_stock_atomic(",
    "update_location_inventory(", "deduct_location_inventory_atomic(",
)
CONVERGED = {
    "out_order.py": (OUT_SRC, ("complete_out_order", "revert_out_order",
                               "batch_complete_out_order")),
    "after_sale_out.py": (ASO_SRC, ("complete_after_sale_out_order",
                                    "revert_after_sale_out_order")),
}


def _seed():
    db.drop_all()
    db.create_all()
    unit = Unit(code="PCS", name="个")
    warehouse = Warehouse(code="B3_WH", name=WAREHOUSE, status="active", is_default=True)
    supplier = Supplier(code="B3_SUP", name="批三供应商")
    user = User(
        username="p23b3_admin", password_hash=generate_password_hash("admin"),
        role="admin", status="normal", must_change_password=False,
    )
    material = Material(code="B3_MAT", name="批三物料", unit=unit, stock=0, price=1)
    material2 = Material(code="B3_MAT2", name="批三物料二", unit=unit, stock=0, price=1)
    db.session.add_all([unit, warehouse, supplier, user, material, material2])
    db.session.commit()
    set_system_setting("location_management_enabled", "1")
    db.session.commit()


def _login(client):
    resp = client.post("/login", data={"username": "p23b3_admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code in (200, 302)


def _material(code="B3_MAT"):
    return Material.query.filter_by(code=code).one()


def _loc_qty(code="B3_MAT"):
    wh = Warehouse.query.filter_by(name=WAREHOUSE).one()
    inv = LocationInventory.query.filter_by(
        material_id=_material(code).id, location=LOCATION, warehouse_id=wh.id).first()
    return inv.quantity if inv else None


def _ledger_net(transaction_types, code="B3_MAT"):
    m = _material(code)
    txns = StockTransaction.query.filter(
        StockTransaction.material_id == m.id,
        StockTransaction.transaction_type.in_(transaction_types)).all()
    return sum(t.quantity for t in txns)


def _stock_in(quantity, code="B3_MAT"):
    """铺底库存：经同一入口入库（开库位管理下三账同写）。

    原语内部读 current_user（流水 operator_id），需请求上下文提供匿名用户
    （is_authenticated=False → operator_id=None，与生产未登录写入口径一致）。
    """
    with app_module.app.test_request_context():
        ok, err = apply_stock_delta(
            _material(code), quantity, transaction_type="in",
            warehouse=WAREHOUSE, location=LOCATION)
        assert ok, err
        db.session.commit()


def _create_out_order(quantity, code="B3_MAT"):
    """DB 直建 pending 领料出库单（complete 只依赖单据字段与库存）。"""
    m = _material(code)
    order = OutOrder(
        order_no=generate_order_no("OUT"), date=date.today(),
        business_type="领料出库", warehouse=WAREHOUSE, location=LOCATION,
        purpose="批三测试", status="pending",
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(OutOrderItem(
        out_order_id=order.id, material_id=m.id,
        quantity=quantity, price=1, amount=quantity,
    ))
    db.session.commit()
    return order.id


def _create_after_sale_order(client, quantity, code="B3_MAT"):
    """test_client 请求不能在 app_context 里发（嵌套上下文会拿不到 JSON 响应）。"""
    with app_module.app.app_context():
        order_no = generate_order_no("ASO")
    resp = client.post("/after_sale_out/add", json={
        "order_no": order_no, "date": str(date.today()),
        "customer": "批三客户", "warehouse": WAREHOUSE, "location": LOCATION,
        "items": [{"code": code, "quantity": quantity, "price": 1}],
    })
    body = resp.get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        return AfterSaleOutOrder.query.filter_by(order_no=order_no).one().id


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _seed()
    c = app_module.app.test_client()
    _login(c)
    yield c


# ---------------------------------------------------------------- 结构锁

def test_out_order_and_after_sale_have_no_raw_primitives():
    """两个路由文件不再裸调任何库存原语（P2-3 批 3 收敛结论）。"""
    for name, (src, _) in CONVERGED.items():
        for lineno, line in enumerate(src.splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            for prim in RAW_PRIMITIVES:
                assert prim not in line, (
                    f"{name} 第 {lineno} 行仍在裸调 {prim}，必须改道 apply_stock_delta")


def test_converged_routes_import_apply_stock_delta():
    """5 个库存写入路由函数都必须经唯一入口（顶级包 services 导入）。"""
    for name, (src, funcs) in CONVERGED.items():
        for func in funcs:
            start = src.index(f"def {func}(")
            nxt = src.find("    @app.route", start)
            body = src[start:nxt] if nxt != -1 else src[start:]
            assert "from services.warehouse_stock_service import apply_stock_delta" in body, (
                f"{name}::{func} 未按顶级包 services 导入 apply_stock_delta")


# ---------------------------------------------------------------- 行为锁

def test_complete_out_order_writes_three_ledgers(client):
    """出库完成（开库位管理）：①总账 -8、③流水 -8、②库位账 -8。"""
    with app_module.app.app_context():
        _stock_in(20)
        oid = _create_out_order(8)
    body = client.post(f"/out_order/{oid}/complete?force=1").get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 12, '①总账未扣减'
        assert _ledger_net(["in", "out"]) == 12, '③流水净额不符'
        assert _loc_qty() == 12, '②库位账未同步扣减（P2-3 要治的静默分裂）'


def test_revert_out_order_reverses_three_ledgers(client):
    """出库反提交：与完成严格对称，三账同时恢复。"""
    with app_module.app.app_context():
        _stock_in(20)
        oid = _create_out_order(8)
    assert client.post(f"/out_order/{oid}/complete?force=1").get_json()["status"] == "success"
    body = client.post(f"/out_order/{oid}/revert").get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 20, '①总账未恢复'
        assert _ledger_net(["in", "out", "revert_out"]) == 20, '③流水未对称恢复'
        assert _loc_qty() == 20, '②库位账未恢复（反提交漏回写库位是历史 BUG 模式）'


def test_batch_complete_out_order_three_ledgers(client):
    """批量完成两张出库单：批量路径同样三账一致（最易漏写库位账）。"""
    with app_module.app.app_context():
        _stock_in(20, "B3_MAT")
        _stock_in(20, "B3_MAT2")
        ids = [_create_out_order(6, "B3_MAT"), _create_out_order(9, "B3_MAT2")]
    body = client.post("/out_order/batch_complete", json={"ids": ids}).get_json()
    assert body["status"] == "success", body
    assert body.get("completed") == 2, body

    with app_module.app.app_context():
        db.session.refresh(_material())
        db.session.refresh(_material("B3_MAT2"))
        assert _material().stock == 14 and _material("B3_MAT2").stock == 11
        assert _loc_qty("B3_MAT") == 14, '批量完成漏写库位账'
        assert _loc_qty("B3_MAT2") == 11, '批量完成漏写库位账（第二张单）'


def test_after_sale_out_complete_and_revert_three_ledgers(client):
    """售后出库完成 + 反提交：三账同减同增、方向对称。"""
    with app_module.app.app_context():
        _stock_in(15)
    oid = _create_after_sale_order(client, 5)
    body = client.post(f"/after_sale_out/{oid}/complete").get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 10, '①总账未扣减'
        assert _loc_qty() == 10, '②库位账未同步扣减'

    body = client.post(f"/after_sale_out/{oid}/revert").get_json()
    assert body["status"] == "success", body

    with app_module.app.app_context():
        db.session.refresh(_material())
        assert _material().stock == 15, '①总账未恢复'
        assert _loc_qty() == 15, '②库位账未恢复'
        assert _ledger_net(["in", "after_sale_out", "revert_after_sale_out"]) == 15
