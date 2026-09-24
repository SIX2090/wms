# -*- coding: utf-8 -*-
"""FEAT-2026-09-24-001 回归：库存台账明细显示「合同编号」。

需求：库存台账要看每条流水是**哪个合同**——入库是哪张合同的货、出库领的是哪张合同的料。

设计要点（本测试逐条锁死）：
1. 取值口径 = **明细行优先、单据头兜底**——与入库单/领料单自带的 Excel 导出完全一致
   （in_order.py:177、out_order.py:137 均为 `item.contract_no or order.contract_no`），
   避免同一张单在「台账」与「单据导出」里给出两个不同答案。
2. **必须按行取**（关键）：一张单含多个物料时，各行合同可能不同——下推/复制生成时
   行级合同号从采购单行（in_order.py:684/715）/ 销售单行（out_order.py:215/239）继承。
   只取单据头会把 A 物料的合同错戴到 B 物料头上。
3. 匹配键为 (单据 id, material_id)：流水按物料记账。同单同物料多行明细时取首个非空
   行值，**不拼接**（「A,B」不是任何一张真实合同）。
4. 仅 in_order / out_order 有合同字段；调拨/盘点/调整/委外/售后出库模型本身没有，
   一律留空（不硬取不存在的字段造恒空列）。
5. 期初结存 / 本期合计是汇总标记行，不对应任何单据，留空。

T1 入库流水：明细行有合同号 -> 取行级值。
T2 入库流水：明细行无合同号 -> 兜底单据头。
T3 同一入库单两个物料不同合同 -> 各自流水取各自行的合同（防「头戴所有行」）。
T4 领料单（出库）：明细行有合同号 -> 取行级值。
T5 领料单：明细行无 -> 兜底单据头。
T6 无合同单据（调拨单）-> 留空，不报错、不显示 "-"。
T7 columns 含「合同编号」列且紧跟「单据编号」（阅读顺序）。
T8 期初结存 / 本期合计行 contract_no 为空串。
T9 导出 Excel 表头含「合同编号」（三个消费路径之一，防只改页面漏改导出）。
T10 排序字段 contract_no 可用（列存在即行存在，防渲染 undefined）。
"""
from __future__ import annotations

import io
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
    db, InOrder, InOrderItem, Material, MaterialCategory, OutOrder, OutOrderItem,
    StockTransaction, TransferOrder, Unit, Warehouse, set_system_setting,
    _collect_ledger_rows, _ledger_columns,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    """单仓库场景（_warehouse_scoped_txn_condition 单仓库不过滤，造数最简）。"""
    set_system_setting("location_management_enabled", "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT"),
        Warehouse(id=1, code="WHA", name="仓库A", is_default=True, status="active"),
    ])
    db.session.commit()
    m1 = Material(code="M001", name="轴承", spec="6204", category_id=1, unit_id=1, stock=0, price=10)
    m2 = Material(code="M002", name="齿轮", spec="G20", category_id=1, unit_id=1, stock=0, price=20)
    db.session.add_all([m1, m2])
    db.session.commit()
    return m1, m2


def _filters(mat):
    return {
        'start_date': None, 'end_date': None,
        'warehouse_id': 1, 'warehouse': '仓库A', 'warehouse_code': 'WHA',
        'business_type': '', 'material_code': mat.code,
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc', 'page': 1, 'page_size': 20,
        'hide_zero': False, 'export': '',
    }


def _mk_in_order(contract_no=None):
    o = InOrder(order_no=f"IN-{datetime.now().timestamp()}", date=date.today(),
                warehouse="仓库A", location="", status='completed',
                business_type='采购入库', contract_no=contract_no)
    db.session.add(o)
    db.session.commit()
    return o


def _mk_in_item(order, material, contract_no=None):
    it = InOrderItem(in_order_id=order.id, material_id=material.id,
                     quantity=10, price=10, amount=100, contract_no=contract_no)
    db.session.add(it)
    db.session.commit()
    return it


def _mk_out_order(contract_no=None):
    o = OutOrder(order_no=f"OU-{datetime.now().timestamp()}", date=date.today(),
                 warehouse="仓库A", location="", status='completed',
                 business_type='领料出库', contract_no=contract_no)
    db.session.add(o)
    db.session.commit()
    return o


