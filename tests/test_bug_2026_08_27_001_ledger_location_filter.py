# -*- coding: utf-8 -*-
"""BUG-2026-08-27-001 回归：库存台账按仓库过滤必须纳入该仓库名下的库位流水。

根因：StockTransaction.location 字段同时承载「仓库名/编码」（in_order/out_order/
期初等走 add_stock/deduct_stock_atomic 写入）与「库位」（transfer/subcontract/mobile
走 add_stock_transaction 直接写入）。库存台账是唯一依赖该字段按仓库过滤的报表，
旧逻辑只匹配仓库名/编码，导致开启库位管理时调拨/委外等库位型流水按仓库查不到，
用户看到「库存台账查不到东西」。

修复：_warehouse_location_filter_values 把仓库名、仓库编码、以及该仓库名下所有库位名
一并纳入 location 过滤；台账与仓库月报共用此逻辑。

T1. 库位管理开启：A 仓入库（location=仓库名）+ 调拨出（location=A 仓库位）在 A 仓台账可见；
    B 仓调拨入（location=B 仓库位）在 B 仓台账可见，不串仓。
T2. 库位管理关闭：无 LocationInventory 行，仅按仓库名/编码匹配，行为不变。
T3. 仓库月报（同根因）同样能按仓库聚合库位型流水。
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
    db, LocationInventory, Material, MaterialCategory, StockTransaction, Unit,
    Warehouse, add_stock, add_stock_transaction, set_system_setting,
    _collect_ledger_rows, _build_warehouse_monthly_report,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(loc_on):
    set_system_setting("location_management_enabled", "1" if loc_on else "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(id=1, code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(id=2, code="WHB", name="仓库B", status="active"),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204",
                   category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    # 库位账：A-01 归属仓库A，B-01 归属仓库B（开启库位管理时存在）
    if loc_on:
        db.session.add_all([
            LocationInventory(material_id=mat.id, location="A-01", warehouse_id=1, quantity=0),
            LocationInventory(material_id=mat.id, location="B-01", warehouse_id=2, quantity=0),
        ])
        db.session.commit()
    return mat


def _filters(wh, mat):
    return {
        'start_date': None, 'end_date': None,
        'warehouse_id': wh.id, 'warehouse': wh.name, 'warehouse_code': wh.code or '',
        'business_type': '', 'material_code': mat.code,
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc', 'page': 1, 'page_size': 20,
        'hide_zero': False, 'export': '',
    }


def _seed_transactions(mat, wh_a, wh_b):
    # 1) 采购入库：add_stock 写 location=仓库名（入库单完成标准做法）
    add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
    # 2) 调拨出：add_stock_transaction 把「库位」写进 location（当前实现）
    add_stock_transaction(mat, -4, 'transfer_out', reference_type='transfer',
                         reference_id=1, location='A-01', remark='调拨出')
    # 3) 调拨入：库位 B-01
    add_stock_transaction(mat, 4, 'transfer_in', reference_type='transfer',
                         reference_id=1, location='B-01', remark='调拨入')
    db.session.commit()


class TestLedgerLocationFilter:

    def test_location_on_transfer_visible_per_warehouse(self):
        """T1：开启库位管理时，调拨等库位型流水按所属仓库正确聚合。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(loc_on=True)
            wh_a = Warehouse.query.get(1)
            wh_b = Warehouse.query.get(2)
            _seed_transactions(mat, wh_a, wh_b)

            rows_a = _collect_ledger_rows(_filters(wh_a, mat))
            rows_b = _collect_ledger_rows(_filters(wh_b, mat))

            # A 仓：入库 + 调拨出 = 2 行；B 仓：调拨入 = 1 行
            assert len(rows_a) == 2, f"仓库A 应有2行，实际 {len(rows_a)}: {[(r['reference_type'], r['location']) for r in rows_a]}"
            assert len(rows_b) == 1, f"仓库B 应有1行，实际 {len(rows_b)}: {[(r['reference_type'], r['location']) for r in rows_b]}"
            # 不串仓：B 仓不应出现 A-01 的调拨出
            assert all(r['location'] in ('仓库B', 'WHB', 'B-01') for r in rows_b)

    def test_location_off_unchanged(self):
        """T2：关闭库位管理时，无 LocationInventory，仅按仓库名/编码匹配，行为不变。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(loc_on=False)
            wh_a = Warehouse.query.get(1)
            wh_b = Warehouse.query.get(2)
            # 关闭库位管理时 from_location 回退为仓库名，故调拨流水 location=仓库名
            add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
            add_stock_transaction(mat, -4, 'transfer_out', reference_type='transfer',
                                 reference_id=1, location='仓库A', remark='调拨出')
            add_stock_transaction(mat, 4, 'transfer_in', reference_type='transfer',
                                 reference_id=1, location='仓库B', remark='调拨入')
            db.session.commit()
            rows_a = _collect_ledger_rows(_filters(wh_a, mat))
            rows_b = _collect_ledger_rows(_filters(wh_b, mat))
            assert len(rows_a) == 2, f"仓库A 应有2行，实际 {len(rows_a)}"
            assert len(rows_b) == 1, f"仓库B 应有1行，实际 {len(rows_b)}"

    def test_monthly_report_includes_location_rows(self):
        """T3：仓库月报（同根因）同样按仓库聚合库位型流水。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(loc_on=True)
            wh_a = Warehouse.query.get(1)
            wh_b = Warehouse.query.get(2)
            _seed_transactions(mat, wh_a, wh_b)
            cols_a, rows_a, _ = _build_warehouse_monthly_report(_filters(wh_a, mat))
            # 月报按物料汇总，M001 一行含 2 笔流水（入库 + 调拨出）
            assert len(rows_a) == 1, f"仓库A 月报应有1物料行，实际 {len(rows_a)}"
            assert rows_a[0]['transaction_count'] == 2, f"流水数应为2，实际 {rows_a[0]['transaction_count']}"
            assert abs(rows_a[0]['in_quantity'] - 10) < 1e-6
