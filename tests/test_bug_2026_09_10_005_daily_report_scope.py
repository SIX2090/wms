# -*- coding: utf-8 -*-
"""BUG-2026-09-10-005 回归：手机端每日报表「查不到今天的记录」。

现象：
- 手机 App 每日报表（领料单）看不到手机原生端 /api/outbound 扫出的出库单；
  该接口历史上固定写 business_type='Android扫码出库'，而报表严格等值 '领料单'。
  首页「今日出库」却有数（dashboard 不区分业务类型），口径自相矛盾。
- PC 端入库/出库保存后默认是 pending（需人工点完成），报表只统计 completed，
  用户表现为「今天的记录查不到」却没有任何线索。

修复：
- requisition 口径改为业务类型集合（'领料单' / 'Android扫码出库' / 类型为空），
  与 PC 领料单列表口径一致；
- 响应输出 warehouse / server_today / diagnostics（待完成单据数、其他类型分布），
  供手机端在空态给出「为什么查不到」的明确提示。

验收：
- T1 手机扫码出库必须出现在领料日报
- T2 业务类型为空的历史出库单按领料计
- T3 销售出库/其他出库不得混入领料日报（口径不扩大）
- T4 响应必须带 warehouse / server_today / diagnostics
- T5 PC pending 单（未点完成）计入 pending_orders 且不进明细
- T6 其他业务类型计数进入 other_type_orders（产品入库不进采购入库日报）
- T7 R2 多仓隔离：他仓手机扫码出库不得串仓
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def _seed():
    from app import (Department, InOrder, InOrderItem, Material, OutOrder,
                     OutOrderItem, Supplier, Unit, User, Warehouse)

    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    wh = Warehouse(code="WH01", name="材料仓", status="active", is_default=True)
    other_wh = Warehouse(code="WH02", name="成品仓", status="active", is_default=False)
    unit = Unit(code="U1", name="个")
    supplier = Supplier(code="SUP001", name="鑫达五金")
    dept = Department(code="DEP001", name="生产一部", status="active")
    db.session.add_all([wh, other_wh, unit, supplier, dept])
    db.session.flush()
    m1 = Material(code="MAT001", name="6204轴承", spec="20*47*14", stock=0,
                  price=1.5, unit=unit)
    db.session.add(m1)
    db.session.flush()

    def _in(no, biz, status, day, warehouse="材料仓"):
        order = InOrder(order_no=no, date=day, business_type=biz, warehouse=warehouse,
                        status=status, operator_id=1, supplier_id=supplier.id,
                        total_amount=0)
        db.session.add(order)
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=order.id, material_id=m1.id,
                                   quantity=5, price=1.5, amount=7.5))
        return order

    def _out(no, biz, status, day, warehouse="材料仓"):
        order = OutOrder(order_no=no, date=day, business_type=biz, warehouse=warehouse,
                         status=status, operator_id=1, department_id=dept.id,
                         total_amount=0)
        db.session.add(order)
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=order.id, material_id=m1.id,
                                    quantity=3, price=1.5, amount=4.5))
        return order

    # 今日：手机原生端扫码出库（历史 business_type='Android扫码出库'）
    _out("OUT-APP-01", "Android扫码出库", "completed", TODAY)
    # 今日：PC 领料单
    _out("OUT-PC-01", "领料单", "completed", TODAY)
    # 今日：业务类型为空的历史出库单（PC 列表按领料计）
    _out("OUT-NULL-01", None, "completed", TODAY)
    # 今日干扰项：销售出库 / 其他出库 不得混入领料日报
    _out("OUT-SALE-01", "销售出库", "completed", TODAY)
    _out("OUT-OTHER-01", "其他出库", "completed", TODAY)
    # 今日：PC 录入但未点完成的出库单 → 不进明细，计入 pending_orders
    _out("OUT-PEND-01", "领料单", "pending", TODAY)
    # 今日：采购入库 completed + 产品入库（不进采购入库日报）+ pending 入库
    _in("IN-TODAY-01", "采购入库", "completed", TODAY)
    _in("IN-PROD-01", "产品入库", "completed", TODAY)
    _in("IN-PEND-01", "采购入库", "pending", TODAY)
    # 昨日手机扫码出库 → 换日期才出现
    _out("OUT-APP-Y1", "Android扫码出库", "completed", YESTERDAY)
    # 跨仓手机扫码出库 → 仓库隔离
    _out("OUT-APP-OTHER", "Android扫码出库", "completed", TODAY, warehouse="成品仓")
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        _seed()
        db.session.remove()
    c = app_module.app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin"},
           content_type="application/x-www-form-urlencoded")
    yield c
    with app_module.app.app_context():
        db.session.remove()


def _get(c, **params):
    resp = c.get(f"/api/mobile/report/daily_detail?{urlencode(params)}")
    return resp, resp.get_json()


class TestDailyReportMobileScope:
    def test_t1_android_scan_outbound_appears_in_requisition(self, client):
        _, body = _get(client, type="requisition", date=TODAY.isoformat())
        data = body["data"]
        order_nos = {row["order_no"] for row in data["items"]}
        assert "OUT-APP-01" in order_nos, "手机扫码出库必须计入领料日报"
        assert data["summary"]["order_count"] == 3  # APP + PC + 空类型

    def test_t2_null_business_type_counted_as_requisition(self, client):
        _, body = _get(client, type="requisition", date=TODAY.isoformat())
        order_nos = {row["order_no"] for row in body["data"]["items"]}
        assert "OUT-NULL-01" in order_nos, "业务类型为空的历史出库单应按领料计"

    def test_t3_sale_and_other_outbound_excluded(self, client):
        _, body = _get(client, type="requisition", date=TODAY.isoformat())
        order_nos = {row["order_no"] for row in body["data"]["items"]}
        assert "OUT-SALE-01" not in order_nos, "销售出库不得混入领料日报"
        assert "OUT-OTHER-01" not in order_nos, "其他出库不得混入领料日报"

    def test_t4_response_has_warehouse_and_diagnostics(self, client):
        _, body = _get(client, type="requisition", date=TODAY.isoformat())
        data = body["data"]
        assert data["warehouse"] == "材料仓"
        assert data["server_today"] == TODAY.isoformat()
        diag = data["diagnostics"]
        assert "Android扫码出库" in diag["business_types"]
        assert "领料单" in diag["business_types"]

    def test_t5_pending_orders_reported_but_excluded(self, client):
        _, body = _get(client, type="requisition", date=TODAY.isoformat())
        data = body["data"]
        assert "OUT-PEND-01" not in {row["order_no"] for row in data["items"]}
        assert data["diagnostics"]["pending_orders"] == 1, "PC 未点完成的单据必须暴露为待完成数"

    def test_t6_other_type_orders_reported(self, client):
        _, body = _get(client, type="purchase_in", date=TODAY.isoformat())
        data = body["data"]
        assert [row["order_no"] for row in data["items"]] == ["IN-TODAY-01"]
        others = {row["business_type"]: row["orders"]
                  for row in data["diagnostics"]["other_type_orders"]}
        assert others.get("产品入库") == 1, "产品入库应提示为其他业务类型"
        assert data["diagnostics"]["pending_orders"] == 1

    def test_t7_cross_warehouse_isolated(self, client):
        _, body = _get(client, type="requisition", date=TODAY.isoformat())
        order_nos = {row["order_no"] for row in body["data"]["items"]}
        assert "OUT-APP-OTHER" not in order_nos, "他仓手机扫码出库不得串仓"
        # 显式切到成品仓后可见
        _, body2 = _get(client, type="requisition", date=TODAY.isoformat(),
                        warehouse_id=2)
        assert "OUT-APP-OTHER" in {row["order_no"] for row in body2["data"]["items"]}

    def test_t8_yesterday_not_leaked_into_today(self, client):
        _, body = _get(client, type="requisition", date=YESTERDAY.isoformat())
        assert [row["order_no"] for row in body["data"]["items"]] == ["OUT-APP-Y1"]