def _mk_out_item(order, material, contract_no=None):
    it = OutOrderItem(out_order_id=order.id, material_id=material.id,
                      quantity=5, price=10, amount=50, contract_no=contract_no)
    db.session.add(it)
    db.session.commit()
    return it


def _mk_txn(material, qty, ref_type, ref_id, mins=0):
    t = StockTransaction(material_id=material.id, transaction_type='in' if qty > 0 else 'out',
                         quantity=qty, location="仓库A", warehouse_id=1,
                         reference_type=ref_type, reference_id=ref_id,
                         created_at=datetime(2026, 9, 1, 10, mins or 0))
    db.session.add(t)
    db.session.commit()
    return t


def _flow_rows(filters):
    """台账含期初/合计标记行；本文件断言只针对流水行。"""
    return [r for r in _collect_ledger_rows(filters)
            if r.get('reference_type') not in ('期初结存', '本期合计')]


class TestLedgerContractNoColumn:

    def test_t1_in_order_row_contract_wins(self):
        """T1 入库流水：明细行有合同号 -> 取行级值（单据头不同值不构成干扰）。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, _ = _seed()
            o = _mk_in_order(contract_no="HEAD-999")       # 单据头故意不同
            _mk_in_item(o, m1, contract_no="ROW-AAA")
            _mk_txn(m1, 10, 'in_order', o.id, mins=1)
            rows = _flow_rows(_filters(m1))
            assert len(rows) == 1
            assert rows[0]['contract_no'] == "ROW-AAA"

    def test_t2_in_order_fallback_to_header(self):
        """T2 入库流水：明细行无合同号 -> 兜底单据头。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, _ = _seed()
            o = _mk_in_order(contract_no="HEAD-777")
            _mk_in_item(o, m1, contract_no=None)
            _mk_txn(m1, 10, 'in_order', o.id, mins=1)
            rows = _flow_rows(_filters(m1))
            assert rows[0]['contract_no'] == "HEAD-777"

    def test_t3_per_material_not_header_for_all(self):
        """T3 同一入库单两个物料不同合同 -> 各流水取各行合同（防「头戴所有行」）。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, m2 = _seed()
            o = _mk_in_order(contract_no="HEAD-000")
            _mk_in_item(o, m1, contract_no="ROW-M1")
            _mk_in_item(o, m2, contract_no="ROW-M2")
            _mk_txn(m1, 10, 'in_order', o.id, mins=1)
            _mk_txn(m2, 20, 'in_order', o.id, mins=2)
            r1 = _flow_rows(_filters(m1))
            r2 = _flow_rows(_filters(m2))
            assert r1[0]['contract_no'] == "ROW-M1", r1
            assert r2[0]['contract_no'] == "ROW-M2", r2
            # 反过来锁：绝不能都变成单据头
            assert not (r1[0]['contract_no'] == "HEAD-000" and r2[0]['contract_no'] == "HEAD-000")

    def test_t4_out_order_row_contract_wins(self):
        """T4 领料单（出库）：明细行有合同号 -> 取行级值。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, _ = _seed()
            o = _mk_out_order(contract_no="HEAD-OUT")
            _mk_out_item(o, m1, contract_no="ROW-OUT")
            _mk_txn(m1, -5, 'out_order', o.id, mins=1)
            rows = _flow_rows(_filters(m1))
            assert rows[0]['contract_no'] == "ROW-OUT"

    def test_t5_out_order_fallback_to_header(self):
        """T5 领料单：明细行无 -> 兜底单据头。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, _ = _seed()
            o = _mk_out_order(contract_no="HEAD-OUT2")
            _mk_out_item(o, m1, contract_no=None)
            _mk_txn(m1, -5, 'out_order', o.id, mins=1)
            rows = _flow_rows(_filters(m1))
            assert rows[0]['contract_no'] == "HEAD-OUT2"

    def test_t6_no_contract_docs_blank(self):
        """T6 无合同字段的单据（调拨单）-> 留空串，不报错也不显示 '-'。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, _ = _seed()
            tr = TransferOrder(transfer_no="TR-1", date=date.today(),
                               from_warehouse="仓库A", to_warehouse="仓库A",
                               from_location="", to_location="",   # 两列均 NOT NULL
                               status='completed')
            db.session.add(tr)
            db.session.commit()
            _mk_txn(m1, 3, 'transfer', tr.id, mins=1)
            rows = _flow_rows(_filters(m1))
            assert rows[0]['contract_no'] == ""

    def test_t7_column_present_after_reference_no(self):
        """T7 columns 含「合同编号」且紧跟「单据编号」（阅读顺序 + 三路同源）。"""
        cols = _ledger_columns()
        fields = [c['field'] for c in cols]
        assert 'contract_no' in fields, fields
        assert fields.index('contract_no') == fields.index('reference_no') + 1, fields
        by_field = {c['field']: c for c in cols}
        assert by_field['contract_no']['title'] == '合同编号'

    def test_t8_marker_rows_blank(self):
        """T8 期初结存 / 本期合计标记行不对应单据，contract_no 为空串。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, _ = _seed()
            o = _mk_in_order(contract_no="HEAD-X")
            _mk_in_item(o, m1, contract_no="ROW-X")
            _mk_txn(m1, 10, 'in_order', o.id, mins=1)
            filters = _filters(m1)
            filters['start_date'] = date(2026, 9, 1)
            filters['end_date'] = date(2026, 9, 30)
            all_rows = _collect_ledger_rows(filters)
            markers = [r for r in all_rows
                       if r.get('reference_type') in ('期初结存', '本期合计')]
            assert len(markers) == 2, all_rows
            assert all(r['contract_no'] == '' for r in markers), markers

    def test_t9_export_excel_header_includes_column(self):
        """T9 导出 Excel 表头含「合同编号」——三个消费路径之一，防只改页面漏改导出。

        直接断言 `_iter_report_export_batches` 产出的 columns：_build_report_excel_download
        就是遍历它执行 ``worksheet.append([column['title'] ...])`` 写表头、按同一 columns
        逐格写行的（不另设列清单），故 columns 含该列 ⇔ 导出表头含该列。
        不走 Response.data 是因为 send_file 处于 direct_passthrough 模式，取 data 会抛
        RuntimeError（与产品无关，纯测试取数方式问题）。
        """
        from app import _iter_report_export_batches

        with app_module.app.test_request_context():
            _reset_db()
            m1, _ = _seed()
            o = _mk_in_order(contract_no="HEAD-E")
            _mk_in_item(o, m1, contract_no="ROW-E")
            _mk_txn(m1, 10, 'in_order', o.id, mins=1)
            filters = _filters(m1)
            seen_cols = None
            seen_values = []
            for batch_columns, rows in _iter_report_export_batches('ledger', filters):
                if seen_cols is None:
                    seen_cols = batch_columns
                seen_values.extend(r.get('contract_no', '<MISSING>') for r in rows)
            assert seen_cols is not None, "导出批次未产出列定义"
            titles = [c['title'] for c in seen_cols]
            assert '合同编号' in titles, titles
            assert "ROW-E" in seen_values, seen_values

    def test_t10_sortable_and_all_rows_have_key(self):
        """T10 每行都有 contract_no 键（防前端渲染 undefined）+ 可作排序字段。"""
        with app_module.app.test_request_context():
            _reset_db()
            m1, m2 = _seed()
            o1 = _mk_in_order(contract_no="C-B")
            _mk_in_item(o1, m1, contract_no="C-B")
            _mk_txn(m1, 10, 'in_order', o1.id, mins=1)
            o2 = _mk_out_order(contract_no="C-A")
            _mk_out_item(o2, m1, contract_no="C-A")
            _mk_txn(m1, -3, 'out_order', o2.id, mins=2)
            rows = _collect_ledger_rows(_filters(m1))
            assert rows and all('contract_no' in r for r in rows), rows
            # 模拟前端/后端排序：字段存在才可排（_sort_rows 用 rows[0] 判定）
            from app import _sort_rows
            sorted_rows = _sort_rows(rows, 'contract_no', 'asc')
            flow = [r['contract_no'] for r in sorted_rows
                    if r.get('reference_type') not in ('期初结存', '本期合计')]
            assert flow == sorted(flow), flow
