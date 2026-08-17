# -*- coding: utf-8 -*-
"""BUG-2026-08-17-00X 回归：关库位管理 + 单仓库时仓库级库存回退全局口径。

根因：get_warehouse_stock_quantities 关库位管理分支按 StockTransaction.location
聚合，历史 NULL-location 流水不入列，单仓库部署时仓库级库存可能为 0
（"有库存查不出来"）。修复：系统仅一个仓库时直接以全局 Material.stock 为准。

测试用例：
  T1. 单仓库 + 关库位管理：NULL-location 流水存在时，仓库聚合仍等于全局库存
  T2. 多仓库 + 关库位管理：仍按 location 聚合，不串仓（fallback 不误触发）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Material, MaterialCategory, StockTransaction, Unit, Warehouse,
    add_stock, get_warehouse_stock_quantities, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_units_categories():
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
    ])
    db.session.commit()


def _seed_material(code="M001", stock=0):
    mat = Material(code=code, name="轴承", spec="6204",
                   category_id=1, unit_id=1, stock=stock, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def test_single_warehouse_fallback():
    """T1：单仓库 + 关库位管理，NULL-location 流水不丢库存。"""
    with app_module.app.test_request_context():
        _reset_db()
        set_system_setting("location_management_enabled", "0")
        _seed_units_categories()
        wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
        db.session.add(wh)
        db.session.commit()
        mat = _seed_material(stock=10)
        # 模拟历史 NULL-location 流水（旧代码写入，无 location）
        db.session.add(StockTransaction(
            material_id=mat.id, transaction_type='in', quantity=10,
            location=None, reference_type='in_order', reference_id=1,
        ))
        db.session.commit()
        stock = get_warehouse_stock_quantities(wh)
        assert abs(stock.get(mat.id, 0) - 10) < 1e-9, f"单仓库 fallback 失效: {stock}"


def test_multi_warehouse_no_fallback():
    """T2：多仓库 + 关库位管理，fallback 不触发，仍按 location 聚合。"""
    with app_module.app.test_request_context():
        _reset_db()
        set_system_setting("location_management_enabled", "0")
        _seed_units_categories()
        wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
        wh_b = Warehouse(code="WHB", name="仓库B", status="active")
        db.session.add_all([wh_a, wh_b])
        db.session.commit()
        mat = _seed_material(stock=15)
        ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
        assert ok
        ok, _ = add_stock(mat, 5, 'in', 'in_order', 2, warehouse=wh_b)
        assert ok
        db.session.commit()
        stock_a = get_warehouse_stock_quantities(wh_a)
        stock_b = get_warehouse_stock_quantities(wh_b)
        assert abs(stock_a.get(mat.id, 0) - 10) < 1e-9, f"A 仓串仓: {stock_a}"
        assert abs(stock_b.get(mat.id, 0) - 5) < 1e-9, f"B 仓串仓: {stock_b}"
