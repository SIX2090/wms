# -*- coding: utf-8 -*-
"""BUG-2026-09-07-014 回归：物料采购汇总报表 SQL 分页下沉。

背景：物料采购汇总与采购执行/供应商采购汇总/采购价格分析**共用**采集器
`_collect_purchase_order_execution_rows`，而该采集器受 REPORT_ROW_LIMIT(5 万)
截断。原内存路径把采购明细物化后再在 Python 里按物料分桶，超 5 万行时明细
被截断，而汇总卡片正是对这份**截断后的分桶结果**求和——长周期查询会出现
「采购金额比实际小」，违反 R2「汇总 = 明细全集」。

本修复把分桶与聚合下沉 SQL GROUP BY 物料（编码/名称/规格），汇总改由 SQL
全量聚合并与分页解耦；`last_supplier` 的「分组内取最新一行」语义不依赖窗口
函数，改用三次分组回连逐层收敛。

断言：
  T1. 分页语义：物料行分页正确、互不重叠，total 为真实物料数。
  T2. 汇总与分页解耦 + R2：不同页 summary 相同；且「各页明细加总 == 汇总」。
  T3. 默认排序：最近采购日期倒序。
  T4. 排序：按 amount 降序时首行为最大值。
  T5. 仓库必填与多仓隔离（R2）：无仓库返回空；B 仓数据不串入 A 仓。
  T6. API 层：/report/api/material_purchase_summary 分页元数据正确且不截断。
  T7. SQL 路径与内存路径分桶结果一致（按物料比对，防口径漂移）。
  T8. last_supplier 取「分组内最新一行」：同日期按单号倒序取最大者。
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
D5 = date(2026, 9, 5)
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


class TestBug20260907014:
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
            sup3 = Supplier(code="S3", name="供应商丙")
            db.session.add_all([self.wh_a, self.wh_b, unit, user, sup1, sup2, sup3])
            db.session.flush()
            m1 = Material(code="M001", name="电缆", spec="2.5mm",
                          unit_id=unit.id, price=10.0, stock=0.0)
            m2 = Material(code="M002", name="开关", spec="16A",
                          unit_id=unit.id, price=20.0, stock=0.0)
            m3 = Material(code="M003", name="插座", spec="五孔",
                          unit_id=unit.id, price=5.0, stock=0.0)
            db.session.add_all([m1, m2, m3])
            db.session.flush()

            self.user_id = user.id
            self.sup1_id, self.sup2_id, self.sup3_id = sup1.id, sup2.id, sup3.id
            self.m1_id, self.m2_id, self.m3_id = m1.id, m2.id, m3.id

            # ==== M001：两单两个供应商（甲 09-01 / 乙 09-02）====
            # PO-1（09-01，甲，partial）：M001×10 收 4 @10 → 100
            self._add_po("PO-1", D1, sup1.id, "partial", PAST, [
                (m1.id, 10.0, 4.0, 10.0, 100.0),
            ], "仓库A", "PIN-1")
            # PO-2（09-02，乙，pending）：M001×5 收 0 @12 → 60
            self._add_po("PO-2", D2, sup2.id, "pending", FUTURE, [
                (m1.id, 5.0, 0.0, 12.0, 60.0),
            ], "仓库A", "PIN-2")

            # ==== M002：单供应商 ====
            # PO-3（09-03，甲，completed）：M002×4 全收 @20 → 80
            self._add_po("PO-3", D3, sup1.id, "completed", PAST, [
                (m2.id, 4.0, 4.0, 20.0, 80.0),
            ], "仓库A", "PIN-3")

            # ==== M003：同日两单（09-05），用于验证 last_supplier 单号倒序取大 ====
            # PO-4（丙）：M003×3 @5 → 15；PO-5（甲）：M003×2 全收 @6 → 12
            # 采集器按 (日期, 单号, 明细ID) 倒序 → PO-5 先出现 → last_supplier=甲
            self._add_po("PO-4", D5, sup3.id, "pending", FUTURE, [
                (m3.id, 3.0, 0.0, 5.0, 15.0),
            ], "仓库A", "PIN-4")
            self._add_po("PO-5", D5, sup1.id, "pending", FUTURE, [
                (m3.id, 2.0, 2.0, 6.0, 12.0),
            ], "仓库A", "PIN-5")

            # ==== B 仓（R2 隔离验证）====
            self._add_po("PO-B", D1, sup1.id, "pending", FUTURE, [
                (m2.id, 777.0, 0.0, 10.0, 7770.0),
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
    #   M001：2 单 / 2 供应商 / 订 15 / 收 4 / 剩 11 / 金额 160
    #         已入金额 40 / 未入金额 120 / 均价 10.67 / 最近供应商 乙 / 最近 09-02
    #   M002：1 单 / 1 供应商 / 订 4 / 收 4 / 剩 0 / 金额 80
    #         已入金额 80 / 未入金额 0 / 均价 20 / 最近供应商 甲 / 最近 09-03
    #   M003：2 单 / 2 供应商 / 订 5 / 收 2 / 剩 3 / 金额 27
    #         已入金额 12 / 未入金额 15 / 均价 5.4 / 最近供应商 甲 / 最近 09-05
    #   summary：物料数 3 / 数量 24 / 金额 267
    def test_T1_pagination_semantics(self):
        """3 个物料；page_size=1 时三页各 1 行、互不重叠、total=3。"""
        with app_module.app.app_context():
            seen = []
            for page in (1, 2, 3):
                _, rows, _, total = app_module._sql_paged_material_purchase_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                assert len(rows) == 1, f"page{page} 应 1 行，实际 {len(rows)}"
                assert total == 3, f"total 应为真实物料数 3，实际 {total}"
                seen.append(rows[0]['material_code'])
            assert len(set(seen)) == 3, f"分页结果重叠: {seen}"

    def test_T2_summary_decoupled_and_equals_detail_sum(self):
        """汇总与分页解耦，且「各页明细加总 == 汇总」（R2 汇总 = 明细全集）。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_material_purchase_report(
                _filters(**self.a_kw, page=1, page_size=1))
            _, _, s3, _ = app_module._sql_paged_material_purchase_report(
                _filters(**self.a_kw, page=3, page_size=1))
            assert s1 == s3, "不同页 summary 必须一致（全集口径）"
            assert s1['count'] == 3, f"物料数应为 3，实际 {s1['count']}"
            assert s1['quantity'] == 24, f"采购数量应为 24，实际 {s1['quantity']}"
            assert s1['amount'] == 267, f"采购金额应为 267，实际 {s1['amount']}"

            all_rows = []
            for page in (1, 2, 3):
                _, rows, _, _ = app_module._sql_paged_material_purchase_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                all_rows.extend(rows)
            assert sum(r['order_quantity'] for r in all_rows) == s1['quantity']
            assert sum(r['amount'] for r in all_rows) == s1['amount']

    def test_T3_default_sort_last_purchase_date_desc(self):
        """默认按最近采购日期倒序：M003(09-05) > M002(09-03) > M001(09-02)。"""
        with app_module.app.app_context():
            _, rows, _, _ = app_module._sql_paged_material_purchase_report(
                _filters(**self.a_kw))
            codes = [r['material_code'] for r in rows]
            assert codes == ['M003', 'M002', 'M001'], f"默认排序错误: {codes}"

    def test_T4_sort_by_amount_desc(self):
        """按 amount 降序：首行为金额最大的 M001（160）。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_material_purchase_report(
                _filters(**self.a_kw, sort_field='amount', sort_order='desc'))
            assert total == 3
            amounts = [r['amount'] for r in rows]
            assert amounts[0] == 160, f"降序首行应为 160，实际 {amounts[0]}"
            assert amounts == sorted(amounts, reverse=True), "当页必须按金额降序"

    def test_T5_warehouse_required_and_isolation(self):
        """无仓库返回空；B 仓数据不串入 A 仓（R2）。"""
        with app_module.app.app_context():
            _, rows, summary, total = app_module._sql_paged_material_purchase_report(
                _filters())
            assert total == 0 and rows == [], "无仓库必须返回空"
            assert summary == {'count': 0, 'quantity': 0, 'amount': 0}

            _, rows_a, summary_a, total_a = app_module._sql_paged_material_purchase_report(
                _filters(**self.a_kw))
            assert total_a == 3, f"A 仓应 3 个物料，实际 {total_a}"
            assert summary_a['quantity'] == 24
            assert all(r['order_quantity'] != 777 for r in rows_a), "B 仓 777 串入 A 仓"

            _, _, summary_b, total_b = app_module._sql_paged_material_purchase_report(
                _filters(**self.b_kw))
            assert total_b == 1, f"B 仓应 1 个物料，实际 {total_b}"
            assert summary_b['quantity'] == 777, f"B 仓数量应为 777，实际 {summary_b['quantity']}"

    def test_T6_api_pagination_response(self):
        """API：page=2&page_size=1 → total=3、len(data)=1、total_pages=3、truncated=False。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(
            f"/report/api/material_purchase_summary?warehouse_id={self.wh_a_id}"
            "&page=2&page_size=1")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 3
        assert len(data['data']) == 1
        assert data['total_pages'] == 3
        assert data['truncated'] is False, "SQL 聚合不应触发明细截断"
        assert data['summary']['amount'] == 267

    def test_T7_sql_path_matches_memory_path(self):
        """SQL 路径与内存路径分桶结果一致（按物料比对，防口径漂移）。

        与 009-07-013 同款两点环境/历史差异，故按「报表声明列」逐字段比对：
        1) 内存路径 order_count 由 row['order_url'] 去重得到，依赖 url_for，
           必须在请求上下文内才有值，故本用例显式包 test_request_context；
        2) 内存路径共用 _build_purchase_summary_row，会多带一个恒为 0 的
           material_count（物料分桶无 material_ids），不在声明列内。
        """
        declared = {c['field'] for c in app_module._material_purchase_summary_columns()}
        with app_module.app.test_request_context('/report/view/material_purchase_summary'):
            _, mem_rows, mem_summary = app_module._build_material_purchase_report(
                _filters(**self.a_kw))
            _, sql_rows, sql_summary, sql_total = \
                app_module._sql_paged_material_purchase_report(
                    _filters(**self.a_kw, export='excel'))

            def _norm(row):
                return {k: v for k, v in row.items() if k in declared}

            mem_by_code = {r['material_code']: _norm(r) for r in mem_rows}
            sql_by_code = {r['material_code']: _norm(r) for r in sql_rows}
            assert mem_by_code.keys() == sql_by_code.keys(), \
                f"物料集合不一致: 内存 {sorted(mem_by_code)} vs SQL {sorted(sql_by_code)}"
            for code in mem_by_code:
                assert mem_by_code[code] == sql_by_code[code], \
                    f"{code} 分桶内容不一致: 内存 {mem_by_code[code]} vs SQL {sql_by_code[code]}"
            assert sql_total == len(mem_rows)
            assert sql_summary == mem_summary, "汇总口径必须与内存路径一致"

    def test_T8_last_supplier_picks_latest_row_in_group(self):
        """last_supplier 取分组内「最新一行」：同日期按单号倒序取大者（PO-5 > PO-4）。"""
        with app_module.app.app_context():
            _, rows, _, _ = app_module._sql_paged_material_purchase_report(
                _filters(**self.a_kw))
            by_code = {r['material_code']: r for r in rows}
            assert by_code['M003']['last_supplier'] == '供应商甲', \
                f"M003 同日两单应取单号更大的 PO-5(甲)，实际 {by_code['M003']['last_supplier']}"
            assert by_code['M003']['last_purchase_date'] == '2026-09-05'
            assert by_code['M001']['last_supplier'] == '供应商乙', "M001 最近供应商应为乙(09-02)"
            assert by_code['M002']['last_supplier'] == '供应商甲'
