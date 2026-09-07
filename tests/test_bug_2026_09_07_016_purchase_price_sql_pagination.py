# -*- coding: utf-8 -*-
"""BUG-2026-09-07-016 回归：采购价格分析报表 SQL 分页下沉。

背景：采购价格分析与采购执行/供应商采购汇总/物料采购汇总**共用**采集器
`_collect_purchase_order_execution_rows`，而该采集器受 REPORT_ROW_LIMIT(5 万)
截断。原内存路径把采购明细物化后再在 Python 里按（物料 × 供应商）分桶，
超 5 万行时明细被截断，而汇总卡片正是对这份**截断后的分桶结果**求和——
长周期查询会出现「采购金额比实际小」，违反 R2「汇总 = 明细全集」。这是共用
该采集器的最后一张报表，做完整条采集器风险线关闭。

关键语义细节：内存路径取「最新一行」（last_price/last_order_no/url）用的是
`row_date >= last_purchase_date`（**含等号**）逐行覆写，而明细按
(日期, 单号, 明细ID) 倒序遍历 → 同一最大日期内**单号最小**者最终胜出
（与 009-07-014 物料汇总严格 `>` 取最大单号相反）。SQL 路径用两次 MIN 回连
复刻该语义，T8 专项锁定。

断言：
  T1. 分页语义：行分页正确、互不重叠，total 为真实组数。
  T2. 汇总与分页解耦 + R2：不同页 summary 相同；且「各页明细加总 == 汇总」。
  T3. 默认排序：最近采购日期倒序。
  T4. 排序：按 amount 降序时首行为最大值。
  T5. 仓库必填与多仓隔离（R2）：无仓库返回空；B 仓数据不串入 A 仓。
  T6. API 层：/report/api/purchase_price_analysis 分页元数据正确且不截断。
  T7. SQL 路径与内存路径分桶结果一致（按 物料×供应商 比对，防口径漂移）。
  T8. last_* 复刻含等号覆写语义：同日期取**单号最小**者的价格与单号。
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
D4 = date(2026, 9, 4)
D5 = date(2026, 9, 5)
FUTURE = date(2026, 12, 31)


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


class TestBug20260907016:
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
            m1 = Material(code="M001", name="电缆", spec="2.5mm",
                          unit_id=unit.id, price=10.0, stock=0.0)
            m2 = Material(code="M002", name="开关", spec="16A",
                          unit_id=unit.id, price=20.0, stock=0.0)
            db.session.add_all([m1, m2])
            db.session.flush()

            self.user_id = user.id
            self.sup1_id, self.sup2_id = sup1.id, sup2.id
            self.m1_id, self.m2_id = m1.id, m2.id

            # ==== G1：M001 × 供应商甲（三单，价格 10/12/11，最新 09-03@11 PO-3）====
            self._add_po("PO-1", D1, sup1.id, [
                (m1.id, 10.0, 10.0, 100.0),
            ], "仓库A", "PIN-1")
            self._add_po("PO-2", D2, sup1.id, [
                (m1.id, 5.0, 12.0, 60.0),
            ], "仓库A", "PIN-2")
            self._add_po("PO-3", D3, sup1.id, [
                (m1.id, 4.0, 11.0, 44.0),
            ], "仓库A", "PIN-3")

            # ==== G2：M001 × 供应商乙（09-05@20 PO-4）====
            self._add_po("PO-4", D5, sup2.id, [
                (m1.id, 6.0, 20.0, 120.0),
            ], "仓库A", "PIN-4")

            # ==== G3：M002 × 供应商甲（同日两单 09-02：PO-5 @5 / PO-6 @9）====
            # 内存路径含等号覆写 → 胜出者应为「单号最小」的 PO-5 @5（T8 专项）
            self._add_po("PO-5", D2, sup1.id, [
                (m2.id, 8.0, 5.0, 40.0),
            ], "仓库A", "PIN-5")
            self._add_po("PO-6", D2, sup1.id, [
                (m2.id, 2.0, 9.0, 18.0),
            ], "仓库A", "PIN-6")

            # ==== G4：M002 × 供应商乙（09-04@7 PO-7）====
            self._add_po("PO-7", D4, sup2.id, [
                (m2.id, 3.0, 7.0, 21.0),
            ], "仓库A", "PIN-7")

            # ==== G5：M001 × 无供应商（09-06@3 PO-8）→ 显示「未指定供应商」====
            self._add_po("PO-8", D5, None, [
                (m1.id, 2.0, 3.0, 6.0),
            ], "仓库A", "PIN-8")

            # ==== B 仓（R2 隔离验证）====
            self._add_po("PO-B", D1, sup1.id, [
                (m1.id, 777.0, 1.0, 7770.0),
            ], "仓库B", "PIN-B")

            db.session.commit()
            self.wh_a_id = self.wh_a.id
            self.wh_b_id = self.wh_b.id
            self.a_kw = dict(warehouse_id=self.wh_a_id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=self.wh_b_id, warehouse="仓库B", warehouse_code="WHB")

    def _add_po(self, order_no, day, supplier_id, items, in_warehouse, in_order_no):
        po = PurchaseOrder(order_no=order_no, date=day, supplier_id=supplier_id,
                           status="pending", operator_id=self.user_id,
                           expected_date=FUTURE, total_amount=0.0)
        db.session.add(po)
        db.session.flush()
        for material_id, qty, price, amount in items:
            db.session.add(PurchaseOrderItem(
                purchase_order_id=po.id, material_id=material_id,
                quantity=qty, received_quantity=0.0,
                price=price, amount=amount))
        # 采购订单本身不记录仓库，归属靠关联入库单；本测试用
        # InOrder.source_purchase_order_id 建立归属
        db.session.add(InOrder(order_no=in_order_no, date=day,
                               warehouse=in_warehouse, status="completed",
                               operator_id=self.user_id, business_type="采购入库",
                               source_purchase_order_id=po.id))

    # 期望口径（A 仓，5 组）：
    #   G1 M001×甲：次数3/数19/额204/min10/max12/均价10.74/last PO-3@11/09-03
    #   G2 M001×乙：次数1/数6/额120/min20/max20/均价20/last PO-4@20/09-05
    #   G3 M002×甲：次数2/数10/额58/min5/max9/价差4/均价5.8/last PO-5@5/09-02
    #   G4 M002×乙：次数1/数3/额21/min7/max7/均价7/last PO-7@7/09-04
    #   G5 M001×无：次数1/数2/额6/min3/max3/均价3/last PO-8@3/09-05（未指定供应商）
    #   summary：组5/数量40/金额409
    def _expect(self):
        return {
            ('M001', '供应商甲'): dict(purchase_times=3, quantity=19, amount=204,
                                       min_price=10, max_price=12, price_range=2,
                                       avg_price=10.74, last_order_no='PO-3',
                                       last_price=11, last_purchase_date='2026-09-03'),
            ('M001', '供应商乙'): dict(purchase_times=1, quantity=6, amount=120,
                                       min_price=20, max_price=20, price_range=0,
                                       avg_price=20, last_order_no='PO-4',
                                       last_price=20, last_purchase_date='2026-09-05'),
            ('M002', '供应商甲'): dict(purchase_times=2, quantity=10, amount=58,
                                       min_price=5, max_price=9, price_range=4,
                                       avg_price=5.8, last_order_no='PO-5',
                                       last_price=5, last_purchase_date='2026-09-02'),
            ('M002', '供应商乙'): dict(purchase_times=1, quantity=3, amount=21,
                                       min_price=7, max_price=7, price_range=0,
                                       avg_price=7, last_order_no='PO-7',
                                       last_price=7, last_purchase_date='2026-09-04'),
            ('M001', '未指定供应商'): dict(purchase_times=1, quantity=2, amount=6,
                                       min_price=3, max_price=3, price_range=0,
                                       avg_price=3, last_order_no='PO-8',
                                       last_price=3, last_purchase_date='2026-09-05'),
        }

    def test_T1_pagination_semantics(self):
        """5 组；page_size=1 时 5 页各 1 行、互不重叠、total=5。"""
        with app_module.app.app_context():
            seen = []
            for page in (1, 2, 3, 4, 5):
                _, rows, _, total = app_module._sql_paged_purchase_price_analysis_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                assert len(rows) == 1, f"page{page} 应 1 行，实际 {len(rows)}"
                assert total == 5, f"total 应为真实组数 5，实际 {total}"
                seen.append((rows[0]['material_code'], rows[0]['supplier']))
            assert len(set(seen)) == 5, f"分页结果重叠: {seen}"

    def test_T2_summary_decoupled_and_equals_detail_sum(self):
        """汇总与分页解耦，且「各页明细加总 == 汇总」（R2 汇总 = 明细全集）。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_purchase_price_analysis_report(
                _filters(**self.a_kw, page=1, page_size=1))
            _, _, s5, _ = app_module._sql_paged_purchase_price_analysis_report(
                _filters(**self.a_kw, page=5, page_size=1))
            assert s1 == s5, "不同页 summary 必须一致（全集口径）"
            assert s1['count'] == 5, f"组数应为 5，实际 {s1['count']}"
            assert s1['quantity'] == 40, f"数量应为 40，实际 {s1['quantity']}"
            assert s1['amount'] == 409, f"金额应为 409，实际 {s1['amount']}"

            all_rows = []
            for page in (1, 2, 3, 4, 5):
                _, rows, _, _ = app_module._sql_paged_purchase_price_analysis_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                all_rows.extend(rows)
            assert sum(r['quantity'] for r in all_rows) == s1['quantity']
            assert sum(r['amount'] for r in all_rows) == s1['amount']

    def test_T3_default_sort_last_purchase_date_desc(self):
        """默认按最近采购日期倒序：G2/G5(09-05) → G4(09-04) → G1(09-03) → G3(09-02)。

        同日按物料编码/供应商升序稳定兜底（'供应商乙' < '未指定供应商'）。
        """
        with app_module.app.app_context():
            _, rows, _, _ = app_module._sql_paged_purchase_price_analysis_report(
                _filters(**self.a_kw))
            keys = [(r['material_code'], r['supplier']) for r in rows]
            assert keys == [
                ('M001', '供应商乙'),      # G2 09-05
                ('M001', '未指定供应商'),  # G5 09-05
                ('M002', '供应商乙'),      # G4 09-04
                ('M001', '供应商甲'),      # G1 09-03
                ('M002', '供应商甲'),      # G3 09-02
            ], f"默认排序错误: {keys}"

    def test_T4_sort_by_amount_desc(self):
        """按 amount 降序：首行为金额最大的 G1（M001×甲 204）。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_purchase_price_analysis_report(
                _filters(**self.a_kw, sort_field='amount', sort_order='desc'))
            assert total == 5
            amounts = [r['amount'] for r in rows]
            assert amounts[0] == 204, f"降序首行应为 204，实际 {amounts[0]}"
            assert amounts == sorted(amounts, reverse=True), "当页必须按金额降序"

    def test_T5_warehouse_required_and_isolation(self):
        """无仓库返回空；B 仓数据不串入 A 仓（R2）。"""
        with app_module.app.app_context():
            _, rows, summary, total = app_module._sql_paged_purchase_price_analysis_report(
                _filters())
            assert total == 0 and rows == [], "无仓库必须返回空"
            assert summary == {'count': 0, 'quantity': 0, 'amount': 0}

            _, rows_a, summary_a, total_a = app_module._sql_paged_purchase_price_analysis_report(
                _filters(**self.a_kw))
            assert total_a == 5, f"A 仓应 5 组，实际 {total_a}"
            assert summary_a['quantity'] == 40
            assert all(r['quantity'] != 777 for r in rows_a), "B 仓 777 串入 A 仓"

            _, _, summary_b, total_b = app_module._sql_paged_purchase_price_analysis_report(
                _filters(**self.b_kw))
            assert total_b == 1, f"B 仓应 1 组，实际 {total_b}"
            assert summary_b['quantity'] == 777, f"B 仓数量应为 777，实际 {summary_b['quantity']}"

    def test_T6_api_pagination_response(self):
        """API：page=2&page_size=1 → total=5、len(data)=1、total_pages=5、truncated=False。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(
            f"/report/api/purchase_price_analysis?warehouse_id={self.wh_a_id}"
            "&page=2&page_size=1")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 5
        assert len(data['data']) == 1
        assert data['total_pages'] == 5
        assert data['truncated'] is False, "SQL 聚合不应触发明细截断"
        assert data['summary']['amount'] == 409

    def test_T7_sql_path_matches_memory_path(self):
        """SQL 路径与内存路径分桶结果一致（按 物料×供应商 比对，防口径漂移）。

        环境差异同 009-07-013/014：order_url 依赖 url_for，须在请求上下文内；
        按「报表声明列」逐字段归一化比对。
        """
        declared = {c['field'] for c in app_module._purchase_price_analysis_columns()}
        with app_module.app.test_request_context('/report/view/purchase_price_analysis'):
            _, mem_rows, mem_summary = app_module._build_purchase_price_report(
                _filters(**self.a_kw))
            _, sql_rows, sql_summary, sql_total = \
                app_module._sql_paged_purchase_price_analysis_report(
                    _filters(**self.a_kw, export='excel'))

            def _norm(row):
                return {k: v for k, v in row.items() if k in declared}

            mem_by_key = {(r['material_code'], r['supplier']): _norm(r) for r in mem_rows}
            sql_by_key = {(r['material_code'], r['supplier']): _norm(r) for r in sql_rows}
            assert mem_by_key.keys() == sql_by_key.keys(), \
                f"分组集合不一致: 内存 {sorted(mem_by_key)} vs SQL {sorted(sql_by_key)}"
            for key in mem_by_key:
                assert mem_by_key[key] == sql_by_key[key], \
                    f"{key} 分桶内容不一致: 内存 {mem_by_key[key]} vs SQL {sql_by_key[key]}"
            assert sql_total == len(mem_rows)
            assert sql_summary == mem_summary, "汇总口径必须与内存路径一致"

    def test_T8_last_row_uses_min_order_no_on_same_date(self):
        """last_* 复刻含等号覆写语义：同日两单（PO-6@9 > PO-5@5）胜出者为 PO-5。"""
        with app_module.app.app_context():
            exp = self._expect()
            _, rows, _, _ = app_module._sql_paged_purchase_price_analysis_report(
                _filters(**self.a_kw))
            by_key = {(r['material_code'], r['supplier']): r for r in rows}
            g3 = by_key[('M002', '供应商甲')]
            assert g3['last_order_no'] == 'PO-5', \
                f"同日取最小单号 PO-5，实际 {g3['last_order_no']}"
            assert g3['last_price'] == 5.0, f"最近采购价应为 PO-5 的 5，实际 {g3['last_price']}"
            assert g3['last_purchase_date'] == '2026-09-02'
            # 内存路径同样行为，双路一致
            with app_module.app.test_request_context('/report/view/purchase_price_analysis'):
                _, mem_rows, _ = app_module._build_purchase_price_report(_filters(**self.a_kw))
            mem_g3 = {(r['material_code'], r['supplier']): r for r in mem_rows}[('M002', '供应商甲')]
            assert mem_g3['last_order_no'] == 'PO-5', "内存路径语义应一致"
            assert mem_g3['last_price'] == 5.0

            # 其余分组全字段复核
            for key, want in exp.items():
                row = by_key[key]
                for field, value in want.items():
                    assert row[field] == value, \
                        f"{key} 字段 {field} 应为 {value}，实际 {row[field]}"
