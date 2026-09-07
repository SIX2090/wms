# -*- coding: utf-8 -*-
"""BUG-2026-09-07-006 回归：库存台账新增期初结存行与本期合计行。

背景：台账此前只有流水行。按日期范围查询时，期初余额虽被计入结存
（start_date 前流水跳过但累计），但「期初是多少、本期入/出合计多少、
期末多少」不可见，对账只能手工加减。

修复：start_date 前累计为「期初结存」行（排同物料最前）；末尾加「本期
合计」行（期初 + 本期入 − 本期出 = 期末结存，排同物料最后）。

断言：
  T1. 带日期范围查询：首行为期初结存（150），末行为本期合计（期初 150、
      入 10、出 30、期末 130），流水行结存连续。
  T2. 无 start_date：无期初行，合计行期初为 0。
  T3. summary 期末结存口径不回归（amount=130）。
  T4. 多物料时标记行按物料分行且位置正确（各自组内最前/最后）。
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import Material, StockTransaction, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True


def _filters(**overrides):
    base = {
        'start_date': None, 'end_date': None,
        'warehouse_id': 0, 'warehouse': '', 'warehouse_code': '',
        'business_type': '', 'material_code': '',
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc',
        'page': 1, 'page_size': 20, 'hide_zero': False, 'export': '',
    }
    base.update(overrides)
    return base


def _txn(material_id, ttype, qty, day, warehouse_id):
    return StockTransaction(
        material_id=material_id, transaction_type=ttype, quantity=qty,
        location='主仓', warehouse_id=warehouse_id,
        reference_type='in_order' if qty >= 0 else 'out_order', reference_id=1,
        created_at=datetime(2026, day[0], day[1], 10, 0, 0))


class TestBug20260907006:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            wh = Warehouse(code="WHM", name="主仓", is_default=True, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([wh, unit, user])
            db.session.flush()
            m1 = Material(code="M001", name="电缆", unit_id=unit.id, price=10.0, stock=130.0)
            m2 = Material(code="M002", name="开关", unit_id=unit.id, price=5.0, stock=7.0)
            db.session.add_all([m1, m2])
            db.session.flush()
            self.wh_id, self.m1, self.m2 = wh.id, m1.id, m2.id
            # M001：8月期初建账100 + 入库50；9月入库10、出库30 → 期末130
            db.session.add_all([
                _txn(m1.id, 'opening', 100, (8, 1), wh.id),
                _txn(m1.id, 'in', 50, (8, 5), wh.id),
                _txn(m1.id, 'in', 10, (9, 1), wh.id),
                _txn(m1.id, 'out', -30, (9, 3), wh.id),
                # M002：9月入库 7
                _txn(m2.id, 'in', 7, (9, 2), wh.id),
            ])
            db.session.commit()

    def _ledger(self, **kw):
        cols, rows, summary = app_module._build_ledger_report(_filters(
            warehouse_id=self.wh_id, warehouse='主仓', warehouse_code='WHM', **kw))
        return rows, summary

    def test_T1_opening_and_closing_rows_with_range(self):
        """9月范围：期初 150 → 流水 2 行（结存 160/130）→ 合计（150+10-30=130）。"""
        with app_module.app.app_context():
            rows, summary = self._ledger(
                material_code='M001',
                start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
            assert len(rows) == 4, f"期初+2流水+合计应 4 行，实际 {len(rows)}"
            first, last = rows[0], rows[-1]
            assert first['reference_type'] == '期初结存'
            assert first['opening_quantity'] == 150 and first['balance_quantity'] == 150
            assert first['date'] == '2026-09-01'
            assert rows[1]['balance_quantity'] == 160, "首笔流水结存 = 期初150+10"
            assert rows[2]['balance_quantity'] == 130
            assert last['reference_type'] == '本期合计'
            assert last['opening_quantity'] == 150
            assert last['in_quantity'] == 10
            assert last['out_quantity'] == 30
            assert last['balance_quantity'] == 130
            assert '期初 + 本期入库 − 本期出库 = 期末结存' in last['remark']

    def test_T2_no_start_date_no_opening_row(self):
        """无 start_date：无期初行，合计行期初为 0。"""
        with app_module.app.app_context():
            rows, _ = self._ledger(material_code='M001')
            assert all(r['reference_type'] != '期初结存' for r in rows)
            last = rows[-1]
            assert last['reference_type'] == '本期合计'
            assert last['opening_quantity'] == 0
            assert last['in_quantity'] == 160
            assert last['out_quantity'] == 30
            assert last['balance_quantity'] == 130

    def test_T3_summary_ending_balance_unchanged(self):
        """summary.amount 期末结存口径不回归（130）。"""
        with app_module.app.app_context():
            _, summary = self._ledger(
                material_code='M001',
                start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
            assert summary['amount'] == 130, f"期末结存应 130，实际 {summary['amount']}"

    def test_T4_multi_material_marker_rows_grouped(self):
        """多物料：M001/M002 各有期初行与合计行，且位置在各自组内最前/最后。"""
        with app_module.app.app_context():
            rows, _ = self._ledger(
                material_code='M00',  # 模糊命中 M001 与 M002
                start_date=date(2026, 9, 1), end_date=date(2026, 9, 30))
            m1_rows = [r for r in rows if r['material_id'] == self.m1]
            m2_rows = [r for r in rows if r['material_id'] == self.m2]
            assert m1_rows and m2_rows, "两个物料都应有行"
            assert m1_rows[0]['reference_type'] == '期初结存'
            assert m1_rows[-1]['reference_type'] == '本期合计'
            assert m1_rows[-1]['balance_quantity'] == 130
            assert m2_rows[0]['reference_type'] == '期初结存'
            assert m2_rows[0]['opening_quantity'] == 0, "M002 期初前无流水，期初 0"
            assert m2_rows[-1]['reference_type'] == '本期合计'
            assert m2_rows[-1]['in_quantity'] == 7
            assert m2_rows[-1]['balance_quantity'] == 7
