# -*- coding: utf-8 -*-
"""BUG-2026-09-10-009 回归：手机每日报表支持指定仓库与「全部仓库」汇总。

背景：用户有 4 个以上在用仓库，而手机报表页请求不带任何仓库参数，
`/api/mobile/report/daily_detail` 一律回退 `get_default_warehouse()`（默认仓），
录在其他仓的单据在日报里完全看不到——这是「今天的记录查不到」的直接原因之一。

修复：
- 支持显式 `warehouse_id / warehouse_code / warehouse` 指定仓库；
- 显式传 `all` 表示全部仓库汇总（用户主动跨仓，不是"未指定仓库"，
  不违反 AGENTS.md 仓库必填规则；缺省仍回退默认仓，非法仓库仍 400）；
- 明细行新增 `warehouse` 字段（全部仓库模式下可看出每行所属仓）；
- 响应新增 `warehouse_id` / `all_warehouses`。

验收：
- T1 指定仓只返回该仓数据
- T2 warehouse_id=all 合计 = 各仓之和（R2 汇总=明细）
- T3 全部仓库模式明细行带 warehouse 字段
- T4 不传仓库参数仍回退默认仓（兼容旧 App，行为不变）
- T5 all 模式响应 warehouse='全部仓库' / warehouse_id=null / all_warehouses=true
- T6 非法仓库参数仍 400（仓库必填不放松）
- T7 全部仓库模式下诊断统计同样跨仓（pending_orders 累加）
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
                  price=1.5, unit=unit)
    db.session.add(m1)
    db.session.flush()

    def _in(no, day, warehouse_name, status="completed"):
        order = InOrder(order_no=no, date=day, business_type="采购入库",
                        warehouse=warehouse_name, status=status, operator_id=1,
                        supplier_id=supplier.id, total_amount=0)
        db.session.add(order)
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=order.id, material_id=m1.id,
                                   quantity=5, price=1.5, amount=7.5))
        return order

    _in("IN-A-01", TODAY, "材料仓")          # 默认仓
    _in("IN-B-01", TODAY, "成品仓")          # 非默认仓：旧行为查不到
    _in("IN-B-02", TODAY, "成品仓")
    _in("IN-C-01", TODAY, "五金仓")
    _in("IN-C-PEND", TODAY, "五金仓", status="pending")  # 跨仓待完成
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


class TestDailyReportWarehouseScope:
    def test_t1_explicit_warehouse_id(self, client):
        _, body = _get(client, type="purchase_in", date=TODAY.isoformat(),
                       warehouse_id=2)
        data = body["data"]
        assert {row["order_no"] for row in data["items"]} == {"IN-B-01", "IN-B-02"}
        assert data["warehouse"] == "成品仓"

    def test_t2_all_warehouses_equals_sum(self, client):
        _, all_body = _get(client, type="purchase_in", date=TODAY.isoformat(),
                           warehouse_id="all")
        total = all_body["data"]["summary"]["order_count"]
        per_wh = 0
        for wh_id in (1, 2, 3):
            _, body = _get(client, type="purchase_in", date=TODAY.isoformat(),
                           warehouse_id=wh_id)
            per_wh += body["data"]["summary"]["order_count"]
        assert total == per_wh == 4, "全部仓库合计必须等于各仓之和（R2）"

    def test_t3_all_mode_rows_carry_warehouse(self, client):
        _, body = _get(client, type="purchase_in", date=TODAY.isoformat(),
                       warehouse_id="all")
        rows = {row["order_no"]: row["warehouse"] for row in body["data"]["items"]}
        assert rows == {"IN-A-01": "材料仓", "IN-B-01": "成品仓",
                        "IN-B-02": "成品仓", "IN-C-01": "五金仓"}

    def test_t4_default_warehouse_when_omitted(self, client):
        _, body = _get(client, type="purchase_in", date=TODAY.isoformat())
        data = body["data"]
        assert data["warehouse"] == "材料仓", "不传仓库仍回退默认仓（旧 App 行为不变）"
        assert {row["order_no"] for row in data["items"]} == {"IN-A-01"}

    def test_t5_all_mode_response_flags(self, client):
        _, body = _get(client, type="purchase_in", date=TODAY.isoformat(),
                       warehouse_id="all")
        data = body["data"]
        assert data["warehouse"] == "全部仓库"
        assert data["all_warehouses"] is True
        assert data["warehouse_id"] is None

    def test_t6_invalid_warehouse_rejected(self, client):
        resp, body = _get(client, type="purchase_in", date=TODAY.isoformat(),
                          warehouse_id=999)
        assert resp.status_code == 400, "非法仓库仍必须 400（仓库必填不放松）"
        assert body["status"] == "error"

    def test_t7_all_mode_pending_count_cross_warehouse(self, client):
        _, body = _get(client, type="purchase_in", date=TODAY.isoformat(),
                       warehouse_id="all")
        assert body["data"]["diagnostics"]["pending_orders"] == 1
        _, body_default = _get(client, type="purchase_in", date=TODAY.isoformat())
        assert body_default["data"]["diagnostics"]["pending_orders"] == 0
