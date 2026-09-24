# -*- coding: utf-8 -*-
"""BUG-2026-09-24-001 回归：库存台账「日期」列与日期口径改用**单据日期**。

现象：台账明细的「日期」列显示的是流水创建时间（StockTransaction.created_at），
不是单据日期。补录 / 批量导入 / 历史迁移时二者不一致——例如 8 月的单 9 月才录入，
台账把历史单据错排到录入当天，按日期对账对不上。

修复口径（本测试逐条锁死）：
1. 业务日期 = **单据日期优先、无来源单据退回 created_at 日期**。
2. 三个消费点统一改用业务日期（原都用 created_at）：
   a. 显示列「日期」；
   b. start_date 期初分界（开始日期前的单据累计为期初结存）；
   c. end_date 过滤——从 SQL 层移到 Python 侧（来源单据是多态的，SQL 无法跨表 join），
      只保留「单据日期 ≤ end_date」的流水。
3. 结存是运行期逐笔累加值 → **累加顺序也必须按业务日期**，否则「单据日期早但流水
   时间晚」的补录单会累加错位、结存列与日期列自相矛盾。

T1 单据日期 ≠ 流水时间 → 明细「日期」显示单据日期。
T2 无来源单据流水 → 退回 created_at 日期。
T3 单据日期 ≤ end_date 但流水时间 > end_date → 仍纳入（原 SQL 过滤会误剔除）。
T4 单据日期 > end_date 但流水时间 ≤ end_date → 排除（原 SQL 过滤会误纳入）。
T5 start_date 期初分界按单据日期（单据日期早于 start_date 计期初，不显示明细行）。
T6 结存累加顺序按单据日期（补录单在前正常单在后，结存列正确）。
T7 期初/合计标记行日期逻辑不变（期初=start_date、合计=end_date）。
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
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
    db, InOrder, InOrderItem, Material, MaterialCategory, StockTransaction,
    Unit, Warehouse, set_system_setting, _collect_ledger_rows,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    set_system_setting("location_management_enabled", "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT"),
        Warehouse(id=1, code="WHA", name="仓库A", is_default=True, status="active"),
    ])
    db.session.commit()
    m = Material(code="M001", name="轴承", spec="6204", category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(m)
    db.session.commit()
    return m


def _filters(mat, start=None, end=None):
    return {
        'start_date': start, 'end_date': end,
        'warehouse_id': 1, 'warehouse': '仓库A', 'warehouse_code': 'WHA',
        'business_type': '', 'material_code': mat.code,
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc', 'page': 1, 'page_size': 20,
        'hide_zero': False, 'export': '',
    }


def _mk_in_order(order_no, doc_date):
    o = InOrder(order_no=order_no, date=doc_date, warehouse="仓库A",
                location="", status='completed', business_type='采购入库')
    db.session.add(o)
    db.session.commit()
    db.session.add(InOrderItem(in_order_id=o.id, material_id=1,
                               quantity=10, price=10, amount=100))
    db.session.commit()
    return o


def _mk_txn(order, qty, txn_dt):
    t = StockTransaction(material_id=1, transaction_type='in' if qty > 0 else 'out',
                         quantity=qty, location="仓库A", warehouse_id=1,
                         reference_type='in_order', reference_id=order.id,
                         created_at=txn_dt)
    db.session.add(t)
    db.session.commit()
    return t


def _flow_rows(filters):
    return [r for r in _collect_ledger_rows(filters)
            if r.get('reference_type') not in ('期初结存', '本期合计')]


class TestLedgerDocumentDate:

    def test_t1_shows_document_date_not_created_at(self):
        """T1 明细「日期」显示单据日期（单据 8/1、流水 9/5 → 显示 8/1）。"""
        with app_module.app.test_request_context():
            _reset_db()
            m = _seed()
            o = _mk_in_order("IN-T1", date(2026, 8, 1))
            _mk_txn(o, 10, datetime(2026, 9, 5, 10, 0))
            rows = _flow_rows(_filters(m))
            assert len(rows) == 1
            assert rows[0]['date'] == "2026-08-01", rows[0]['date']

    def test_t2_fallback_to_created_at_when_no_doc(self):
        """T2 无来源单据流水退回 created_at 日期。"""
        with app_module.app.test_request_context():
            _reset_db()
            m = _seed()
            t = StockTransaction(material_id=1, transaction_type='in', quantity=5,
                                 location="仓库A", warehouse_id=1,
                                 reference_type=None, reference_id=None,
                                 created_at=datetime(2026, 9, 3, 8, 0))
            db.session.add(t)
            db.session.commit()
            rows = _flow_rows(_filters(m))
            assert len(rows) == 1
            assert rows[0]['date'] == "2026-09-03", rows[0]['date']

    def test_t3_doc_date_within_end_but_created_later_is_included(self):
        """T3 单据日期 ≤ end_date 但流水时间 > end_date → 仍纳入（原 SQL 会误剔除）。"""
        with app_module.app.test_request_context():
            _reset_db()
            m = _seed()
            o = _mk_in_order("IN-T3", date(2026, 9, 10))          # 单据日期在窗口内
            _mk_txn(o, 10, datetime(2026, 10, 5, 10, 0))          # 流水时间在窗口外
            rows = _flow_rows(_filters(m, start=date(2026, 9, 1), end=date(2026, 9, 30)))
            assert len(rows) == 1, rows
            assert rows[0]['date'] == "2026-09-10"

    def test_t4_doc_date_after_end_but_created_before_is_excluded(self):
        """T4 单据日期 > end_date 但流水时间 ≤ end_date → 排除（原 SQL 会误纳入）。"""
        with app_module.app.test_request_context():
            _reset_db()
            m = _seed()
            o = _mk_in_order("IN-T4", date(2026, 10, 1))          # 单据日期在窗口外
            _mk_txn(o, 10, datetime(2026, 9, 20, 10, 0))          # 流水时间在窗口内
            rows = _flow_rows(_filters(m, start=date(2026, 9, 1), end=date(2026, 9, 30)))
            assert rows == [], rows

    def test_t5_opening_boundary_uses_document_date(self):
        """T5 单据日期 < start_date → 计期初结存、不显示明细行（即使流水时间在窗口内）。"""
        with app_module.app.test_request_context():
            _reset_db()
            m = _seed()
            o = _mk_in_order("IN-T5", date(2026, 8, 20))          # 单据日期早于 start_date
            _mk_txn(o, 10, datetime(2026, 9, 2, 10, 0))           # 流水时间在窗口内
            rows = _flow_rows(_filters(m, start=date(2026, 9, 1), end=date(2026, 9, 30)))
            assert rows == [], rows
            all_rows = _collect_ledger_rows(_filters(m, start=date(2026, 9, 1), end=date(2026, 9, 30)))
            opening = [r for r in all_rows if r.get('reference_type') == '期初结存']
            assert len(opening) == 1
            assert opening[0]['balance_quantity'] == 10, opening[0]

    def test_t6_balance_accumulates_in_document_date_order(self):
        """T6 结存累加按单据日期：补录单（日期早、流水晚）排在正常单之前，结存正确。

        单 A：单据日期 9/10、流水时间 9/1（正常）。
        单 B：单据日期 9/2、流水时间 9/5（补录，单据日期早但流水晚）。
        按业务日期：B(9/2) 先、A(9/10) 后 → 结存 B=10、A=20。
        若按 created_at 累加（错误）：A(9/1)=10、B(9/5)=20，展示却按日期 B 在前，
        会出现 B 行结存显示 20、A 行显示 10 的错乱。
        """
        with app_module.app.test_request_context():
            _reset_db()
            m = _seed()
            oa = _mk_in_order("IN-T6-A", date(2026, 9, 10))
            _mk_txn(oa, 10, datetime(2026, 9, 1, 10, 0))
            ob = _mk_in_order("IN-T6-B", date(2026, 9, 2))
            _mk_txn(ob, 10, datetime(2026, 9, 5, 10, 0))
            rows = _flow_rows(_filters(m))
            assert [r['date'] for r in rows] == ["2026-09-02", "2026-09-10"], rows
            assert [r['balance_quantity'] for r in rows] == [10, 20], rows

    def test_t7_marker_rows_unchanged(self):
        """T7 期初/合计标记行日期仍为 start_date / end_date（不受业务日期影响）。"""
        with app_module.app.test_request_context():
            _reset_db()
            m = _seed()
            o = _mk_in_order("IN-T7", date(2026, 9, 15))
            _mk_txn(o, 10, datetime(2026, 9, 15, 10, 0))
            all_rows = _collect_ledger_rows(_filters(m, start=date(2026, 9, 1), end=date(2026, 9, 30)))
            opening = [r for r in all_rows if r.get('reference_type') == '期初结存'][0]
            closing = [r for r in all_rows if r.get('reference_type') == '本期合计'][0]
            assert opening['date'] == "2026-09-01", opening['date']
            assert closing['date'] == "2026-09-30", closing['date']
