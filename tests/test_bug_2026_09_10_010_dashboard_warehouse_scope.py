# -*- coding: utf-8 -*-
"""BUG-2026-09-10-010 回归：手机首页概览支持指定仓库与「全部仓库」汇总。

背景：与 BUG-2026-09-10-009（日报跨仓）同根因。手机首页 `/api/mobile/dashboard`
此前不带任何仓库参数，服务端一律回退 `get_default_warehouse()`，首页四张卡
（今日入库/出库/待处理/库存告警）只反映默认仓。对于有 4 个以上在用仓库的用户，
录在其他仓的单据完全不计入，首页数字明显偏小甚至为 0。

修复：
- 支持显式 `warehouse_id / warehouse_code / warehouse` 指定仓库；
- 显式传 `all` 表示全部仓库汇总（用户主动跨仓，不违反 AGENTS.md 仓库必填）；
- 响应新增 `warehouse` / `warehouse_id` / `all_warehouses`。

验收：
- T1 指定仓只统计该仓的今日单据数
- T2 warehouse_id=all 合计 = 各仓之和（R2 汇总=明细）
- T3 全部仓库模式待处理数同样跨仓累加
- T4 不传仓库参数仍回退默认仓（兼容旧 App，行为不变）
- T5 all 模式响应 warehouse='全部仓库' / warehouse_id=null / all_warehouses=true
- T6 非法仓库参数仍 400（仓库必填不放松）
- T7 全部仓库模式下告警按物料去重（跨仓同一物料只算一条）
- T8 今日数量（非单数）同样跨仓累加
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
    wh_a = Warehouse(code="WHA", name="材料仓", status="active", is_default=True)
    wh_b = Warehouse(code="WHB", name="成品仓", status="active", is_default=False)
    wh_c = Warehouse(code="WHC", name="五金仓", status="active", is_default=False)
    unit = Unit(code="U1", name="个")
    supplier = Supplier(code="SUP001", name="鑫达五金")
    dept = Department(code="DEP001", name="生产一部", status="active")
    db.session.add_all([wh_a, wh_b, wh_c, unit, supplier, dept])
    db.session.flush()
    m1 = Material(code="MAT001", name="6204轴承", spec="20*47*14", stock=0,
                  price=1.5, unit=unit, min_stock=10)
    m2 = Material(code="MAT002", name="螺栓", spec="M8", stock=0,
                  price=0.5, unit=unit, min_stock=100)
    db.session.add_all([m1, m2])
    db.session.flush()

    def _in(no, day, warehouse_name, qty=5, status="completed"):
        order = InOrder(order_no=no, date=day, business_type="采购入库",
                        warehouse=warehouse_name, status=status, operator_id=1,
                        supplier_id=supplier.id, total_amount=0)
        db.session.add(order)
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=order.id, material_id=m1.id,
                                   quantity=qty, price=1.5, amount=qty * 1.5))
        return order

    def _out(no, day, warehouse_name, qty=3, status="completed"):
        order = OutOrder(order_no=no, date=day, business_type="领料单",
                         warehouse=warehouse_name, status=status, operator_id=1,
                         department_id=dept.id, total_amount=0)
        db.session.add(order)
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=order.id, material_id=m1.id,
                                    quantity=qty, price=1.5, amount=qty * 1.5))
        return order

    # 今日已完成：默认仓 1 张，非默认仓 2 张（旧行为只看到 1 张）
    _in("IN-A-01", TODAY, "材料仓", qty=5)
    _in("IN-B-01", TODAY, "成品仓", qty=7)
    _in("IN-B-02", TODAY, "五金仓", qty=11)
    # 今日出库：默认仓 1 张，非默认仓 1 张
    _out("OUT-A-01", TODAY, "材料仓", qty=3)
    _out("OUT-C-01", TODAY, "五金仓", qty=4)
    # 待处理：默认仓 1、非默认仓 2
    _in("IN-A-PEND", TODAY, "材料仓", status="pending")
    _in("IN-B-PEND", TODAY, "成品仓", status="pending")
    _out("OUT-C-PEND", TODAY, "五金仓", status="pending")
    # 昨日已完成：不应计入"今日"
    _in("IN-A-OLD", YESTERDAY, "材料仓", qty=99)
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
    qs = urlencode(params) if params else ""
    resp = c.get(f"/api/mobile/dashboard?{qs}" if qs else "/api/mobile/dashboard")
    return resp, resp.get_json()


class TestDashboardWarehouseScope:
    def test_t1_explicit_warehouse_id(self, client):
        _, body = _get(client, warehouse_id=2)
        data = body["data"]
        assert data["today_in_orders"] == 1, "成品仓今日仅 1 张入库单"
        assert data["today_out_orders"] == 0, "成品仓今日无出库单"
        assert data["warehouse"] == "成品仓"

    def test_t2_all_warehouses_equals_sum(self, client):
        _, all_body = _get(client, warehouse_id="all")
        total_in = all_body["data"]["today_in_orders"]
        per_wh_in = 0
        for wh_id in (1, 2, 3):
            _, body = _get(client, warehouse_id=wh_id)
            per_wh_in += body["data"]["today_in_orders"]
        assert total_in == per_wh_in, "全部仓库合计必须等于各仓之和（R2）"

    def test_t3_all_mode_pending_is_cross_warehouse(self, client):
        _, all_body = _get(client, warehouse_id="all")
        data = all_body["data"]
        # 待处理入库：材料仓 1 + 成品仓 1 = 2；出库：五金仓 1
        assert data["pending_in_orders"] == 2
        assert data["pending_out_orders"] == 1

    def test_t4_default_warehouse_when_omitted(self, client):
        _, body = _get(client)
        data = body["data"]
        assert data["today_in_orders"] == 1, "缺省应回退默认仓（材料仓）"
        assert data["warehouse"] == "材料仓"
        assert data["all_warehouses"] is False

    def test_t5_all_mode_flags(self, client):
        _, body = _get(client, warehouse_id="all")
        data = body["data"]
        assert data["warehouse"] == "全部仓库"
        assert data["warehouse_id"] is None
        assert data["all_warehouses"] is True

    def test_t6_invalid_warehouse_still_400(self, client):
        resp, body = _get(client, warehouse_id=999999)
        assert resp.status_code == 400
        assert body["status"] == "error"

    def test_t7_all_mode_alert_dedup(self, client):
        """跨仓同一物料低于最低库存只算一条告警（不被仓库数放大）。"""
        from app import Material
        with app_module.app.app_context():
            assert Material.query.filter(Material.min_stock > 0).count() >= 2
        _, all_body = _get(client, warehouse_id="all")
        _, wh1_body = _get(client, warehouse_id=1)
        alert_all = all_body["data"]["alert_count"]
        alert_wh1 = wh1_body["data"]["alert_count"]
        # 全部仓库告警去重后不超过物料种类数（2 种），而非 2 种 × 3 仓 = 6
        assert alert_all <= 2, f"告警应去重，实际 {alert_all}"
        # 单仓告警不超过全部告警
        assert alert_wh1 <= alert_all

    def test_t8_all_mode_quantity_sum(self, client):
        _, all_body = _get(client, warehouse_id="all")
        _, wh1_body = _get(client, warehouse_id=1)
        _, wh2_body = _get(client, warehouse_id=2)
        _, wh3_body = _get(client, warehouse_id=3)
        total_qty = all_body["data"]["today_in_quantity"]
        sum_qty = sum(b["data"]["today_in_quantity"]
                      for b in (wh1_body, wh2_body, wh3_body))
        assert abs(total_qty - sum_qty) < 0.01, "数量合计必须等于各仓之和（R2）"


class TestDashboardYesterdayExcluded:
    def test_yesterday_not_counted(self, client):
        _, body = _get(client, warehouse_id="all")
        # 昨日那张 99 个不应计入今日
        assert body["data"]["today_in_quantity"] == 23.0, "5 + 7 + 11 = 23"
