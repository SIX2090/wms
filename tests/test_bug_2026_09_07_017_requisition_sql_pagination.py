# -*- coding: utf-8 -*-
"""BUG-2026-09-07-017 回归：工单领料报表 SQL 分页下沉。

背景：领料报表行集 = 领料单，无 REPORT_ROW_LIMIT 截断（无 R2 失真），但原内存
路径每次查询/翻页都全量物化领料单 + selectinload 全部明细行再逐单 Python 求和
（实测 15000 单 / 30000 明细 → 单次查询 1.85s / 31 条 SQL，翻 3 页 4.99s，
单页均摊 1.66s）——翻一页重算一遍全量，页越大越卡。

SQL 路径：明细行先按领料单分组聚合（命中子查询，物料关键词时仅命中行参与，
与内存 matched_items 口径一致）；主查询把 WHERE/排序/LIMIT 全部下沉 SQL，
默认路径只取当页；汇总由 SQL 对筛选后全集聚合、与分页解耦；表头排序回退
「全量取回 + Python 排序 + 切片」（行数=领料单数，无明细 ORM 加载，语义一致）。

断言：
  T1. 默认排序：日期倒序（同日按 ID 倒序确定兜底），分页互不重叠 total 真实。
  T2. 汇总与分页解耦 + R2：不同页 summary 相同；「各页明细加总 == 汇总」。
  T3. 无明细领料单仍出现（数量 0）且计入单数（与内存路径一致）。
  T4. 物料关键词：只算命中物料行；无命中单被排除。
  T5. 仓库必填与多仓隔离：无仓库返回空；B 仓 777 不串入 A 仓。
  T6. API 层：/report/api/requisition 分页元数据正确。
  T7. 双路径分桶结果一致（按 req_no 比对，防口径漂移）。
  T8. 表头排序（amount 降序）首行为最大值。
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
from app import (BOM, Material, ProductionRequisition, ProductionRequisitionItem,  # noqa: E402
                 Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

D1 = date(2026, 9, 1)
D2 = date(2026, 9, 2)
D3 = date(2026, 9, 3)


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


class TestBug20260907017:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            wh_b = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([wh_a, wh_b, unit, user])
            db.session.flush()
            m1 = Material(code="M001", name="电缆", spec="2.5mm",
                          unit_id=unit.id, price=10.0, stock=0.0)
            m2 = Material(code="M002", name="开关", spec="16A",
                          unit_id=unit.id, price=20.0, stock=0.0)
            bom = BOM(bom_no="BOM-1", product_code="P001", product_name="成品1")
            db.session.add_all([m1, m2, bom])
            db.session.flush()
            self.user_id = user.id
            self.wh_a_id, self.wh_b_id = wh_a.id, wh_b.id
            self.m1_id, self.m2_id = m1.id, m2.id
            self.bom_id = bom.id
            self.a_kw = dict(warehouse_id=wh_a.id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=wh_b.id, warehouse="仓库B", warehouse_code="WHB")

            # ==== 仓库 A ====
            # R1（09-01，BOM-1）：M001×10(100) + M002×5(100) → 数15/额200
            self._add_req("REQ-1", D1, "completed", "仓库A", self.user_id,
                          self.bom_id, [(m1.id, 10.0), (m2.id, 5.0)], "领料备注")
            # R2（09-03，无 BOM/无操作人）：M001×2 → 数2/额20
            self._add_req("REQ-2", D3, "pending", "仓库A", None, None,
                          [(m1.id, 2.0)], None)
            # R3（09-02，无明细）：数0/额0，必须仍出现
            self._add_req("REQ-3", D2, "completed", "仓库A", self.user_id, None, [], None)
            # R4（09-02，晚于 R3 创建 → ID 更大）：M002×7 → 数7/额140
            self._add_req("REQ-4", D2, "completed", "仓库A", self.user_id, None,
                          [(m2.id, 7.0)], None)

            # ==== 仓库 B（R2 隔离）====
            self._add_req("REQ-B", D3, "completed", "仓库B", self.user_id, None,
                          [(m1.id, 777.0)], None)

            db.session.commit()

    def _add_req(self, req_no, day, status, warehouse_name, operator_id, bom_id,
                 items, remark):
        req = ProductionRequisition(req_no=req_no, date=day, status=status,
                                    warehouse=warehouse_name, operator_id=operator_id,
                                    bom_id=bom_id, remark=remark)
        db.session.add(req)
        db.session.flush()
        for material_id, qty in items:
            db.session.add(ProductionRequisitionItem(
                requisition_id=req.id, material_id=material_id, quantity=qty))

    def test_T1_default_sort_and_pagination(self):
        """默认日期倒序：REQ-2(09-03) → REQ-4/REQ-3(09-02, ID 倒序) → REQ-1(09-01)。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw, page_size=10))
            assert total == 4
            reqs = [r['req_no'] for r in rows]
            assert reqs == ['REQ-2', 'REQ-4', 'REQ-3', 'REQ-1'], f"默认排序错误: {reqs}"

            # 分页：page_size=2 → 两页互不重叠
            p1 = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw, page=1, page_size=2))[1]
            p2 = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw, page=2, page_size=2))[1]
            seen = [r['req_no'] for r in p1] + [r['req_no'] for r in p2]
            assert len(set(seen)) == 4, f"分页重叠/漏行: {seen}"

    def test_T2_summary_decoupled_and_equals_detail_sum(self):
        """汇总与分页解耦：不同页 summary 相同；各页明细加总 == 汇总。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw, page=1, page_size=2))
            _, _, s2, _ = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw, page=2, page_size=2))
            assert s1 == s2, "不同页 summary 必须一致（全集口径）"
            assert s1['count'] == 4, f"领料单数应为 4，实际 {s1['count']}"
            assert s1['quantity'] == 24, f"数量应为 24，实际 {s1['quantity']}"
            assert s1['amount'] == 360, f"金额应为 360，实际 {s1['amount']}"

            all_rows = []
            for page in (1, 2):
                _, rows, _, _ = app_module._sql_paged_requisition_report(
                    _filters(**self.a_kw, page=page, page_size=2))
                all_rows.extend(rows)
            assert sum(r['quantity'] for r in all_rows) == s1['quantity']
            assert sum(r['amount'] for r in all_rows) == s1['amount']

    def test_T3_empty_requisition_appears_with_zero(self):
        """无明细领料单（REQ-3）仍出现、数量 0、计入单数。"""
        with app_module.app.app_context():
            _, rows, _, _ = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw))
            r3 = {r['req_no']: r for r in rows}['REQ-3']
            assert r3['quantity'] == 0.0 and r3['amount'] == 0

    def test_T4_material_keyword_filters_and_narrows(self):
        """物料关键词：只算命中行；无命中单被排除；REQ-1 只计 M001 的 10。"""
        with app_module.app.app_context():
            kw = dict(self.a_kw, material_code='M001')
            _, rows, summary, total = app_module._sql_paged_requisition_report(_filters(**kw))
            by_req = {r['req_no']: r for r in rows}
            assert total == 2, f"命中单应为 REQ-1/REQ-2 共 2 张，实际 {total}"
            assert by_req['REQ-1']['quantity'] == 10.0, \
                f"REQ-1 只算 M001 行应为 10，实际 {by_req['REQ-1']['quantity']}"
            assert by_req['REQ-1']['amount'] == 100.0
            assert by_req['REQ-2']['quantity'] == 2.0
            assert summary['count'] == 2 and summary['quantity'] == 12
            assert summary['amount'] == 120.0

            _, rows_none, summary_none, total_none = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw, material_code='NOTEXIST'))
            assert total_none == 0 and rows_none == []
            assert summary_none == {'count': 0, 'quantity': 0, 'amount': 0}

    def test_T5_warehouse_required_and_isolation(self):
        """无仓库返回空；B 仓数据不串入 A 仓（R2）。"""
        with app_module.app.app_context():
            _, rows, summary, total = app_module._sql_paged_requisition_report(_filters())
            assert total == 0 and rows == []
            assert summary == {'count': 0, 'quantity': 0, 'amount': 0}

            _, rows_a, summary_a, total_a = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw))
            assert total_a == 4 and summary_a['quantity'] == 24
            assert all(r['quantity'] != 777 for r in rows_a), "B 仓 777 串入 A 仓"

            _, _, summary_b, total_b = app_module._sql_paged_requisition_report(
                _filters(**self.b_kw))
            assert total_b == 1 and summary_b['quantity'] == 777

    def test_T6_api_pagination_response(self):
        """API：page=2&page_size=2 → total=4、len(data)=2、total_pages=2。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(
            f"/report/api/requisition?warehouse_id={self.wh_a_id}&page=2&page_size=2")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 4
        assert len(data['data']) == 2
        assert data['total_pages'] == 2
        assert data['summary']['amount'] == 360

    def test_T7_sql_path_matches_memory_path(self):
        """SQL 路径与内存路径结果一致（按 req_no 比对，防口径漂移）。

        order_url 依赖 url_for，须在请求上下文内比对；按报表声明列归一化。
        """
        declared = {c['field'] for c in app_module._requisition_columns()}
        with app_module.app.test_request_context('/report/view/requisition'):
            _, mem_rows, mem_summary = app_module._build_requisition_report(
                _filters(**self.a_kw))
            _, sql_rows, sql_summary, sql_total = \
                app_module._sql_paged_requisition_report(
                    _filters(**self.a_kw, export='excel'))

            def _norm(row):
                return {k: v for k, v in row.items() if k in declared}

            mem_by = {r['req_no']: _norm(r) for r in mem_rows}
            sql_by = {r['req_no']: _norm(r) for r in sql_rows}
            assert mem_by.keys() == sql_by.keys()
            for req_no in mem_by:
                assert mem_by[req_no] == sql_by[req_no], \
                    f"{req_no} 不一致: 内存 {mem_by[req_no]} vs SQL {sql_by[req_no]}"
            assert sql_total == len(mem_rows)
            assert sql_summary == mem_summary

            # 关键词路径同样一致
            _, mem_kw, mem_sum_kw = app_module._build_requisition_report(
                _filters(**self.a_kw, material_code='M001'))
            _, sql_kw, sql_sum_kw, sql_tot_kw = \
                app_module._sql_paged_requisition_report(
                    _filters(**self.a_kw, material_code='M001', export='excel'))
            m = {r['req_no']: _norm(r) for r in mem_kw}
            s = {r['req_no']: _norm(r) for r in sql_kw}
            assert m.keys() == s.keys()
            for req_no in m:
                assert m[req_no] == s[req_no], f"[kw] {req_no} 不一致"
            assert sql_tot_kw == len(mem_kw)
            assert sql_sum_kw == mem_sum_kw

    def test_T8_header_sort_by_amount_desc(self):
        """表头排序（amount 降序）回退全量排序：首行为 REQ-1(200)。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_requisition_report(
                _filters(**self.a_kw, sort_field='amount', sort_order='desc'))
            assert total == 4
            amounts = [r['amount'] for r in rows]
            assert amounts[0] == 200, f"降序首行应为 200，实际 {amounts[0]}"
            assert amounts == sorted(amounts, reverse=True)
            assert [r['req_no'] for r in rows] == ['REQ-1', 'REQ-4', 'REQ-2', 'REQ-3']
