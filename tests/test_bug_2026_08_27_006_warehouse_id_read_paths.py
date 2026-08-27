# -*- coding: utf-8 -*-
"""C 断根（BUG-2026-08-27-005 后续）：读取路径切换 warehouse_id 精确过滤 + 四方对账。

背景：B 已给 stock_transaction 加 warehouse_id 外键并回填历史。C 把仓库级
报表的读取路径从 location 字符串推理切换为 warehouse_id 外键精确命中，
未回填行（warehouse_id IS NULL）退回 location 字符串兜底，保证口径在
"新数据/已回填历史/未回填历史"三类行上完全一致。

T1. 台账-新数据：warehouse_id=1 且空 location 流水，仓库A 可见、仓库B 不可见。
T2. 月报-新数据：同上，月报仓库A 计入、仓库B 不计。
T3. 库存汇总：get_warehouse_stock_quantities 按 warehouse_id 聚合空 location 流水。
T4. 未回填兜底：warehouse_id IS NULL + location=仓库名 的行仍被三处计入（不回归）。
T5. 四方对账（防复发杀手锏，开库位管理）：同批混合数据（新数据+已回填+未回填+
    空location归属），台账期末 == 月报期末 == 库存查询 == LocationInventory 实际库存，
    且台账 in/out == 月报 in/out。
T6. _material_stock_unattributed：warehouse_id 非空即视为可归属（替代 location 判断）。
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
    db, InOrder, LocationInventory, Material, MaterialCategory, StockTransaction,
    Unit, Warehouse, _collect_ledger_rows, _build_warehouse_monthly_report,
    _material_stock_unattributed, get_warehouse_stock_quantities,
    set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(location_mgmt=False):
    set_system_setting("location_management_enabled", "1" if location_mgmt else "0")
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


def _ledger_totals(wh, mat):
    rows = _collect_ledger_rows(_filters(wh, mat))
    return {
        'in': sum(r['in_quantity'] for r in rows),
        'out': sum(r['out_quantity'] for r in rows),
        'balance': rows[-1]['balance_quantity'] if rows else 0.0,
    }


def _monthly_row(wh, mat):
    _, rows, _ = _build_warehouse_monthly_report(_filters(wh, mat))
    month_str = date.today().strftime('%Y-%m')
    hits = [r for r in rows if r['material_code'] == mat.code and r['month'] == month_str]
    assert len(hits) == 1, f"月报应恰有 1 行（当月 {month_str}），实际 {len(hits)}"
    return hits[0]


class TestWarehouseIdReadPaths:

    def test_ledger_new_data_warehouse_id_exact(self):
        """T1：warehouse_id=1 且空 location 流水，仓库A 台账可见、仓库B 不可见。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a, wh_b = Warehouse.query.get(1), Warehouse.query.get(2)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=80,
                                            location=None, warehouse_id=1,
                                            reference_type='in_order', reference_id=order.id))
            db.session.commit()
            ta = _ledger_totals(wh_a, mat)
            tb = _ledger_totals(wh_b, mat)
            assert abs(ta['in'] - 80) < 1e-6, f"仓库A台账应计 80，实际 {ta['in']}"
            assert abs(tb['in']) < 1e-6, f"仓库B台账不应计，实际 {tb['in']}"

    def test_monthly_new_data_warehouse_id_exact(self):
        """T2：warehouse_id=1 且空 location 流水，月报仓库A 计入、仓库B 不计。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a, wh_b = Warehouse.query.get(1), Warehouse.query.get(2)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=60,
                                            location=None, warehouse_id=1,
                                            reference_type='in_order', reference_id=order.id))
            db.session.commit()
            ra = _monthly_row(wh_a, mat)
            rb = _monthly_row(wh_b, mat)
            assert abs(ra['in_quantity'] - 60) < 1e-6, f"月报仓库A应计 60，实际 {ra['in_quantity']}"
            assert abs(rb['in_quantity']) < 1e-6, f"月报仓库B不应计，实际 {rb['in_quantity']}"

    def test_stock_quantities_warehouse_id_aggregation(self):
        """T3：库存汇总按 warehouse_id 聚合空 location 流水。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a, wh_b = Warehouse.query.get(1), Warehouse.query.get(2)
            db.session.add_all([
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                 location=None, warehouse_id=1, reference_type='x', reference_id=1),
                StockTransaction(material_id=mat.id, transaction_type='out', quantity=-30,
                                 location=None, warehouse_id=1, reference_type='x', reference_id=2),
            ])
            db.session.commit()
            sa = get_warehouse_stock_quantities(wh_a)
            sb = get_warehouse_stock_quantities(wh_b)
            assert abs(sa.get(mat.id, 0.0) - 70) < 1e-6, \
                f"仓库A库存应 100-30=70（warehouse_id 精确聚合），实际 {sa.get(mat.id)}"
            assert abs(sb.get(mat.id, 0.0)) < 1e-6, f"仓库B库存不应有数，实际 {sb.get(mat.id)}"

    def test_unbackfilled_location_fallback(self):
        """T4：warehouse_id IS NULL + location=仓库名 的行，三处仍计入（兜底不回归）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            wh_a = Warehouse.query.get(1)
            order = _mk_in_order('仓库A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=50,
                                            location='仓库A', warehouse_id=None,
                                            reference_type='in_order', reference_id=order.id))
            db.session.commit()
            ta = _ledger_totals(wh_a, mat)
            ra = _monthly_row(wh_a, mat)
            sa = get_warehouse_stock_quantities(wh_a)
            assert abs(ta['in'] - 50) < 1e-6, f"台账兜底应计 50，实际 {ta['in']}"
            assert abs(ra['in_quantity'] - 50) < 1e-6, f"月报兜底应计 50，实际 {ra['in_quantity']}"
            assert abs(sa.get(mat.id, 0.0) - 50) < 1e-6, \
                f"库存汇总兜底应计 50，实际 {sa.get(mat.id)}"


class TestFourWayReconciliation:

    def test_ledger_monthly_stock_inventory_consistency(self):
        """T5：四方对账（开库位管理）——台账期末 == 月报期末 == 库存查询 == 实际库存。

        同批混合数据：
        - 新数据：warehouse_id=1 空 location 收入 100（写端已落外键）
        - 已回填历史：warehouse_id=1 + location='仓库A' 发出 30
        - 未回填历史：warehouse_id IS NULL + location='仓库A' 收入 20（字符串兜底）
        - 空 location 未回填：warehouse_id IS NULL + location=None + 来源入库单仓库A 收入 10
        - 仓库B 干扰项：warehouse_id=2 收入 99（仓库A 四路都不应计）
        实际库存基准：LocationInventory(warehouse_id=1) 汇总 = 100-30+20+10 = 100。
        """
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed(location_mgmt=True)
            wh_a, wh_b = Warehouse.query.get(1), Warehouse.query.get(2)
            order_a = _mk_in_order('仓库A', no='IN-A')
            db.session.add_all([
                # 新数据（写端已落 warehouse_id）
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=100,
                                 location=None, warehouse_id=1,
                                 reference_type='in_order', reference_id=order_a.id),
                # 已回填历史
                StockTransaction(material_id=mat.id, transaction_type='out', quantity=-30,
                                 location='仓库A', warehouse_id=1,
                                 reference_type='in_order', reference_id=order_a.id),
                # 未回填历史（location 兜底）
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=20,
                                 location='仓库A', warehouse_id=None,
                                 reference_type='in_order', reference_id=order_a.id),
                # 空 location 未回填（来源单据归属）
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=10,
                                 location=None, warehouse_id=None,
                                 reference_type='in_order', reference_id=order_a.id),
                # 仓库B 干扰项
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=99,
                                 location='仓库B', warehouse_id=2,
                                 reference_type='in_order', reference_id=order_a.id),
            ])
            # 实际库存基准：仓库A 库位账
            db.session.add(LocationInventory(material_id=mat.id, warehouse_id=1,
                                             location='仓库A', quantity=100))
            db.session.commit()

            # 四路取数
            ledger = _ledger_totals(wh_a, mat)
            monthly = _monthly_row(wh_a, mat)
            stock_q = get_warehouse_stock_quantities(wh_a)
            inventory = db.session.query(
                db.func.coalesce(db.func.sum(LocationInventory.quantity), 0)
            ).filter(
                LocationInventory.material_id == mat.id,
                LocationInventory.warehouse_id == 1,
            ).scalar()
            # 仓库B 也应一致为 0（无库位账行）
            stock_b = get_warehouse_stock_quantities(wh_b)

            # 四方对账：台账 in/out 与月报 in/out 一致
            assert abs(ledger['in'] - 130) < 1e-6, f"台账收入应 100+20+10=130，实际 {ledger['in']}"
            assert abs(ledger['out'] - 30) < 1e-6, f"台账发出应 30，实际 {ledger['out']}"
            assert abs(monthly['in_quantity'] - ledger['in']) < 1e-6 and \
                abs(monthly['out_quantity'] - ledger['out']) < 1e-6, \
                f"月报与台账不一致: 月报 in={monthly['in_quantity']} out={monthly['out_quantity']}，" \
                f"台账 in={ledger['in']} out={ledger['out']}"
            # 四方对账：期末一致
            assert abs(monthly['ending_quantity'] - ledger['balance']) < 1e-6, \
                f"月报期末 {monthly['ending_quantity']} 与台账 {ledger['balance']} 不一致"
            assert abs(stock_q.get(mat.id, 0.0) - ledger['balance']) < 1e-6, \
                f"库存查询 {stock_q.get(mat.id)} 与台账期末 {ledger['balance']} 不一致"
            assert abs(float(inventory) - ledger['balance']) < 1e-6, \
                f"实际库存(库位账) {inventory} 与台账期末 {ledger['balance']} 不一致"
            # 仓库B 隔离
            assert abs(stock_b.get(mat.id, 0.0)) < 1e-6, \
                f"仓库B 不应有库存，实际 {stock_b.get(mat.id)}"


class TestMaterialStockUnattributed:

    def test_warehouse_id_counts_as_attributed(self):
        """T6：warehouse_id 非空（即使空 location）即视为可归属。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=5,
                                            location=None, warehouse_id=1,
                                            reference_type='x', reference_id=1))
            db.session.commit()
            assert _material_stock_unattributed(mat.id) is False, \
                "warehouse_id=1 的空 location 流水应视为已归属"

    def test_all_null_keeps_unattributed(self):
        """T6b：全部 warehouse_id 为 NULL 仍视为不可归属（兜底逻辑保留）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=5,
                                            location=None, warehouse_id=None,
                                            reference_type='x', reference_id=1))
            db.session.commit()
            assert _material_stock_unattributed(mat.id) is True, \
                "全 NULL 仍应视为不可归属"
