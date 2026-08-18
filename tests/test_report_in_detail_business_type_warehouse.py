# -*- coding: utf-8 -*-
"""回归：入库明细报表必须能查出所有入库类型、且兼容仓库名/编号不统一的历史数据。

BUG-2026-08-18-004：此前 _collect_in_detail_rows 硬编码只查 InOrder.business_type == '采购入库'，
手机端"产品入库"、网页端"其他入库"在入库明细报表里永远查不出来；
同时仓库只按名称匹配，手机端手工录入仓库编号（如 WH001）的历史单据也查不出来。

本测试用真实的 in_detail API 链路验证：
- 采购入库（仓库名）能查出
- 产品入库（仓库编号 WH001）能查出
- 其他入库（仓库名）能查出
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder,
    InOrderItem,
    Material,
    Unit,
    User,
    Warehouse,
    db,
)


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    db.session.add(User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    db.session.commit()


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        unit = Unit(code="PC", name="个")
        db.session.add(unit)
        db.session.flush()
        material = Material(code="M001", name="轴承", spec="6204", unit_id=unit.id, price=10)
        db.session.add(material)
        db.session.flush()
        wh = Warehouse(code="WH001", name="一号仓库", status="active")
        db.session.add(wh)
        db.session.flush()
        wh_id = wh.id

        def _make_in_order(order_no, business_type, warehouse_value):
            order = InOrder(
                order_no=order_no,
                date=date.today(),
                business_type=business_type,
                warehouse=warehouse_value,
                location="",
                status="completed",
                operator_id=1,
                total_amount=10.0,
            )
            db.session.add(order)
            db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=order.id,
                material_id=material.id,
                quantity=1,
                price=10.0,
                amount=10.0,
            ))

        # 网页端：采购入库，仓库存名称
        _make_in_order("IN-001", "采购入库", "一号仓库")
        # 手机端：产品入库，仓库存编号（历史手工录入 WH001 的数据）
        _make_in_order("IN-002", "产品入库", "WH001")
        # 网页端：其他入库，仓库存名称
        _make_in_order("IN-003", "其他入库", "一号仓库")
        db.session.commit()
    c = app_module.app.test_client()
    _login(c)
    yield c


def test_in_detail_report_includes_all_business_types_and_wh_code(client):
    """入库明细报表应同时查出采购/产品/其他入库，且兼容仓库编号历史数据。"""
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="WH001").first()
        wh_id = wh.id
    resp = client.get(f"/report/api/in_detail?warehouse_id={wh_id}")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    order_nos = {row["order_no"] for row in data.get("data", [])}
    types = {(row["order_no"], row["business_type"]) for row in data.get("data", [])}
    # 三种入库类型都要在
    assert "IN-001" in order_nos, f"采购入库未查出: {order_nos}"
    assert "IN-002" in order_nos, f"产品入库(仓库编号WH001)未查出: {order_nos}"
    assert "IN-003" in order_nos, f"其他入库未查出: {order_nos}"
    assert ("IN-001", "采购入库") in types
    assert ("IN-002", "产品入库") in types
    assert ("IN-003", "其他入库") in types
    assert data.get("total") == 3, f"期望3条记录，实际 {data.get('total')}"


def test_in_detail_report_business_type_filter(client):
    """指定 business_type=产品入库 时只返回产品入库记录。"""
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="WH001").first()
        wh_id = wh.id
    resp = client.get(f"/report/api/in_detail?warehouse_id={wh_id}&business_type=产品入库")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    order_nos = {row["order_no"] for row in data.get("data", [])}
    assert order_nos == {"IN-002"}, order_nos
