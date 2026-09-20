# -*- coding: utf-8 -*-
"""P2-3 收敛：`app.services.warehouse_stock_service.apply_stock_delta` 单测。

服务层是库存三账（①总账+③流水+②库位账）写入唯一入口。本测试锁定：
1. 入库（delta>0）：总账+流水+库位账三账同写；
2. 出库（delta<0）：总账扣减+流水负值+库位账负 delta；
3. delta==0：不写任何账（与存量调用点 quantity==0 跳过口径一致）；
4. 关库位管理：不写库位账（向后兼容）；
5. 库位键缺省回退 warehouse（与 22 处既有双写定式逐字一致）；
6. 双仓隔离：B 仓库存不掩护 A 仓出库（A11/R2 语义，服务层不得破坏）；
7. 无库位记录出库：显式失败不静默（BUG-2026-08-04-002 语义）；
8. 流水参数（type/reference/remark/warehouse_id）原样透传。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    LocationInventory, Material, MaterialCategory, StockTransaction,
    Supplier, Unit, Warehouse, db, set_system_setting,
)
from app.services.warehouse_stock_service import apply_stock_delta  # noqa: E402

WAREHOUSE_A = "A仓"
WAREHOUSE_B = "B仓"


@pytest.fixture()
def ctx():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="供应商"),
            Warehouse(code="WHA", name=WAREHOUSE_A, is_default=True),
            Warehouse(code="WHB", name=WAREHOUSE_B, is_default=False),
        ])
        db.session.commit()
        db.session.add(Material(
            code="M-SVC", name="服务层料", spec="S",
            category_id=1, unit_id=1, supplier_id=1, stock=100, price=1,
        ))
        db.session.commit()
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
        # 原语内部读 current_user（流水 operator_id），无请求上下文时是 None 会
        # AttributeError；test_request_context 提供匿名用户（is_authenticated=False
        # → operator_id=None），与生产未登录写入的口径一致。
        with app_module.app.test_request_context():
            yield
        db.session.remove()


def _material():
    return Material.query.filter_by(code="M-SVC").one()


def _loc_qty(material_id, location, warehouse_name):
    wh = Warehouse.query.filter_by(name=warehouse_name).one()
    inv = LocationInventory.query.filter_by(
        material_id=material_id, location=location, warehouse_id=wh.id).first()
    return inv.quantity if inv else None


def _enable_location():
    set_system_setting("location_management_enabled", "1")
    db.session.commit()


def test_apply_stock_delta(ctx):
    """delta>0：总账 +10、流水 +10、库位 +10（开库位管理）。

    函数名即 A9 锚点（lint 按 test_<函数名> 精确匹配）。"""
    _enable_location()
    m = _material()
    ok, err = apply_stock_delta(
        m, 10, transaction_type="adjustment_in",
        reference_type="adjustment", reference_id=1,
        remark="测试入库", warehouse=WAREHOUSE_A, location="A-01")
    assert ok, err
    db.session.commit()
    db.session.refresh(m)
    assert m.stock == 110
    txn = StockTransaction.query.filter_by(material_id=m.id).one()
    assert txn.quantity == 10 and txn.transaction_type == "adjustment_in"
    assert txn.reference_type == "adjustment" and txn.reference_id == 1
    assert txn.remark == "测试入库"
    wh = Warehouse.query.filter_by(name=WAREHOUSE_A).one()
    assert txn.warehouse_id == wh.id
    assert _loc_qty(m.id, "A-01", WAREHOUSE_A) == 10


def test_outbound_writes_three_ledgers(ctx):
    """delta<0：总账 -30、流水 -30、库位 -30。"""
    _enable_location()
    m = _material()
    ok, err = apply_stock_delta(m, 50, transaction_type="in", warehouse=WAREHOUSE_A, location="A-01")
    assert ok, err
    ok, err = apply_stock_delta(
        m, -30, transaction_type="out",
        reference_type="out_order", reference_id=7,
        warehouse=WAREHOUSE_A, location="A-01")
    assert ok, err
    db.session.commit()
    db.session.refresh(m)
    assert m.stock == 120
    out_txn = StockTransaction.query.filter_by(
        material_id=m.id, transaction_type="out").one()
    assert out_txn.quantity == -30
    assert _loc_qty(m.id, "A-01", WAREHOUSE_A) == 20


def test_zero_delta_writes_nothing(ctx):
    """delta==0：总账、流水、库位账均不变。"""
    _enable_location()
    m = _material()
    ok, err = apply_stock_delta(m, 0, transaction_type="in", warehouse=WAREHOUSE_A)
    assert ok, err
    db.session.commit()
    db.session.refresh(m)
    assert m.stock == 100
    assert StockTransaction.query.filter_by(material_id=m.id).count() == 0
    assert LocationInventory.query.filter_by(material_id=m.id).count() == 0


def test_location_disabled_skips_location_ledger(ctx):
    """关库位管理：写总账+流水，不写库位账。"""
    m = _material()
    ok, err = apply_stock_delta(m, 5, transaction_type="in", warehouse=WAREHOUSE_A)
    assert ok, err
    db.session.commit()
    db.session.refresh(m)
    assert m.stock == 105
    assert LocationInventory.query.filter_by(material_id=m.id).count() == 0


def test_location_key_falls_back_to_warehouse(ctx):
    """location 缺省：库位键回退 warehouse 名（既有定式）。"""
    _enable_location()
    m = _material()
    ok, err = apply_stock_delta(m, 8, transaction_type="in", warehouse=WAREHOUSE_A)
    assert ok, err
    db.session.commit()
    assert _loc_qty(m.id, WAREHOUSE_A, WAREHOUSE_A) == 8


def test_dual_warehouse_isolation(ctx):
    """双仓隔离：物料总账 100 全在 A 仓时，B 仓出库必须失败且总账不动。"""
    m = _material()
    ok, err = apply_stock_delta(m, 100, transaction_type="in", warehouse=WAREHOUSE_A)
    assert ok, err
    db.session.commit()  # 入库先入账（避免后续 rollback 误退）
    ok, err = apply_stock_delta(m, -10, transaction_type="out", warehouse=WAREHOUSE_B)
    assert not ok
    assert WAREHOUSE_B in err
    db.session.rollback()
    db.session.refresh(m)
    assert m.stock == 200


def test_missing_location_record_fails_loudly(ctx):
    """无库位记录出库：显式失败（不静默成功），且总账回滚由调用方负责。"""
    _enable_location()
    m = _material()
    ok, err = apply_stock_delta(m, 10, transaction_type="in", warehouse=WAREHOUSE_A, location="A-01")
    assert ok, err
    ok, err = apply_stock_delta(m, -5, transaction_type="out", warehouse=WAREHOUSE_A, location="A-99")
    assert not ok
    assert "无库位库存记录" in err


def test_invalid_material_fails(ctx):
    """material 为 None：显式失败。"""
    ok, err = apply_stock_delta(None, 1, transaction_type="in", warehouse=WAREHOUSE_A)
    assert not ok
    assert "物料不存在" in err
