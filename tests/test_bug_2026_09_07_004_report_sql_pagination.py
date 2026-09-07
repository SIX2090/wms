# -*- coding: utf-8 -*-
"""BUG-2026-09-07-004 回归：入库/出库明细报表 SQL 分页下沉。

背景：原路径每次查询/翻页/排序都全量物化（最多 5 万行）再内存切片，
翻一次页重算一次全量；汇总卡片与列表共享同一份截断数据，超限时失真。
本修复把 count/聚合/排序/分页下沉到 SQL：翻页只取当页、汇总基于筛选后
全集（R2 汇总=明细）、total 为真实总数。

断言：
  T1. 分页语义：page1/2/3 行数正确、互不重叠，total 为 SQL 真实总数。
  T2. 汇总与分页解耦：不同页的 summary 相同且等于全集聚合。
  T3. 排序下沉：按 quantity 降序时第一页首行为最大值，且 total 不变。
  T4. 出库客户/部门筛选下沉后三通道命中（部门名/客户文本/用途）。
  T5. 仓库必填与多仓隔离（R2）：无仓库返回空；B 仓数据不串入 A 仓。
  T6. API 层：/report/api/in_detail 分页响应 total/data 正确。
  T7. SQL 路径与内存路径同序同内容（防行映射漂移）。
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


class TestBug20260907004:
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
            self.dept_id = dept.id
            mat = Material(code="M001", name="电缆", unit_id=unit.id, price=10.0, stock=0.0)
            db.session.add(mat)
            db.session.flush()
            self.mat_id = mat.id
            # A 仓：13 张入库单 × 2 行 = 26 行，数量从 1 递增便于排序断言
            qty = 1
            for idx in range(13):
                order = InOrder(order_no=f"IN-{idx:02d}", date=date.today(),
                                warehouse="仓库A", status="completed",
                                operator_id=user.id, business_type="采购入库")
                db.session.add(order)
                db.session.flush()
                for _ in range(2):
                    db.session.add(InOrderItem(
                        in_order_id=order.id, material_id=mat.id,
                        quantity=qty, price=10.0, amount=qty * 10.0))
                    qty += 1
            # B 仓：1 张入库单 × 2 行（R2 隔离验证）
            order_b = InOrder(order_no="IN-B0", date=date.today(),
                              warehouse="仓库B", status="completed",
                              operator_id=user.id, business_type="采购入库")
            db.session.add(order_b)
            db.session.flush()
            for _ in range(2):
                db.session.add(InOrderItem(
                    in_order_id=order_b.id, material_id=mat.id,
                    quantity=100, price=10.0, amount=1000.0))
            # A 仓出库三通道：部门名 / 客户文本 / 用途 各一张
            cases = [
                ("OUT-DEPT", dept.id, None, None),          # 部门名命中
                ("OUT-CUST", None, "某某客户公司", None),     # 客户文本命中
                ("OUT-PURP", None, None, "设备维修用料"),     # 用途命中
            ]
            for no, dept_id, cust, purp in cases:
                oo = OutOrder(order_no=no, date=date.today(), warehouse="仓库A",
                              status="completed", operator_id=user.id,
                              department_id=dept_id, customer=cust, purpose=purp)
                db.session.add(oo)
                db.session.flush()
                db.session.add(OutOrderItem(
                    out_order_id=oo.id, material_id=mat.id,
                    quantity=2, price=10.0, amount=20.0))
            db.session.commit()
            self.wh_a_id = self.wh_a.id
            self.wh_b_id = self.wh_b.id
            # 真实链路 _build_report_filters 会从 warehouse_id 解析出名称/编号，
            # 函数层直调时必须三件套一起传（仓库过滤按名称/编号任一匹配）
            self.a_kw = dict(warehouse_id=self.wh_a_id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=self.wh_b_id, warehouse="仓库B", warehouse_code="WHB")

    def test_T1_pagination_semantics(self):
        """page1/2/3 = 10/10/6 行、互不重叠、total=26。"""
        with app_module.app.app_context():
            seen = []
            for page, expect in ((1, 10), (2, 10), (3, 6)):
                cols, rows, summary, total = app_module._sql_paged_in_detail_report(
                    _filters(**self.a_kw, page=page, page_size=10))
                assert len(rows) == expect, f"page{page} 应 {expect} 行，实际 {len(rows)}"
                assert total == 26, f"total 应为真实总数 26，实际 {total}"
                seen.extend(r['order_url'] + str(r['quantity']) + str(r['amount']) for r in rows)
            assert len(seen) == len(set(seen)), "分页之间不得重叠"
            payload = app_module._build_report_payload(
                'in_detail', _filters(**self.a_kw, page=1, page_size=10))
            assert payload['total_pages'] == 3, f"26 行/10 → 3 页，实际 {payload['total_pages']}"

    def test_T2_summary_decoupled_from_pagination(self):
        """汇总基于筛选后全集，与页码无关。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_in_detail_report(
                _filters(**self.a_kw, page=1, page_size=10))
            _, _, s3, _ = app_module._sql_paged_in_detail_report(
                _filters(**self.a_kw, page=3, page_size=10))
            assert s1 == s3, "不同页 summary 必须一致（全集口径）"
            assert s1['count'] == 26
            assert s1['quantity'] == sum(range(1, 27)), f"数量全集求和错误: {s1['quantity']}"
            assert s1['amount'] == sum(range(1, 27)) * 10.0

    def test_T3_sort_in_sql(self):
        """按 quantity 降序：首页首行 quantity=26；total 不受排序影响。"""
        with app_module.app.app_context():
            cols, rows, summary, total = app_module._sql_paged_in_detail_report(
                _filters(**self.a_kw, page=1, page_size=10,
                         sort_field='quantity', sort_order='desc'))
            assert total == 26
            quantities = [r['quantity'] for r in rows]
            assert quantities[0] == 26.0, f"降序首行应为最大数量 26，实际 {quantities[0]}"
            assert quantities == sorted(quantities, reverse=True), "当页必须按数量降序"

    def test_T4_out_detail_customer_three_channels(self):
        """出库客户筛选下沉：部门名/客户文本/用途三通道均可命中。"""
        with app_module.app.app_context():
            for keyword, expect_no in (("生产部", "OUT-DEPT"),
                                       ("某某客户", "OUT-CUST"),
                                       ("维修用料", "OUT-PURP")):
                cols, rows, summary, total = app_module._sql_paged_out_detail_report(
                    _filters(**self.a_kw, customer=keyword))
                assert total == 1, f"关键词 {keyword} 应命中 1 行，实际 {total}"
                assert rows[0]['order_no'] == expect_no

    def test_T5_warehouse_required_and_isolation(self):
        """无仓库返回空；B 仓数据不串入 A 仓（R2）。"""
        with app_module.app.app_context():
            cols, rows, summary, total = app_module._sql_paged_in_detail_report(_filters())
            assert total == 0 and rows == [], "无仓库必须返回空"
            _, rows_a, _, total_a = app_module._sql_paged_in_detail_report(
                _filters(**self.a_kw))
            assert total_a == 26 and all('IN-B0' != r['order_no'] for r in rows_a)
            _, _, _, total_b = app_module._sql_paged_in_detail_report(
                _filters(**self.b_kw))
            assert total_b == 2, f"B 仓应只有 2 行，实际 {total_b}"

    def test_T6_api_pagination_response(self):
        """API：page=2&page_size=10 → len(data)=10、total=26、total_pages=3。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(f"/report/api/in_detail?warehouse_id={self.wh_a_id}&page=2&page_size=10")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 26
        assert len(data['data']) == 10
        assert data['total_pages'] == 3
        assert data['truncated'] is False

    def test_T7_sql_path_matches_memory_path(self):
        """SQL 导出路（全量同序）与内存 collect 行内容完全一致（防映射漂移）。"""
        with app_module.app.app_context():
            mem_rows = app_module._collect_in_detail_rows(_filters(**self.a_kw))
            _, sql_rows, _, total = app_module._sql_paged_in_detail_report(
                _filters(**self.a_kw, export='excel'))
            assert total == len(mem_rows) == len(sql_rows)
            assert sql_rows == mem_rows, "SQL 路径与内存路径行内容必须一致"
