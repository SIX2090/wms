# -*- coding: utf-8 -*-
"""BUG-2026-09-07-018 回归：委外加工报表 SQL 分页下沉。

背景：委外报表行集 = 委外单，无 REPORT_ROW_LIMIT 截断（无 R2 失真），但原内存
路径每次查询/翻页都把委外单连同 需求明细 + 发料单及其明细 + 收货单及其明细
**全部物化**再逐单 Python 匹配求和——实测（8000 单 / 40000 明细行，内存 SQLite）
单次查询 2.52s / 81 条 SQL，翻 3 页 7.24s。发料/收货两套子表使其比领料报表更重。

SQL 路径：发料/收货明细分别先按委外单分组聚合（命中子查询，物料关键词时仅命中
行参与）；主查询 LEFT JOIN 两个聚合 + 加工厂商，WHERE/排序/LIMIT 下沉 SQL；
汇总由 SQL 对筛选后全集聚合、与分页解耦；关键词时「任一表（需求/发料/收货）
命中即保留委外单」，各列只累计各自命中行。

断言：
  T1. 默认排序日期倒序，分页互不重叠、total 真实。
  T2. 汇总与分页解耦 + R2：quantity=发料总和、amount=收货总和（与内存 summary
      口径一致）；「各页明细加总 == 汇总」。
  T3. 无发料/收货的委外单仍出现（数量 0）。
  T4. 物料关键词：SC-1 只累计命中行（发 4/收 2），无命中单被排除。
  T5. 仓库必填与多仓隔离：无仓库返回空；B 仓 777 不串入 A 仓。
  T6. API 层：/report/api/subcontract 分页元数据正确。
  T7. 双路径结果一致（按 order_no 比对，含关键词路径，防口径漂移）。
  T8. 表头排序（收货数量 receive_qty 降序）首行为最大值。
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
from app import (Material, SubcontractIssue, SubcontractIssueItem,  # noqa: E402
                 SubcontractItem, SubcontractOrder, SubcontractReceive,
                 SubcontractReceiveItem, Supplier, Unit, User, Warehouse, db)

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


class TestBug20260907018:
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
            sup = Supplier(code="S1", name="加工厂")
            db.session.add_all([wh_a, wh_b, unit, user, sup])
            db.session.flush()
            m1 = Material(code="M001", name="电缆", spec="2.5mm",
                          unit_id=unit.id, price=10.0, stock=0.0)
            m2 = Material(code="M002", name="开关", spec="16A",
                          unit_id=unit.id, price=20.0, stock=0.0)
            db.session.add_all([m1, m2])
            db.session.flush()
            self.user_id, self.sup_id = user.id, sup.id
            self.wh_a_id, self.wh_b_id = wh_a.id, wh_b.id
            self.m1_id, self.m2_id = m1.id, m2.id
            self.unit_id = unit.id
            self.a_kw = dict(warehouse_id=wh_a.id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=wh_b.id, warehouse="仓库B", warehouse_code="WHB")

            # SC-1（09-01）：需求 M001；发料 M001×4+M002×3；收货 M001×2+M002×1
            sc1 = self._add_sc("SC-1", D1, "仓库A", "active", [(m1.id, 10.0)], None)
            self._add_issue(sc1.id, "SI-1", [(m1.id, 4.0), (m2.id, 3.0)])
            self._add_receive(sc1.id, "SR-1", [(m1.id, 2.0), (m2.id, 1.0)])
            # SC-3（09-02）：仅收货 M001×6
            sc3 = self._add_sc("SC-3", D2, "仓库A", "active", [(m2.id, 8.0)], None)
            self._add_receive(sc3.id, "SR-3", [(m1.id, 6.0)])
            # SC-2（09-03）：无发料/收货（创建晚于 SC-3，验证无子单保留）
            self._add_sc("SC-2", D3, "仓库A", "active", [(m2.id, 5.0)], "委外备注")
            # B 仓隔离
            sc_b = self._add_sc("SC-B", D1, "仓库B", "active", [(m1.id, 777.0)], None)
            self._add_issue(sc_b.id, "SI-B", [(m1.id, 777.0)])

            db.session.commit()

    def _add_sc(self, order_no, day, warehouse_name, status, demand_items, remark):
        sc = SubcontractOrder(order_no=order_no, date=day, supplier_id=self.sup_id,
                              operator_id=self.user_id, status=status,
                              warehouse=warehouse_name, remark=remark, total_amount=0.0)
        db.session.add(sc)
        db.session.flush()
        for material_id, qty in demand_items:
            db.session.add(SubcontractItem(
                subcontract_order_id=sc.id, material_id=material_id, quantity=qty,
                returned_quantity=0.0, loss=0.0, unit_id=self.unit_id))
        return sc

    def _add_issue(self, sc_id, issue_no, items):
        iss = SubcontractIssue(issue_no=issue_no, date=D1, subcontract_order_id=sc_id,
                               supplier_id=self.sup_id, operator_id=self.user_id,
                               status="completed", warehouse="仓库A", remark=None)
        db.session.add(iss)
        db.session.flush()
        for material_id, qty in items:
            db.session.add(SubcontractIssueItem(
                issue_id=iss.id, material_id=material_id, quantity=qty,
                unit_id=self.unit_id, remark=None))

    def _add_receive(self, sc_id, receive_no, items):
        rec = SubcontractReceive(receive_no=receive_no, date=D2,
                                 subcontract_order_id=sc_id, supplier_id=self.sup_id,
                                 operator_id=self.user_id, status="completed",
                                 warehouse="仓库A", total_quantity=0.0)
        db.session.add(rec)
        db.session.flush()
        for material_id, qty in items:
            db.session.add(SubcontractReceiveItem(
                receive_id=rec.id, material_id=material_id, quantity=qty,
                scrap_quantity=0.0, unit_id=self.unit_id, price=0.0, amount=0.0,
                remark=None))

    def test_T1_default_sort_and_pagination(self):
        """默认日期倒序：SC-2(09-03) → SC-3(09-02) → SC-1(09-01)。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, page_size=10))
            assert total == 3
            assert [r['order_no'] for r in rows] == ['SC-2', 'SC-3', 'SC-1']

            p1 = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, page=1, page_size=2))[1]
            p2 = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, page=2, page_size=2))[1]
            seen = [r['order_no'] for r in p1] + [r['order_no'] for r in p2]
            assert len(set(seen)) == 3, f"分页重叠/漏行: {seen}"

    def test_T2_summary_decoupled_and_equals_detail_sum(self):
        """汇总与分页解耦：quantity=发料总和 7、amount=收货总和 9。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, page=1, page_size=2))
            _, _, s2, _ = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, page=2, page_size=2))
            assert s1 == s2
            assert s1['count'] == 3, f"委外单数应为 3，实际 {s1['count']}"
            assert s1['quantity'] == 7, f"发料总和应为 7，实际 {s1['quantity']}"
            assert s1['amount'] == 9, f"收货总和应为 9，实际 {s1['amount']}"

            all_rows = []
            for page in (1, 2):
                _, rows, _, _ = app_module._sql_paged_subcontract_report(
                    _filters(**self.a_kw, page=page, page_size=2))
                all_rows.extend(rows)
            assert sum(r['issue_qty'] for r in all_rows) == s1['quantity']
            assert sum(r['receive_qty'] for r in all_rows) == s1['amount']

    def test_T3_no_doc_order_appears_with_zero(self):
        """无发料/收货的 SC-2 仍出现，数量 0。"""
        with app_module.app.app_context():
            _, rows, _, _ = app_module._sql_paged_subcontract_report(_filters(**self.a_kw))
            sc2 = {r['order_no']: r for r in rows}['SC-2']
            assert sc2['issue_qty'] == 0.0 and sc2['receive_qty'] == 0.0
            assert sc2['remark'] == '委外备注'

    def test_T4_material_keyword_filters_and_narrows(self):
        """物料关键词：SC-1 只累计命中行（发 4/收 2）；SC-2 被排除。"""
        with app_module.app.app_context():
            _, rows, summary, total = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, material_code='M001'))
            by_no = {r['order_no']: r for r in rows}
            assert total == 2, f"命中单应为 SC-1/SC-3 共 2 张，实际 {total}"
            assert by_no['SC-1']['issue_qty'] == 4.0, \
                f"SC-1 发料只算 M001 应为 4，实际 {by_no['SC-1']['issue_qty']}"
            assert by_no['SC-1']['receive_qty'] == 2.0
            assert by_no['SC-3']['receive_qty'] == 6.0
            assert summary['count'] == 2 and summary['quantity'] == 4.0
            assert summary['amount'] == 8.0

            _, rows_none, sum_none, total_none = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, material_code='NOTEXIST'))
            assert total_none == 0 and rows_none == []
            assert sum_none == {'count': 0, 'quantity': 0, 'amount': 0}

    def test_T5_warehouse_required_and_isolation(self):
        """无仓库返回空；B 仓数据不串入 A 仓（R2）。"""
        with app_module.app.app_context():
            _, rows, summary, total = app_module._sql_paged_subcontract_report(_filters())
            assert total == 0 and rows == []
            assert summary == {'count': 0, 'quantity': 0, 'amount': 0}

            _, rows_a, summary_a, total_a = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw))
            assert total_a == 3 and summary_a['quantity'] == 7
            assert all(r['issue_qty'] != 777 for r in rows_a), "B 仓 777 串入 A 仓"

            _, _, summary_b, total_b = app_module._sql_paged_subcontract_report(
                _filters(**self.b_kw))
            assert total_b == 1 and summary_b['quantity'] == 777

    def test_T6_api_pagination_response(self):
        """API：page=2&page_size=2 → total=3、len(data)=1、total_pages=2。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(
            f"/report/api/subcontract?warehouse_id={self.wh_a_id}&page=2&page_size=2")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 3
        assert len(data['data']) == 1
        assert data['total_pages'] == 2
        assert data['summary']['amount'] == 9

    def test_T7_sql_path_matches_memory_path(self):
        """SQL 路径与内存路径结果一致（按 order_no 比对，含关键词路径）。"""
        declared = {c['field'] for c in app_module._subcontract_columns()}
        with app_module.app.test_request_context('/report/view/subcontract'):
            _, mem_rows, mem_summary = app_module._build_subcontract_report(
                _filters(**self.a_kw))
            _, sql_rows, sql_summary, sql_total = \
                app_module._sql_paged_subcontract_report(
                    _filters(**self.a_kw, export='excel'))

            def _norm(row):
                return {k: v for k, v in row.items() if k in declared}

            m = {r['order_no']: _norm(r) for r in mem_rows}
            s = {r['order_no']: _norm(r) for r in sql_rows}
            assert m.keys() == s.keys()
            for no in m:
                assert m[no] == s[no], f"{no} 不一致: 内存 {m[no]} vs SQL {s[no]}"
            assert sql_total == len(mem_rows)
            assert sql_summary == mem_summary

            _, mem_kw, mem_sum_kw = app_module._build_subcontract_report(
                _filters(**self.a_kw, material_code='M001'))
            _, sql_kw, sql_sum_kw, sql_tot_kw = \
                app_module._sql_paged_subcontract_report(
                    _filters(**self.a_kw, material_code='M001', export='excel'))
            mk = {r['order_no']: _norm(r) for r in mem_kw}
            sk = {r['order_no']: _norm(r) for r in sql_kw}
            assert mk.keys() == sk.keys()
            for no in mk:
                assert mk[no] == sk[no], f"[kw] {no} 不一致: 内存 {mk[no]} vs SQL {sk[no]}"
            assert sql_tot_kw == len(mem_kw)
            assert sql_sum_kw == mem_sum_kw

    def test_T8_header_sort_by_receive_qty_desc(self):
        """表头排序（receive_qty 降序）回退全量排序：首行为 SC-3(6)。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_subcontract_report(
                _filters(**self.a_kw, sort_field='receive_qty', sort_order='desc'))
            assert total == 3
            values = [r['receive_qty'] for r in rows]
            assert values[0] == 6.0, f"降序首行应为 6，实际 {values[0]}"
            assert values == sorted(values, reverse=True)
