# -*- coding: utf-8 -*-
"""BUG-2026-09-07-012 回归：出入库汇总报表 SQL 分页下沉。

背景：出入库汇总报表同时消费「入库明细」与「出库明细」两条明细流，原内存路径
把两侧各物化最多 REPORT_ROW_LIMIT(5 万) 行再在 Python 里按日期分桶——它是所有
报表里最先触达截断的一类；且汇总卡片基于截断后的分桶结果计算，长周期查询时
「顶部合计 ≠ 明细全集」，违反 R2。

本修复把分桶下沉为 SQL GROUP BY（只产出日期桶行），汇总改由 SQL 聚合筛选后
全集并与分页解耦。

断言：
  T1. 分页语义：日期桶分页行数正确、互不重叠，total 为真实日期桶数。
  T2. 汇总与分页解耦 + R2：不同页 summary 相同；且「各页明细加总 == 汇总」。
  T3. 默认排序日期倒序（原内存路径把"仅出库日"追加在所有入库日之后，非全局有序）。
  T4. 排序：按 net_quantity 降序时首行为最大值。
  T5. 仓库必填与多仓隔离（R2）：无仓库返回空；B 仓数据不串入 A 仓。
  T6. API 层：/report/api/summary 分页响应 total/data/total_pages 正确且不截断。
  T7. SQL 路径与内存路径内容一致（按日期比对，防分桶口径漂移）。
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
from app import (Department, InOrder, InOrderItem, Material, OutOrder,  # noqa: E402
                 OutOrderItem, Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

D1 = date(2026, 9, 1)   # 仅入库日
D2 = date(2026, 9, 2)   # 入库 + 出库日
D3 = date(2026, 9, 3)   # 仅出库日（验证默认排序不再被追加到末尾）


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


class TestBug20260907012:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            self.wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            self.wh_b = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
            unit = Unit(code="PCS", name="个")
            dept = Department(code="SC", name="生产部")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([self.wh_a, self.wh_b, unit, dept, user])
            db.session.flush()
            mat = Material(code="M001", name="电缆", unit_id=unit.id, price=10.0, stock=0.0)
            db.session.add(mat)
            db.session.flush()
            self.mat_id = mat.id
            self.user_id = user.id
            self.dept_id = dept.id

            # ==== A 仓入库 ====
            # D1：1 单 2 行 → in: 2 行 / 30 个 / 300 元
            self._add_in("IN-D1", D1, "仓库A", [10, 20])
            # D2：1 单 1 行 → in: 1 行 / 5 个 / 50 元
            self._add_in("IN-D2", D2, "仓库A", [5])

            # ==== A 仓出库 ====
            # D2：1 单 1 行 → out: 1 行 / 3 个 / 30 元
            self._add_out("OUT-D2", D2, "仓库A", [3])
            # D3：1 单 1 行（仅出库日）→ out: 1 行 / 7 个 / 70 元
            self._add_out("OUT-D3", D3, "仓库A", [7])

            # ==== B 仓（R2 隔离验证）====
            self._add_in("IN-B0", D1, "仓库B", [999])

            db.session.commit()
            self.wh_a_id = self.wh_a.id
            self.wh_b_id = self.wh_b.id
            # 函数层直调需三件套齐传（仓库过滤按名称/编号任一匹配）
            self.a_kw = dict(warehouse_id=self.wh_a_id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=self.wh_b_id, warehouse="仓库B", warehouse_code="WHB")

    def _add_in(self, order_no, day, warehouse, quantities):
        order = InOrder(order_no=order_no, date=day, warehouse=warehouse,
                        status="completed", operator_id=self.user_id,
                        business_type="采购入库")
        db.session.add(order)
        db.session.flush()
        for qty in quantities:
            db.session.add(InOrderItem(
                in_order_id=order.id, material_id=self.mat_id,
                quantity=qty, price=10.0, amount=qty * 10.0))

    def _add_out(self, order_no, day, warehouse, quantities):
        order = OutOrder(order_no=order_no, date=day, warehouse=warehouse,
                         status="completed", operator_id=self.user_id,
                         department_id=self.dept_id)
        db.session.add(order)
        db.session.flush()
        for qty in quantities:
            db.session.add(OutOrderItem(
                out_order_id=order.id, material_id=self.mat_id,
                quantity=qty, price=10.0, amount=qty * 10.0))

    # 期望口径（A 仓）：
    #   D1: in 2/30/300  out 0/0/0    net  30/300
    #   D2: in 1/5/50    out 1/3/30   net   2/20
    #   D3: in 0/0/0     out 1/7/70   net  -7/-70
    #   summary: count(日期数)=3, quantity=(30+5)+(3+7)=45, amount=(300+50)+(30+70)=450
    def test_T1_pagination_semantics(self):
        """3 个日期桶；page_size=1 时三页各 1 行、互不重叠、total=3。"""
        with app_module.app.app_context():
            seen = []
            for page in (1, 2, 3):
                _, rows, _, total = app_module._sql_paged_summary_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                assert len(rows) == 1, f"page{page} 应 1 行，实际 {len(rows)}"
                assert total == 3, f"total 应为真实日期桶数 3，实际 {total}"
                seen.append(rows[0]['date'])
            assert len(set(seen)) == 3, f"分页结果重叠: {seen}"

    def test_T2_summary_decoupled_and_equals_detail_sum(self):
        """汇总与分页解耦，且「各页明细加总 == 汇总」（R2 汇总 = 明细全集）。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_summary_report(
                _filters(**self.a_kw, page=1, page_size=1))
            _, _, s3, _ = app_module._sql_paged_summary_report(
                _filters(**self.a_kw, page=3, page_size=1))
            assert s1 == s3, "不同页 summary 必须一致（全集口径）"
            assert s1['count'] == 3, f"日期数应为 3，实际 {s1['count']}"
            assert s1['quantity'] == 45, f"出入库数量应为 45，实际 {s1['quantity']}"
            assert s1['amount'] == 450, f"出入库金额应为 450，实际 {s1['amount']}"

            # 翻完全部页，各日 in/out 加总必须等于汇总（不再按截断数据统计）
            all_rows = []
            for page in (1, 2, 3):
                _, rows, _, _ = app_module._sql_paged_summary_report(
                    _filters(**self.a_kw, page=page, page_size=1))
                all_rows.extend(rows)
            assert len(all_rows) == 3
            qty_sum = sum(r['in_quantity'] + r['out_quantity'] for r in all_rows)
            amt_sum = sum(r['in_amount'] + r['out_amount'] for r in all_rows)
            assert qty_sum == s1['quantity'], f"明细加总 {qty_sum} != 汇总 {s1['quantity']}"
            assert amt_sum == s1['amount'], f"明细加总 {amt_sum} != 汇总 {s1['amount']}"

    def test_T3_default_sort_date_desc(self):
        """默认按日期倒序；「仅出库日 D3」不再被追加到所有入库日之后。"""
        with app_module.app.app_context():
            _, rows, _, _ = app_module._sql_paged_summary_report(_filters(**self.a_kw))
            dates = [r['date'] for r in rows]
            assert dates == [D3.isoformat(), D2.isoformat(), D1.isoformat()], \
                f"默认应为日期倒序，实际 {dates}"

    def test_T4_sort_by_net_quantity_desc(self):
        """按 net_quantity 降序：首行为最大值 30（D1）。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_summary_report(
                _filters(**self.a_kw, sort_field='net_quantity', sort_order='desc'))
            assert total == 3
            nets = [r['net_quantity'] for r in rows]
            assert nets[0] == 30, f"降序首行净变动应为 30，实际 {nets[0]}"
            assert nets == sorted(nets, reverse=True), "当页必须按净变动数量降序"

    def test_T5_warehouse_required_and_isolation(self):
        """无仓库返回空；B 仓数据不串入 A 仓（R2）。"""
        with app_module.app.app_context():
            _, rows, summary, total = app_module._sql_paged_summary_report(_filters())
            assert total == 0 and rows == [], "无仓库必须返回空"
            assert summary == {'count': 0, 'quantity': 0, 'amount': 0}

            _, rows_a, summary_a, total_a = app_module._sql_paged_summary_report(
                _filters(**self.a_kw))
            assert total_a == 3, f"A 仓应 3 个日期桶，实际 {total_a}"
            assert summary_a['quantity'] == 45
            # B 仓的 999 不得串入 A 仓
            assert all(r['in_quantity'] != 999 for r in rows_a)

            _, _, summary_b, total_b = app_module._sql_paged_summary_report(
                _filters(**self.b_kw))
            assert total_b == 1, f"B 仓应 1 个日期桶，实际 {total_b}"
            assert summary_b['quantity'] == 999, f"B 仓数量应为 999，实际 {summary_b['quantity']}"

    def test_T6_api_pagination_response(self):
        """API：page=2&page_size=1 → total=3、len(data)=1、total_pages=3、truncated=False。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(f"/report/api/summary?warehouse_id={self.wh_a_id}&page=2&page_size=1")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 3
        assert len(data['data']) == 1
        assert data['total_pages'] == 3
        assert data['truncated'] is False, "日期桶聚合不应触发明细截断"
        assert data['summary']['quantity'] == 45

    def test_T7_sql_path_matches_memory_path(self):
        """SQL 路径与内存路径分桶结果一致（按日期比对，防口径漂移）。"""
        with app_module.app.app_context():
            _, mem_rows, mem_summary = app_module._build_summary_report(
                _filters(**self.a_kw))
            _, sql_rows, sql_summary, sql_total = app_module._sql_paged_summary_report(
                _filters(**self.a_kw, export='excel'))

            mem_by_date = {r['date']: r for r in mem_rows}
            sql_by_date = {r['date']: r for r in sql_rows}
            assert mem_by_date.keys() == sql_by_date.keys(), \
                f"日期桶集合不一致: 内存 {sorted(mem_by_date)} vs SQL {sorted(sql_by_date)}"
            for day in mem_by_date:
                assert mem_by_date[day] == sql_by_date[day], f"{day} 分桶内容不一致"
            assert sql_total == len(mem_rows)
            assert sql_summary == mem_summary, "汇总口径必须与内存路径一致"
