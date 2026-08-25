# -*- coding: utf-8 -*-
"""移动端每日明细报表 API 回归测试（/api/mobile/report/daily_detail）。

覆盖：
- type=purchase_in 只统计当日"采购入库"已完成单据明细
- type=requisition 只统计当日"领料单"已完成单据明细
- 日期筛选 / 非法日期 / 非法类型 / pending 排除 / 仓库隔离 / 分页
- 汇总基于全集（order_count/item_count/quantity/amount）
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

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
    m2 = Material(code="MAT002", name="M8螺母", spec="M8", stock=0,
                  price=2.0, unit=unit)
    db.session.add_all([m1, m2])
    db.session.flush()

    def in_order(no, biz, status, day, warehouse="材料仓"):
        order = InOrder(order_no=no, date=day, business_type=biz,
                        warehouse=warehouse, status=status, operator_id=1,
                        supplier_id=supplier.id, total_amount=0)
        db.session.add(order)
        db.session.flush()
        return order

    def add_in_items(order, specs):
        for material, qty, price in specs:
            db.session.add(InOrderItem(in_order_id=order.id, material_id=material.id,
                                       quantity=qty, price=price,
                                       amount=round(qty * price, 2)))
        db.session.flush()

    def out_order(no, biz, status, day):
        order = OutOrder(order_no=no, date=day, business_type=biz,
                         warehouse="材料仓", status=status, operator_id=1,
                         department_id=dept.id, total_amount=0)
        db.session.add(order)
        db.session.flush()
        return order

    def add_out_items(order, specs):
        for material, qty, price in specs:
            db.session.add(OutOrderItem(out_order_id=order.id, material_id=material.id,
                                        quantity=qty, price=price,
                                        amount=round(qty * price, 2)))
        db.session.flush()

    # 今日：采购入库 completed（10×1.5 + 5×2.0 = 25.0）
    add_in_items(in_order("IN-TODAY-01", "采购入库", "completed", TODAY),
                 [(m1, 10, 1.5), (m2, 5, 2.0)])
    # 今日：领料单 completed（3×1.5 + 2×2.0 = 8.5）
    add_out_items(out_order("OUT-TODAY-01", "领料单", "completed", TODAY),
                  [(m1, 3, 1.5), (m2, 2, 2.0)])
    # 今日干扰项：产品入库 / 其他出库 / pending 采购入库 → 均不应出现在报表
    add_in_items(in_order("IN-TODAY-02", "产品入库", "completed", TODAY), [(m1, 1, 1.5)])
    add_out_items(out_order("OUT-TODAY-02", "其他出库", "completed", TODAY), [(m1, 1, 1.5)])
    add_in_items(in_order("IN-TODAY-03", "采购入库", "pending", TODAY), [(m1, 9, 1.5)])
    # 昨日采购入库 → 仅在 date=昨日时出现
    add_in_items(in_order("IN-YDAY-01", "采购入库", "completed", YESTERDAY),
                 [(m1, 4, 1.5)])
    # 跨仓采购入库 → 仓库隔离，不应出现
    add_in_items(in_order("IN-OTHER-01", "采购入库", "completed", TODAY,
                          warehouse="成品仓"), [(m1, 7, 1.5)])
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
    from urllib.parse import urlencode
    resp = c.get(f"/api/mobile/report/daily_detail?{urlencode(params)}")
    return resp, resp.get_json()


class TestDailyDetailReport:
    def test_purchase_in_today_default_date(self, client):
        resp, body = _get(client, type="purchase_in")
        assert resp.status_code == 200
        data = body["data"]
        assert data["date"] == TODAY.isoformat()
        assert data["type_label"] == "采购入库"
        assert data["total"] == 2
        assert data["summary"]["order_count"] == 1
        assert data["summary"]["item_count"] == 2
        assert data["summary"]["quantity"] == 15
        assert data["summary"]["amount"] == 25.0
        codes = {row["material_code"] for row in data["items"]}
        assert codes == {"MAT001", "MAT002"}
        row = next(r for r in data["items"] if r["material_code"] == "MAT001")
        assert row["order_no"] == "IN-TODAY-01"
        assert row["supplier"] == "鑫达五金"
        assert row["unit"] == "个"
        assert row["amount"] == 15.0

    def test_requisition_today(self, client):
        resp, body = _get(client, type="requisition")
        assert resp.status_code == 200
        data = body["data"]
        assert data["type_label"] == "领料单"
        assert data["total"] == 2
        assert data["summary"]["order_count"] == 1
        assert data["summary"]["quantity"] == 5
        assert data["summary"]["amount"] == 8.5
        row = next(r for r in data["items"] if r["material_code"] == "MAT002")
        assert row["department"] == "生产一部"
        assert row["order_no"] == "OUT-TODAY-01"

    def test_date_filter(self, client):
        resp, body = _get(client, type="purchase_in", date=YESTERDAY.isoformat())
        assert resp.status_code == 200
        data = body["data"]
        assert data["total"] == 1
        assert data["items"][0]["order_no"] == "IN-YDAY-01"
        assert data["summary"]["quantity"] == 4

    def test_empty_day_returns_zero_summary(self, client):
        resp, body = _get(client, type="requisition", date=YESTERDAY.isoformat())
        assert resp.status_code == 200
        data = body["data"]
        assert data["total"] == 0
        assert data["items"] == []
        assert data["summary"]["order_count"] == 0
        assert data["summary"]["amount"] == 0.0

    def test_invalid_type(self, client):
        resp, body = _get(client, type="foo")
        assert resp.status_code == 400
        assert body["status"] == "error"

    def test_missing_type(self, client):
        resp, body = _get(client)
        assert resp.status_code == 400

    def test_invalid_date_format(self, client):
        resp, body = _get(client, type="purchase_in", date="2026-13-99")
        assert resp.status_code == 400
        assert "YYYY-MM-DD" in body["msg"]

    def test_pagination(self, client):
        resp, body = _get(client, type="purchase_in", page=1, page_size=1)
        assert resp.status_code == 200
        data = body["data"]
        assert data["total"] == 2
        assert data["total_pages"] == 2
        assert len(data["items"]) == 1
        # 汇总仍基于全集
        assert data["summary"]["quantity"] == 15


class TestDailyDetailContractNo:
    """手机端报表展示合同编号：明细行返回 contract_no（明细级优先，回退单据头）。"""

    def _seed_contract_rows(self):
        from app import Contract, InOrder, InOrderItem, Material, OutOrder, OutOrderItem
        with app_module.app.app_context():
            contract = Contract(contract_no="HD260709", project_name="城东配电工程", status="active")
            db.session.add(contract)
            db.session.flush()
            material = Material.query.filter_by(code="MAT001").one()
            # 入库单：仅单据头有合同编号
            in_order = InOrder(order_no="IN-CT-01", date=TODAY, business_type="采购入库",
                               warehouse="材料仓", status="completed", operator_id=1,
                               contract_id=contract.id, contract_no="HD260709",
                               project_name="城东配电工程", total_amount=0)
            db.session.add(in_order)
            db.session.flush()
            db.session.add(InOrderItem(in_order_id=in_order.id, material_id=material.id,
                                       quantity=1, price=1.5, amount=1.5))
            # 出库单（领料单）：明细级合同编号覆盖单据头
            out_order = OutOrder(order_no="OUT-CT-01", date=TODAY, business_type="领料单",
                                 warehouse="材料仓", status="completed", operator_id=1,
                                 contract_no="HD260700", total_amount=0)
            db.session.add(out_order)
            db.session.flush()
            db.session.add(OutOrderItem(out_order_id=out_order.id, material_id=material.id,
                                        quantity=2, price=1.5, amount=3.0,
                                        contract_no="HD260709"))
            db.session.commit()

    def test_purchase_in_row_has_contract_no_from_header(self, client):
        self._seed_contract_rows()
        resp, body = _get(client, type="purchase_in")
        assert resp.status_code == 200
        row = next(r for r in body["data"]["items"] if r["order_no"] == "IN-CT-01")
        assert row["contract_no"] == "HD260709"

    def test_requisition_row_item_contract_overrides_header(self, client):
        self._seed_contract_rows()
        resp, body = _get(client, type="requisition")
        assert resp.status_code == 200
        row = next(r for r in body["data"]["items"] if r["order_no"] == "OUT-CT-01")
        assert row["contract_no"] == "HD260709"

    def test_row_without_contract_returns_empty_string(self, client):
        resp, body = _get(client, type="purchase_in")
        assert resp.status_code == 200
        row = next(r for r in body["data"]["items"] if r["order_no"] == "IN-TODAY-01")
        assert row["contract_no"] == ""


class TestDailyDetailSpecNullSafety:
    """BUG-2026-08-24-007：material.spec 列可空（nullable）。

    daily_detail 明细行 spec 必须兜底为空字符串，禁止下发显式 null——
    Android 端 Gson 经 Unsafe 实例化（绕过构造器默认值），显式 null 会把
    非空字段运行时置 null，UI 层 isNotBlank() 即抛 NPE 导致整 App 崩溃。
    """

    def test_material_without_spec_returns_empty_string(self, client):
        with app_module.app.app_context():
            from app import InOrder, InOrderItem, Material
            m3 = Material(code="MAT003", name="无规格物料", stock=0, price=1.0, unit_id=1)
            db.session.add(m3)
            db.session.flush()
            order = InOrder(order_no="IN-SPEC-01", date=TODAY, business_type="采购入库",
                            warehouse="材料仓", status="completed", operator_id=1,
                            supplier_id=1, total_amount=0)
            db.session.add(order)
            db.session.flush()
            db.session.add(InOrderItem(in_order_id=order.id, material_id=m3.id,
                                       quantity=1, price=1.0, amount=1.0))
            db.session.commit()
        resp, body = _get(client, type="purchase_in")
        assert resp.status_code == 200
        row = next(r for r in body["data"]["items"] if r["material_code"] == "MAT003")
        assert row["spec"] == "", "spec 为 NULL 的物料必须输出空字符串，不得下发显式 null"
