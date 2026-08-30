# -*- coding: utf-8 -*-
"""
BUG-2026-08-30-001 回归测试：出库明细/领料报表筛选修复

修复内容（app.py _collect_out_detail_rows）：
  1. 仓库过滤兼容名称/编号：此前只匹配 OutOrder.warehouse == 仓库名，
     手机端手工录入存仓库编号（如 WHA）的单据在出库报表查不出来；
     与入库明细 BUG-2026-08-18-004 同一口径，名称或编号任一匹配。
  2. 客户/部门筛选字段补全：此前只匹配部门名（无部门时回退用途 purpose），
     完全不查 OutOrder.customer 文本，按客户名称筛选永远无结果；
     现部门名 / 客户文本 / 用途任一命中即保留。

断言：
  T1. 仓库字段存编号时，按该仓库查询出库明细能查出单据
  T2. 按 OutOrder.customer 客户名称关键词能筛出对应单据
  T3. 按部门名关键词仍能筛出（旧行为不回归）
  T4. 不匹配的客户关键词仍然被过滤掉

使用方法：
  cd /workspace && python -m pytest tests/test_bug_2026_08_30_001_out_detail_filter_fixes.py -xvs
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
from app import (Department, Material, OutOrder, OutOrderItem, Unit, User,  # noqa: E402
                 Warehouse, db)

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


def _seed():
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    dept = Department(code="D1", name="生产一部")
    unit = Unit(code="PCS", name="个")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    db.session.add_all([wh, dept, unit, user])
    db.session.flush()
    mat = Material(code="M001", name="电缆", spec="3x2.5", unit_id=unit.id,
                   price=10.0, stock=100.0)
    db.session.add(mat)
    db.session.flush()
    # 单 1：仓库字段存「编号」（模拟手机端录入），记客户文本，无部门
    o1 = OutOrder(order_no="OUT-CODE-1", date=date.today(), warehouse="WHA",
                  customer="恒大地产", purpose="工地领料", status="completed",
                  operator_id=user.id)
    # 单 2：仓库字段存「名称」，挂部门，无客户文本
    o2 = OutOrder(order_no="OUT-NAME-1", date=date.today(), warehouse="仓库A",
                  department_id=dept.id, status="completed", operator_id=user.id)
    db.session.add_all([o1, o2])
    db.session.flush()
    db.session.add_all([
        OutOrderItem(out_order_id=o1.id, material_id=mat.id, quantity=1,
                     price=10.0, amount=10.0),
        OutOrderItem(out_order_id=o2.id, material_id=mat.id, quantity=2,
                     price=10.0, amount=20.0),
    ])
    db.session.commit()
    return wh


class TestBug20260830001:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            self.wh_id = _seed().id

    def _rows(self, **overrides):
        with app_module.app.app_context():
            return app_module._collect_out_detail_rows(_filters(**overrides))

    def test_T1_warehouse_code_stored_order_is_found(self):
        # 仓库存编号的单（OUT-CODE-1）与存名称的单（OUT-NAME-1）都应查出
        rows = self._rows(warehouse_id=self.wh_id,
                          warehouse="仓库A", warehouse_code="WHA")
        order_nos = {r['order_no'] for r in rows}
        assert "OUT-CODE-1" in order_nos, "仓库字段存编号的出库单未查出"
        assert "OUT-NAME-1" in order_nos, "仓库字段存名称的出库单未查出"

    def test_T2_customer_name_keyword_matches(self):
        rows = self._rows(warehouse_id=self.wh_id,
                          warehouse="仓库A", warehouse_code="WHA",
                          customer="恒大")
        order_nos = {r['order_no'] for r in rows}
        assert order_nos == {"OUT-CODE-1"}, "按客户名称筛选未命中 OutOrder.customer"

    def test_T3_department_name_keyword_still_matches(self):
        rows = self._rows(warehouse_id=self.wh_id,
                          warehouse="仓库A", warehouse_code="WHA",
                          customer="生产一部")
        order_nos = {r['order_no'] for r in rows}
        assert order_nos == {"OUT-NAME-1"}, "按部门名筛选旧行为回归"

    def test_T4_unmatched_keyword_filtered(self):
        rows = self._rows(warehouse_id=self.wh_id,
                          warehouse="仓库A", warehouse_code="WHA",
                          customer="不存在的客户")
        assert rows == [], "不匹配的客户关键词应过滤全部单据"
