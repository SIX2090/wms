# -*- coding: utf-8 -*-
"""BUG-2026-08-27-004 回归：多仓库下仓库月报/库存汇总与台账同口径处理空 location 流水。

根因：BUG-2026-08-27-003 修复台账空 location 流水按来源单据归属时，月报
（_build_warehouse_monthly_report）与库存汇总（get_warehouse_stock_quantities
多仓库+关库位分支）未同步——仍仅 location.in_(loc_names)，把空 location 历史
流水整体排除，导致同一批数据"台账有数、月报/库存查询无数"，两报表数字对不上。
这是同一口径逻辑被复制成多份、修复漏改一处导致反复出 BUG 的直接案例。

修复：提炼 _warehouse_scoped_txn_condition + _filter_txn_list_by_warehouse_scope
两个共用口径助手，台账/月报/库存汇总统一调用，改口径只改一处。

T1. 空 location 流水（来源入库单属仓库A）：月报仓库A 当月收入含它（修复前为 0）。
T2. 同上，月报仓库B 不含（不串仓）。
T3. location 非空（仓库名）流水仍正常计入月报（不回归）。
T4. 一致性：同批数据台账 in/out 合计 == 月报 in/out，台账期末余额 == 月报期末。
T5. get_warehouse_stock_quantities 多仓库+关库位：空 location 归属流水计入仓库库存。
T6. 调拨空 location 流水：月报调出归 from_warehouse、调入归 to_warehouse。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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
    db, InOrder, Material, MaterialCategory, StockTransaction, TransferOrder,
    Unit, Warehouse, set_system_setting, _collect_ledger_rows,
    _build_warehouse_monthly_report, get_warehouse_stock_quantities,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    set_system_setting("location_management_enabled", "0")  # 关库位管理
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT"),
        Warehouse(id=1, code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(id=2, code="WHB", name="仓库B", status="active"),
    ])
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


def _mk_in_order(warehouse_name, no="IN-1"):
    o = InOrder(order_no=no, date=date.today(), warehouse=warehouse_name,
                status='completed', business_type='采购入库')
    db.session.add(o)
    db.session.commit()
    return o


def _monthly_row(wh, mat):
    """取月报中当前月+指定物料的行（start/end 缺省=本月）。"""
    _, rows, _ = _build_warehouse_monthly_report(_filters(wh, mat))
    month_str = date.today().strftime('%Y-%m')
    hits = [r for r in rows if r['material_code'] == mat.code and r['month'] == month_str]
    assert len(hits) == 1, f"月报应恰有 1 行（当月 {month_str}），实际 {len(hits)}: {rows}"
    return hits[0]


class TestMonthlyReportSourceWarehouseAttribution:

    def test_monthly_includes_null_location_txn(self):
        """T1：空 location 流水来源入库单属仓库A，月报仓库A 当月收入含它。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                            location=None, reference_type='in_order', reference_id=order.id))
            db.session.commit()
            row = _monthly_row(wh_a, mat)
            assert abs(row['in_quantity'] - 100) < 1e-6, \
                f"月报当月收入应含空location归属流水 100，实际 {row['in_quantity']}"

    def test_monthly_excludes_other_warehouse(self):
        """T2：同上，月报仓库B 不含该流水（不串仓）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_b = Warehouse.query.get(2)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                            location=None, reference_type='in_order', reference_id=order.id))
            db.session.commit()
            row = _monthly_row(wh_b, mat)
            assert abs(row['in_quantity']) < 1e-6, \
                f"仓库B月报不应计入仓库A的空location流水，实际收入 {row['in_quantity']}"

    def test_monthly_named_location_no_regression(self):
        """T3：location 非空（仓库名）流水仍正常计入月报（不回归）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=10,
                                            location='仓库A', reference_type='in_order', reference_id=order.id))
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=5,
                                            location=None, reference_type='in_order', reference_id=order.id))
            db.session.commit()
            row = _monthly_row(wh_a, mat)
            assert abs(row['in_quantity'] - 15) < 1e-6, \
                f"仓库名流水10+空location流水5 应共15，实际 {row['in_quantity']}"

    def test_ledger_monthly_consistency(self):
        """T4：同批数据，台账 in/out 合计 == 月报 in/out，台账期末余额 == 月报期末。

        防复发核心断言：台账与月报口径今后任何一边被单独修改，本测试立刻红。
        """
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            order = _mk_in_order('仓库A')
            db.session.add_all([
                # 空 location 收入 100（来源入库单属仓库A，靠归属逻辑计入）
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                 location=None, reference_type='in_order', reference_id=order.id),
                # 仓库名发出 30
                StockTransaction(material_id=mat.id, transaction_type='out', quantity=-30,
                                 location='仓库A', reference_type='in_order', reference_id=order.id),
                # 仓库B 的流水（仓库A 不应计入）
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=50,
                                 location='仓库B', reference_type='in_order', reference_id=order.id),
            ])
            db.session.commit()
            ledger_rows = _collect_ledger_rows(_filters(wh_a, mat))
            ledger_in = sum(r['in_quantity'] for r in ledger_rows)
            ledger_out = sum(r['out_quantity'] for r in ledger_rows)
            ledger_balance = ledger_rows[-1]['balance_quantity'] if ledger_rows else 0.0
            row = _monthly_row(wh_a, mat)
            assert abs(ledger_in - 100) < 1e-6 and abs(ledger_out - 30) < 1e-6, \
                f"台账口径异常: in={ledger_in} out={ledger_out}"
            assert abs(row['in_quantity'] - ledger_in) < 1e-6, \
                f"月报收入 {row['in_quantity']} 与台账 {ledger_in} 不一致"
            assert abs(row['out_quantity'] - ledger_out) < 1e-6, \
                f"月报发出 {row['out_quantity']} 与台账 {ledger_out} 不一致"
            assert abs(row['ending_quantity'] - ledger_balance) < 1e-6, \
                f"月报期末 {row['ending_quantity']} 与台账余额 {ledger_balance} 不一致"

    def test_stock_quantities_include_attributed_txn(self):
        """T5：get_warehouse_stock_quantities 多仓库+关库位：空 location 归属流水计入。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            order = _mk_in_order('仓库A')
            db.session.add_all([
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                 location=None, reference_type='in_order', reference_id=order.id),
                StockTransaction(material_id=mat.id, transaction_type='out', quantity=-30,
                                 location='仓库A', reference_type='in_order', reference_id=order.id),
            ])
            db.session.commit()
            stock_map = get_warehouse_stock_quantities(wh_a)
            assert abs(stock_map.get(mat.id, 0.0) - 70) < 1e-6, \
                f"仓库A库存应为 100-30=70（含空location归属流水），实际 {stock_map.get(mat.id)}"

    def test_monthly_transfer_attribution_by_sign(self):
        """T6：调拨空 location 流水，月报调出归 from_warehouse、调入归 to_warehouse。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            wh_b = Warehouse.query.get(2)
            t = TransferOrder(transfer_no="TR-1", date=date.today(), from_warehouse='仓库A',
                              to_warehouse='仓库B', from_location='仓库A', to_location='仓库B',
                              status='completed')
            db.session.add(t)
            db.session.commit()
            db.session.add_all([
                StockTransaction(material_id=mat.id, transaction_type='transfer_out', quantity=-4,
                                 location=None, reference_type='transfer', reference_id=t.id),
                StockTransaction(material_id=mat.id, transaction_type='transfer_in', quantity=4,
                                 location=None, reference_type='transfer', reference_id=t.id),
            ])
            db.session.commit()
            row_a = _monthly_row(wh_a, mat)
            row_b = _monthly_row(wh_b, mat)
            assert abs(row_a['out_quantity'] - 4) < 1e-6 and abs(row_a['in_quantity']) < 1e-6, \
                f"调拨出应仅计仓库A发出4，实际 in={row_a['in_quantity']} out={row_a['out_quantity']}"
            assert abs(row_b['in_quantity'] - 4) < 1e-6 and abs(row_b['out_quantity']) < 1e-6, \
                f"调拨入应仅计仓库B收入4，实际 in={row_b['in_quantity']} out={row_b['out_quantity']}"
