# -*- coding: utf-8 -*-
"""BUG-2026-08-16-006 回归：add_stock/deduct_stock_atomic 写流水必须带仓库 location。

根因：add_stock / deduct_stock_atomic 写 StockTransaction 时不填 location
（仅 transfer 写），而 get_warehouse_stock_quantities 关库位管理模式按
`location IN (仓库名/编码)` 聚合流水——NULL 不入列，多仓库+关库位管理时
仓库级库存恒为 0（库存查询/出库校验全部失真）。

修复：两个函数新增 warehouse 参数，写流水时把仓库名/编码写入
StockTransaction.location；单据完成/反提交/调整/委外/领料/售后/盘点等
全部库存变动入口传入 warehouse。

测试用例：
  T1. 关库位管理：A 仓入库 10、B 仓入库 5，仓库级聚合各自正确不串仓
  T2. 关库位管理：A 仓出库 3 后，A 仓聚合为 7、B 仓仍为 5
  T3. 关库位管理：流水 location 已写入仓库名（可直接按 location 聚合）
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
    add_stock, deduct_stock, deduct_stock_atomic,
    get_warehouse_stock_quantities, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    # 关闭库位管理
    set_system_setting("location_management_enabled", "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204",
                   category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def test_add_stock():
    """A9 门禁：add_stock 写流水带仓库 location（见 T1/T3）。"""
    with app_module.app.test_request_context():
        _reset_db()
        mat = _seed()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        ok, _ = add_stock(mat, 1, 'in', 'in_order', 9, warehouse=wh_a)
        assert ok


def test_deduct_stock_atomic():
    """A9 门禁：deduct_stock_atomic 写流水带仓库 location（见 T1/T2）。"""
    with app_module.app.test_request_context():
        _reset_db()
        mat = _seed()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        add_stock(mat, 5, 'in', 'in_order', 9, warehouse=wh_a)
        db.session.commit()
        ok, err, _ = deduct_stock_atomic(mat.id, 1, 'out', 'out_order', 9,
                                         warehouse=wh_a)
        assert ok, err


def test_deduct_stock():
    """A9 门禁：deduct_stock 包装函数转发 warehouse（见 complete_requisition）。"""
    with app_module.app.test_request_context():
        _reset_db()
        mat = _seed()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        add_stock(mat, 5, 'in', 'in_order', 9, warehouse=wh_a)
        db.session.commit()
        ok, err = deduct_stock(mat, 1, 'requisition', 'requisition', 9,
                               warehouse=wh_a)
        assert ok, err


class TestStockTransactionWarehouseLocation:

    def test_a_b_warehouse_inventory_not_mixed(self):
        """T1+T2：关库位管理，A/B 双仓入库/出库后仓库级聚合各自正确。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            wh_b = Warehouse.query.filter_by(code="WHB").first()

            # A 仓入库 10，B 仓入库 5
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
            assert ok
            ok, _ = add_stock(mat, 5, 'in', 'in_order', 2, warehouse=wh_b)
            assert ok
            db.session.commit()

            qty_a = get_warehouse_stock_quantities(wh_a)
            qty_b = get_warehouse_stock_quantities(wh_b)
            assert abs(qty_a.get(mat.id, 0) - 10) < 1e-6, qty_a
            assert abs(qty_b.get(mat.id, 0) - 5) < 1e-6, qty_b

            # A 仓出库 3，B 仓不受影响
            ok, err, _ = deduct_stock_atomic(
                mat.id, 3, 'out', 'out_order', 3, warehouse=wh_a)
            assert ok, err
            db.session.commit()

            qty_a = get_warehouse_stock_quantities(wh_a)
            qty_b = get_warehouse_stock_quantities(wh_b)
            assert abs(qty_a.get(mat.id, 0) - 7) < 1e-6, qty_a
            assert abs(qty_b.get(mat.id, 0) - 5) < 1e-6, qty_b

    def test_transaction_location_written(self):
        """T3：流水 location 已写入仓库名，可被关库位管理聚合命中。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
            assert ok
            db.session.commit()
            rows = StockTransaction.query.filter_by(
                material_id=mat.id).all()
            assert len(rows) == 1
            assert (rows[0].location or '').strip() == "仓库A", rows[0].location