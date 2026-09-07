# -*- coding: utf-8 -*-
"""BUG-2026-09-07-011 回归：盘点/采购订单执行报表 SQL 分页下沉。

背景：BUG-2026-09-07-004 只下沉了入库/出库明细，盘点明细与采购订单执行
仍走"全量物化（最多 5 万行）再内存切片"老路——翻一次页重算一次全量，
超限时汇总按截断数据失真（违反 R2 汇总=明细）。本修复把这两个报表的
count/聚合/排序/分页同样下沉 SQL：
- 行映射提炼为 _check_row / _purchase_execution_row（内存路径与 SQL 路径
  单一映射源，防两份映射漂移）；
- 盘点新增 _filtered_check_query 共用 WHERE 构造；
- 采购执行 _purchase_order_item_query 统一 outerjoin Supplier/Unit/
  PurchaseRequest（排序映射用），排序移交调用方；
- 采购执行汇总基于 distinct 子查询——warehouse 过滤分支 outerjoin 入库单
  会把同一采购行展开多行，直接 sum 会按入库行数放大金额/数量。

断言：
  T1. 盘点分页语义：page1/2 行数正确、互不重叠、total 为真实总数。
  T2. 盘点汇总与分页解耦：不同页 summary 相同且等于全集聚合；无仓库返回空。
  T3. 盘点排序下沉：difference 降序首页首行为最大值，total 不受排序影响。
  T4. 采购执行分页语义 + 仓库必填；B 仓采购数据不串入 A 仓（R2 隔离）。
  T5. 采购执行汇总不放大：同一采购行被 2 张入库单引用（warehouse 分支
      展开 2 行），summary count/quantity/amount 仍按 1 行计。
  T6. 采购执行排序下沉 + supplier 关键词筛选（outerjoin 化后语义不回归）。
  T7. SQL 路径与内存路径行级一致（check / purchase_execution 各一，防映射漂移）。
  T8. API 层：/report/api/check 分页元数据 total/total_pages 正确。
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
from app import (  # noqa: E402
    InOrder, InOrderItem, InventoryCheck, InventoryCheckItem, Material,
    PurchaseOrder, PurchaseOrderItem, Supplier, Unit, User, Warehouse, db,
)

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


class TestBug20260907011:
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
            supplier = Supplier(code="SUP1", name="鑫达五金")
            db.session.add_all([self.wh_a, self.wh_b, unit, user, supplier])
            db.session.flush()
            self.supplier_id = supplier.id
            mat = Material(code="M001", name="轴承", spec="6204",
                           unit_id=unit.id, price=10.0, stock=0.0)
            db.session.add(mat)
            db.session.flush()
            self.mat_id = mat.id
            # A 仓盘点单：13 行，difference 从 -6 递增到 +6 便于排序断言
            check_a = InventoryCheck(check_no="PD-A", date=date.today(),
                                     warehouse="仓库A", status="completed",
                                     operator_id=user.id)
            db.session.add(check_a)
            db.session.flush()
            for idx in range(13):
                diff = idx - 6
                db.session.add(InventoryCheckItem(
                    inventory_check_id=check_a.id, material_id=mat.id,
                    system_stock=10.0, actual_stock=10.0 + diff,
                    difference=float(diff)))
            # B 仓盘点单：1 行（R2 隔离验证）
            check_b = InventoryCheck(check_no="PD-B", date=date.today(),
                                     warehouse="仓库B", status="completed",
                                     operator_id=user.id)
            db.session.add(check_b)
            db.session.flush()
            db.session.add(InventoryCheckItem(
                inventory_check_id=check_b.id, material_id=mat.id,
                system_stock=5.0, actual_stock=9.0, difference=4.0))
            # A 仓采购订单：1 行，数量 100、已收 30；被 2 张入库单引用
            # （warehouse 过滤分支会把它展开 2 行，汇总不得放大）
            po_a = PurchaseOrder(order_no="PO-A", date=date.today(),
                                 supplier_id=supplier.id, status="partial",
                                 operator_id=user.id, total_amount=1000.0)
            db.session.add(po_a)
            db.session.flush()
            po_item_a = PurchaseOrderItem(
                purchase_order_id=po_a.id, material_id=mat.id,
                quantity=100.0, received_quantity=30.0,
                price=10.0, amount=1000.0)
            db.session.add(po_item_a)
            db.session.flush()
            for idx, qty in enumerate((20.0, 10.0)):
                io = InOrder(order_no=f"PIN-A{idx}", date=date.today(),
                             warehouse="仓库A", status="completed",
                             operator_id=user.id, business_type="采购入库",
                             source_purchase_order_id=po_a.id)
                db.session.add(io)
                db.session.flush()
                db.session.add(InOrderItem(
                    in_order_id=io.id, material_id=mat.id,
                    quantity=qty, price=10.0, amount=qty * 10.0,
                    source_purchase_order_item_id=po_item_a.id))
            # B 仓采购订单：1 行（R2 隔离验证）
            po_b = PurchaseOrder(order_no="PO-B", date=date.today(),
                                 supplier_id=supplier.id, status="pending",
                                 operator_id=user.id, total_amount=500.0)
            db.session.add(po_b)
            db.session.flush()
            po_item_b = PurchaseOrderItem(
                purchase_order_id=po_b.id, material_id=mat.id,
                quantity=50.0, received_quantity=0.0,
                price=10.0, amount=500.0)
            db.session.add(po_item_b)
            db.session.flush()
            io_b = InOrder(order_no="PIN-B0", date=date.today(),
                           warehouse="仓库B", status="completed",
                           operator_id=user.id, business_type="采购入库",
                           source_purchase_order_id=po_b.id)
            db.session.add(io_b)
            db.session.commit()
            self.wh_a_id = self.wh_a.id
            self.wh_b_id = self.wh_b.id
            self.a_kw = dict(warehouse_id=self.wh_a_id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=self.wh_b_id, warehouse="仓库B", warehouse_code="WHB")

    # ---------- 盘点明细 ----------
    def test_T1_check_pagination_semantics(self):
        """盘点：page1=10、page2=3、互不重叠、total=13。"""
        with app_module.app.app_context():
            seen = []
            for page, expect in ((1, 10), (2, 3)):
                _, rows, _, total = app_module._sql_paged_check_report(
                    _filters(**self.a_kw, page=page, page_size=10))
                assert len(rows) == expect, f"page{page} 应 {expect} 行，实际 {len(rows)}"
                assert total == 13, f"total 应为真实总数 13，实际 {total}"
                seen.extend(r['check_no'] + str(r['system_stock']) + str(r['difference']) for r in rows)
            assert len(seen) == len(set(seen)), "分页之间不得重叠"

    def test_T2_check_summary_decoupled_and_warehouse_required(self):
        """盘点：summary 跨页一致且=全集聚合；无仓库返回空。"""
        with app_module.app.app_context():
            _, _, s1, _ = app_module._sql_paged_check_report(
                _filters(**self.a_kw, page=1, page_size=10))
            _, _, s2, _ = app_module._sql_paged_check_report(
                _filters(**self.a_kw, page=2, page_size=10))
            assert s1 == s2, "不同页 summary 必须一致（全集口径）"
            assert s1['count'] == 13
            # quantity = sum(actual_stock) = sum(10+diff), diff 从 -6..6 对称 → 13*10
            assert s1['quantity'] == 130.0, f"实盘数量全集求和错误: {s1['quantity']}"
            # amount = sum(|difference|) = 2*(1+..+6) = 42
            assert s1['amount'] == 42.0, f"差异绝对值全集求和错误: {s1['amount']}"
            _, rows, summary, total = app_module._sql_paged_check_report(_filters())
            assert total == 0 and rows == [], "无仓库必须返回空"
            assert summary == {'count': 0, 'quantity': 0, 'amount': 0}

    def test_T3_check_sort_in_sql(self):
        """盘点：difference 降序首页首行为最大值 +6；total 不变。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_check_report(
                _filters(**self.a_kw, page=1, page_size=10,
                         sort_field='difference', sort_order='desc'))
            assert total == 13
            diffs = [r['difference'] for r in rows]
            assert diffs[0] == 6.0, f"降序首行应为最大差异 6，实际 {diffs[0]}"
            assert diffs == sorted(diffs, reverse=True), "当页必须按差异降序"

    # ---------- 采购订单执行 ----------
    def test_T4_purchase_pagination_and_isolation(self):
        """采购执行：A 仓 total=1 且行内容正确；B 仓不串入；无仓库返回空。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_purchase_execution_report(
                _filters(**self.a_kw))
            assert total == 1, f"A 仓应 1 行，实际 {total}"
            row = rows[0]
            assert row['order_no'] == 'PO-A'
            assert row['order_quantity'] == 100.0
            assert row['received_quantity'] == 30.0
            assert row['remaining_quantity'] == 70.0
            _, rows_b, _, total_b = app_module._sql_paged_purchase_execution_report(
                _filters(**self.b_kw))
            assert total_b == 1 and rows_b[0]['order_no'] == 'PO-B', "B 仓只应看到 PO-B"
            _, rows_none, _, total_none = app_module._sql_paged_purchase_execution_report(
                _filters())
            assert total_none == 0 and rows_none == [], "无仓库必须返回空"

    def test_T5_purchase_summary_not_amplified_by_join(self):
        """采购执行：同一采购行被 2 张入库单引用，汇总仍按 1 行计（不放大）。"""
        with app_module.app.app_context():
            _, _, summary, total = app_module._sql_paged_purchase_execution_report(
                _filters(**self.a_kw))
            assert total == 1, f"distinct 后 total 应为 1，实际 {total}"
            assert summary['count'] == 1, f"汇总行数被入库单展开放大: {summary['count']}"
            assert summary['quantity'] == 100.0, \
                f"数量被放大（应为 100 而非 200）: {summary['quantity']}"
            assert summary['amount'] == 1000.0, \
                f"金额被放大（应为 1000 而非 2000）: {summary['amount']}"

    def test_T6_purchase_sort_and_supplier_keyword(self):
        """采购执行：order_quantity 降序；supplier 关键词筛选 outerjoin 化后不回归。"""
        with app_module.app.app_context():
            _, rows, _, total = app_module._sql_paged_purchase_execution_report(
                _filters(**self.a_kw, sort_field='order_quantity', sort_order='desc'))
            assert total == 1 and rows[0]['order_quantity'] == 100.0
            _, rows_s, _, total_s = app_module._sql_paged_purchase_execution_report(
                _filters(**self.a_kw, supplier='鑫达'))
            assert total_s == 1 and rows_s[0]['supplier'] == '鑫达五金', \
                "supplier 关键词筛选（outerjoin+filter）必须命中"
            _, _, _, total_miss = app_module._sql_paged_purchase_execution_report(
                _filters(**self.a_kw, supplier='不存在的供应商'))
            assert total_miss == 0, "supplier 关键词不命中时必须返回 0 行"

    # ---------- 双路径一致性（防映射漂移） ----------
    def test_T7_sql_path_matches_memory_path(self):
        """check / purchase_execution：SQL 导出路与内存 collect 行内容完全一致。"""
        with app_module.app.app_context():
            mem_check = app_module._collect_check_rows(_filters(**self.a_kw))
            _, sql_check, _, total_check = app_module._sql_paged_check_report(
                _filters(**self.a_kw, export='excel'))
            assert total_check == len(mem_check) == len(sql_check)
            assert sql_check == mem_check, "盘点 SQL 路径与内存路径行内容必须一致"

            mem_po = app_module._collect_purchase_order_execution_rows(_filters(**self.a_kw))
            _, sql_po, _, total_po = app_module._sql_paged_purchase_execution_report(
                _filters(**self.a_kw, export='excel'))
            assert total_po == len(mem_po) == len(sql_po)
            assert sql_po == mem_po, "采购执行 SQL 路径与内存路径行内容必须一致"

    # ---------- API 层 ----------
    def test_T8_api_check_pagination_metadata(self):
        """API：/report/api/check?page=2&page_size=10 → 3 行、total=13、total_pages=2。"""
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(f"/report/api/check?warehouse_id={self.wh_a_id}&page=2&page_size=10")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 13
        assert len(data['data']) == 3
        assert data['total_pages'] == 2
        assert data['truncated'] is False
