# -*- coding: utf-8 -*-
"""
BUG-2026-08-30-003 回归测试：仓库报表全面审计修复

修复内容：
  1. 盘点/工单领料/委外报表仓库过滤兼容名称/编号任一匹配
     （此前只匹配仓库名，仓库存编号的历史单据在这些报表里查不出）。
  2. 仪表盘趋势图/月度金额图仓库过滤名称/编号任一匹配
     （此前只匹配名称，与统计卡口径不一致）。
  3. 入库/出库/盘点/采购执行明细 .limit(5000) 静默截断 → 上限提高并告警。

断言：
  T1. 盘点报表：仓库字段存编号的单据可查出
  T2. 工单领料报表：仓库字段存编号的单据可查出
  T3. 委外报表：仓库字段存编号的单据可查出
  T4. 仪表盘趋势图：仓库存编号的入库/出库单据计入当日趋势数量
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
from app import (InventoryCheck, InventoryCheckItem, InOrder, InOrderItem,  # noqa: E402
                 Material, OutOrder, OutOrderItem, ProductionRequisition,
                 ProductionRequisitionItem, SubcontractItem, SubcontractOrder,
                 Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True


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


class TestBug20260830003:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([wh, unit, user])
            db.session.flush()
            mat = Material(code="M001", name="电缆", unit_id=unit.id,
                           price=10.0, stock=0.0)
            db.session.add(mat)
            db.session.flush()
            self.wh_id, self.mat_id, self.user_id = wh.id, mat.id, user.id
            # 所有单据的仓库字段都存「编号」，模拟手机端录入
            ck = InventoryCheck(check_no="CK-1", date=date.today(),
                                warehouse="WHA", status="completed",
                                operator_id=user.id)
            db.session.add(ck)
            db.session.flush()
            db.session.add(InventoryCheckItem(
                inventory_check_id=ck.id, material_id=mat.id,
                system_stock=10, actual_stock=12, difference=2))
            req = ProductionRequisition(req_no="REQ-1", date=date.today(),
                                        warehouse="WHA", status="completed",
                                        operator_id=user.id)
            db.session.add(req)
            db.session.flush()
            db.session.add(ProductionRequisitionItem(
                requisition_id=req.id, material_id=mat.id, quantity=3))
            sc = SubcontractOrder(order_no="SC-1", date=date.today(),
                                  warehouse="WHA", status="completed",
                                  operator_id=user.id)
            db.session.add(sc)
            db.session.flush()
            db.session.add(SubcontractItem(subcontract_order_id=sc.id,
                                           material_id=mat.id, quantity=5))
            io = InOrder(order_no="IN-1", date=date.today(), warehouse="WHA",
                         status="completed", operator_id=user.id,
                         business_type="采购入库")
            db.session.add(io)
            db.session.flush()
            db.session.add(InOrderItem(in_order_id=io.id, material_id=mat.id,
                                       quantity=7, price=10.0, amount=70.0))
            oo = OutOrder(order_no="OUT-1", date=date.today(), warehouse="WHA",
                          status="completed", operator_id=user.id)
            db.session.add(oo)
            db.session.flush()
            db.session.add(OutOrderItem(out_order_id=oo.id, material_id=mat.id,
                                        quantity=4, price=10.0, amount=40.0))
            db.session.commit()

    def test_T1_check_report_warehouse_code_match(self):
        with app_module.app.app_context():
            rows = app_module._collect_check_rows(_filters(
                warehouse_id=self.wh_id, warehouse="仓库A", warehouse_code="WHA"))
            assert {r['check_no'] for r in rows} == {"CK-1"}, "盘点报表未命中编号仓库单据"

    def test_T2_requisition_report_warehouse_code_match(self):
        with app_module.app.app_context():
            cols, rows, _ = app_module._build_requisition_report(_filters(
                warehouse_id=self.wh_id, warehouse="仓库A", warehouse_code="WHA"))
            assert {r['req_no'] for r in rows} == {"REQ-1"}, "工单领料报表未命中编号仓库单据"

    def test_T3_subcontract_report_warehouse_code_match(self):
        with app_module.app.app_context():
            cols, rows, _ = app_module._build_subcontract_report(_filters(
                warehouse_id=self.wh_id, warehouse="仓库A", warehouse_code="WHA"))
            assert {r['order_no'] for r in rows} == {"SC-1"}, "委外报表未命中编号仓库单据"

    def test_T4_dashboard_trend_includes_code_warehouse_orders(self):
        with app_module.app.app_context():
            wh = Warehouse.query.get(self.wh_id)
            stats, chart_data = app_module.build_report_dashboard_context(wh)
            trend = chart_data['trend']
            today_key = date.today().strftime('%m-%d')
            idx = trend['labels'].index(today_key)
            assert trend['in_qty'][idx] == 7, "趋势图未计入编号仓库的入库数量"
            assert trend['out_qty'][idx] == 4, "趋势图未计入编号仓库的出库数量"
