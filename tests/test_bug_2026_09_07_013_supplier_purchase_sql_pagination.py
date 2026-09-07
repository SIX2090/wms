# -*- coding: utf-8 -*-
"""BUG-2026-09-07-013 回归：供应商采购汇总报表 SQL 分页下沉。

背景：供应商采购汇总与采购执行/物料汇总/价格分析**共用**采集器
`_collect_purchase_order_execution_rows`，而该采集器受 REPORT_ROW_LIMIT(5 万)
截断。原内存路径把采购明细物化后再在 Python 里按供应商分桶，超 5 万行时明细
被截断，而汇总卡片正是对这份**截断后的分桶结果**求和——长周期查询会出现
「采购金额比实际小」，违反 R2「汇总 = 明细全集」。

本修复把分桶与聚合下沉 SQL GROUP BY 供应商（复用 009-07-011 的
`_purchase_order_item_query`，并对 warehouse 分支的入库单展开做 DISTINCT 防护），
汇总改由 SQL 全量聚合并与分页解耦。

断言：
  T1. 分页语义：供应商行分页正确、互不重叠，total 为真实供应商数。
  T2. 汇总与分页解耦 + R2：不同页 summary 相同；且「各页明细加总 == 汇总」。
  T3. 默认排序：最近采购日期倒序。
  T4. 排序：按 amount 降序时首行为最大值。
  T5. 仓库必填与多仓隔离（R2）：无仓库返回空；B 仓数据不串入 A 仓。
  T6. API 层：/report/api/supplier_purchase_summary 分页元数据正确且不截断。
  T7. SQL 路径与内存路径分桶结果一致（按供应商比对，防口径漂移）。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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
from app import (InOrder, Material, PurchaseOrder, PurchaseOrderItem,  # noqa: E402
                 Supplier, Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

D1 = date(2026, 9, 1)
D2 = date(2026, 9, 2)
D3 = date(2026, 9, 3)
PAST = date(2026, 8, 1)      # 已逾期
FUTURE = date(2026, 12, 31)  # 未到期


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


class TestBug20260907013:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            self.wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            self.wh_b = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            sup1 = Supplier(code="S1", name="供应商甲")
            sup2 = Supplier(code="S2", name="供应商乙")
            db.session.add_all([self.wh_a, self.wh_b, unit, user, sup1, sup2])
            db.session.flush()
            m1 = Material(code="M001", name="电缆", unit_id=unit.id, price=10.0, stock=0.0)
            m2 = Material(code="M002", name="开关", unit_id=unit.id, price=20.0, stock=0.0)
            db.session.add_all([m1, m2])
            db.session.flush()

            self.user_id = user.id
            self.sup1_id, self.sup2_id = sup1.id, sup2.id
            self.m1_id, self.m2_id = m1.id, m2.id

            # ==== 供应商甲 ====
            # PO-1（09-01，partial，预计到货已过期）：M001×10 未收、M002×5 未收 → 2 行逾期
            self._add_po("PO-1", D1, sup1.id, "partial", PAST, [
                (m1.id, 10.0, 0.0, 10.0, 100.0),
                (m2.id, 5.0, 0.0, 20.0, 100.0),
            ], "仓库A", "PIN-1")
            # PO-2（09-02，completed，已收完 → 剩余 0 不逾期）：M001×4 全收
            self._add_po("PO-2", D2, sup1.id, "completed", PAST, [
                (m1.id, 4.0, 4.0, 10.0, 40.0),
            ], "仓库A", "PIN-2")

            # ==== 供应商乙 ====
            # PO-3（09-03，pending，未到期 → 不逾期）：M002×2 未收
            self._add_po("PO-3", D3, sup2.id, "pending", FUTURE, [
                (m2.id, 2.0, 0.0, 20.0, 40.0),
            ], "仓库A", "PIN-3")

            # ==== B 仓（R2 隔离验证）====
            self._add_po("PO-B", D1, sup1.id, "pending", FUTURE, [
                (m1.id, 777.0, 0.0, 10.0, 7770.0),
            ], "仓库B", "PIN-B")

            db.session.commit()
            self.wh_a_id = self.wh_a.id
            self.wh_b_id = self.wh_b.id
            self.a_kw = dict(warehouse_id=self.wh_a_id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=self.wh_b_id, warehouse="仓库B", warehouse_code="WHB")

    def _add_po(self, order_no, day, supplier_id, status, expected, items,
                in_warehouse, in_order_no):
        po = PurchaseOrder(order_no=order_no, date=day, supplier_id=supplier_id,
                           status=status, operator_id=self.user_id,
                           expected_date=expected, total_amount=0.0)
        db.session.add(po)
        db.session.flush()
        for material_id, qty, received, price, amount in items:
            db.session.add(PurchaseOrderItem(
                purchase_order_id=po.id, material_id=material_id,
                quantity=qty, received_quantity=received,
                price=price, amount=amount))
        # 采购订单本身不记录仓库，归属靠关联入库单；本测试用
        # InOrder.source_purchase_order_id 建立归属
        db.session.add(InOrder(order_no=in_order_no, date=day,
                               warehouse=in_warehouse, status="completed",
                               operator_id=self.user_id, business_type="采购入库",
                               source_purchase_order_id=po.id))

    # 期望口径（A 仓）：
    #   供应商甲：订单 2 / 物料 2 / 订 19 / 收 4 / 剩 15 / 金额 240
    #             已收金额 40 / 未收金额 200 / 逾期行 2 / 最近 2026-09-02 / 均价 240/19≈12.63
    #   供应商乙：订单 1 / 物料 1 / 订 2 / 收 0 / 剩 2 / 金额 40
    #             已收金额 0 / 未收金额 40 / 逾期行 0 / 最近 2026-09-03 / 均价 20
    #   summary：供应商数 2 / 数量 21 / 金额 280
    def test_T1_pagination_semantics(self):
        """2 个供应商；page_size=1 时两页各 1 行、互不重叠、total=2。"""
        with app_module.app.app_context():
            seen = []
            for page in (1, 2):
                _, rows, _, total = app_module._sql_paged_supplier_purchase_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                assert len(rows) == 1, f"page{page} 应 1 行，实际 {len(rows)}"
                assert total == 2, f"total 应为真实供应商数 2，实际 {total}"
                seen.append(rows[0]['supplier'])
            assert len(set(seen)) == 2, f"分页结果重叠: {seen}"

    def test_T2_summary_decoupled_and_equals_detail_sum(self):
        """汇总与分页解耦，且「各页明细加总 == 汇总」（R2 汇总 = 明细全集）。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_supplier_purchase_report(
                _filters(**self.a_kw, page=1, page_size=1))
            _, _, s2, _ = app_module._sql_paged_supplier_purchase_report(
                _filters(**self.a_kw, page=2, page_size=1))
            assert s1 == s2, "不同页 summary 必须一致（全集口径）"
            assert s1['count'] == 2, f"供应商数应为 2，实际 {s1['count']}"
            assert s1['quantity'] == 21, f"采购数量应为 21，实际 {s1['quantity']}"
            assert s1['amount'] == 280, f"采购金额应为 280，实际 {s1['amount']}"

            all_rows = []
            for page in (1, 2):
                _, rows, _, _ = app_module._sql_paged_supplier_purchase_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                all_rows.extend(rows)
            assert sum(r['order_quantity'] for r in all_rows) == s1['quantity']
            assert sum(r['amount'] for r in all_rows) == s1['amount']

    def test_T3_default_sort_last_purchase_date_desc(self):
        """默认按最近采购日期倒序：乙(09-03) 在 甲(09-02) 之前。"""
        with app_module.app.app_context():
            _, rows, _, _ = app_module._sql_paged_supplier_purchase_report(
                _filters(**self.a_kw))
            names = [r['supplier'] for r in rows]
            assert names == ['供应商乙', '供应商甲'], f"默认排序错误: {names}"

    def test_T4_sort_by_amount_desc(self):
        """按 amount 降序：首行为金额最大的供应商甲（240）。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_supplier_purchase_report(
                _filters(**self.a_kw, sort_field='amount', sort_order='desc'))
            assert total == 2
            amounts = [r['amount'] for r in rows]
            assert amounts[0] == 240, f"降序首行应为 240，实际 {amounts[0]}"
            assert amounts == sorted(amounts, reverse=True), "当页必须按金额降序"

    def test_T5_warehouse_required_and_isolation(self):
        """无仓库返回空；B 仓数据不串入 A 仓（R2）。"""
        with app_module.app.app_context():
            _, rows, summary, total = app_module._sql_paged_supplier_purchase_report(
                _filters())
            assert total == 0 and rows == [], "无仓库必须返回空"
            assert summary == {'count': 0, 'quantity': 0, 'amount': 0}

            _, rows_a, summary_a, total_a = app_module._sql_paged_supplier_purchase_report(
                _filters(**self.a_kw))
            assert total_a == 2, f"A 仓应 2 个供应商，实际 {total_a}"
            assert summary_a['quantity'] == 21
            assert all(r['order_quantity'] != 777 for r in rows_a), "B 仓 777 串入 A 仓"

            _, _, summary_b, total_b = app_module._sql_paged_supplier_purchase_report(
                _filters(**self.b_kw))
            assert total_b == 1, f"B 仓应 1 个供应商，实际 {total_b}"
            assert summary_b['quantity'] == 777, f"B 仓数量应为 777，实际 {summary_b['quantity']}"

    def test_T6_api_pagination_response(self):
        """API：page=2&page_size=1 → total=2、len(data)=1、total_pages=2、truncated=False。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(
            f"/report/api/supplier_purchase_summary?warehouse_id={self.wh_a_id}"
            "&page=2&page_size=1")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 2
        assert len(data['data']) == 1
        assert data['total_pages'] == 2
        assert data['truncated'] is False, "SQL 聚合不应触发明细截断"
        assert data['summary']['amount'] == 280

    def test_T7_sql_path_matches_memory_path(self):
        """SQL 路径与内存路径分桶结果一致（按供应商比对，防口径漂移）。

        注意两点环境/历史差异，因此按「报表声明列」逐字段比对：
        1) 内存路径 order_count 由 row['order_url'] 去重得到，而 order_url 依赖
           url_for —— 必须在请求上下文内才有值，故本用例显式包 test_request_context。
        2) 内存路径共用 _build_purchase_summary_row，会多带一个恒为 0 的
           supplier_count（供应商分桶无 supplier_ids），该字段不在
           _supplier_purchase_summary_columns() 声明列内，SQL 路径不产出。
        """
        declared = {c['field'] for c in app_module._supplier_purchase_summary_columns()}
        with app_module.app.test_request_context('/report/view/supplier_purchase_summary'):
            _, mem_rows, mem_summary = app_module._build_supplier_purchase_report(
                _filters(**self.a_kw))
            _, sql_rows, sql_summary, sql_total = \
                app_module._sql_paged_supplier_purchase_report(
                    _filters(**self.a_kw, export='excel'))

            def _norm(row):
                return {k: v for k, v in row.items() if k in declared}

            mem_by_sup = {r['supplier']: _norm(r) for r in mem_rows}
            sql_by_sup = {r['supplier']: _norm(r) for r in sql_rows}
            assert mem_by_sup.keys() == sql_by_sup.keys(), \
                f"供应商集合不一致: 内存 {sorted(mem_by_sup)} vs SQL {sorted(sql_by_sup)}"
            for name in mem_by_sup:
                assert mem_by_sup[name] == sql_by_sup[name], \
                    f"{name} 分桶内容不一致: 内存 {mem_by_sup[name]} vs SQL {sql_by_sup[name]}"
            assert sql_total == len(mem_rows)
            assert sql_summary == mem_summary, "汇总口径必须与内存路径一致"
