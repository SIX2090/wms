# -*- coding: utf-8 -*-
"""BUG-2026-08-27-002 回归：单仓库下库存台账必须显示历史 NULL-location 流水。

根因：库存台账按 StockTransaction.location 匹配仓库名/编码过滤流水。2026-08-16 之前
add_stock/deduct_stock_atomic 不写仓库名，历史流水 location 为 NULL；而台账过滤是后来
（报表仓库必填）才加的，升级后这些老流水被排除——用户"以前能查、现在查不到"，且出现
"库存查询有数（单仓库 get_warehouse_stock_quantities 有全局兜底）、库存台账却查不到"的
口径不一致。

修复：单仓库时（Warehouse 总数==1）所有流水必属该仓库，不按 location 过滤，与
get_warehouse_stock_quantities 单仓库口径一致；多仓库仍按 location 精确过滤。

T1. 单仓库 + NULL-location 历史流水：台账可见（修复点）。
T2. 单仓库 + 仓库名/编号流水：仍可见（不回归）。
T3. 多仓库 + NULL-location 流水：仍不可见（无法归属，保持严格，防串仓）。
T4. 仓库月报（同根因）单仓库 NULL-location 流水：计入。
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
    set_system_setting, _collect_ledger_rows, _build_warehouse_monthly_report,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base(n_warehouses):
    set_system_setting("location_management_enabled", "0")
    db.session.add_all([Unit(name="个", code="PCS"), MaterialCategory(name="默认分类", code="CAT")])
    db.session.add(Warehouse(id=1, code="WHA", name="仓库A", is_default=True, status="active"))
    if n_warehouses >= 2:
        db.session.add(Warehouse(id=2, code="WHB", name="仓库B", status="active"))
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204", category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
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


def _add_txn(mat, qty, location, ref_id):
    db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=qty,
                                    location=location, reference_type='in_order', reference_id=ref_id))
    db.session.commit()


class TestLedgerSingleWarehouseNullLocation:

    def test_single_warehouse_null_location_visible(self):
        """T1：单仓库 + NULL-location 历史流水，台账可见（修复点）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed_base(n_warehouses=1)
            wh = Warehouse.query.get(1)
            _add_txn(mat, 100, None, 1)  # 历史流水，location 为空
            rows = _collect_ledger_rows(_filters(wh, mat))
            assert len(rows) == 1, f"单仓库 NULL-location 流水应可见，实际 {len(rows)} 行"
            assert abs(rows[0]['in_quantity'] - 100) < 1e-6

    def test_single_warehouse_named_location_still_visible(self):
        """T2：单仓库 + 仓库名/编号流水，仍可见（不回归）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed_base(n_warehouses=1)
            wh = Warehouse.query.get(1)
            _add_txn(mat, 10, '仓库A', 1)
            _add_txn(mat, 5, 'WHA', 2)
            _add_txn(mat, 3, None, 3)
            rows = _collect_ledger_rows(_filters(wh, mat))
            assert len(rows) == 3, f"单仓库应显示全部 3 行，实际 {len(rows)}"
            assert abs(sum(r['in_quantity'] for r in rows) - 18) < 1e-6

    def test_multi_warehouse_null_location_still_hidden(self):
        """T3：多仓库 + NULL-location 流水，仍不可见（无法归属，防串仓）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed_base(n_warehouses=2)
            wh_a = Warehouse.query.get(1)
            _add_txn(mat, 100, None, 1)      # NULL-location，无法归属 -> 应隐藏
            _add_txn(mat, 10, '仓库A', 2)     # 明确属仓库A -> 可见
            rows = _collect_ledger_rows(_filters(wh_a, mat))
            assert len(rows) == 1, f"多仓库 NULL-location 流水应仍隐藏，实际 {len(rows)} 行"
            assert abs(rows[0]['in_quantity'] - 10) < 1e-6

    def test_monthly_report_single_warehouse_null_location(self):
        """T4：仓库月报（同根因）单仓库 NULL-location 流水计入。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed_base(n_warehouses=1)
            wh = Warehouse.query.get(1)
            _add_txn(mat, 100, None, 1)
            cols, rows, summary = _build_warehouse_monthly_report(_filters(wh, mat))
            assert len(rows) == 1, f"月报应有1物料行，实际 {len(rows)}"
            assert rows[0]['transaction_count'] == 1, f"月报流水数应为1，实际 {rows[0]['transaction_count']}"
            assert abs(rows[0]['in_quantity'] - 100) < 1e-6
