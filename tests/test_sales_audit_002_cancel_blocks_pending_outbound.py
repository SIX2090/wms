# -*- coding: utf-8 -*-
"""SALES-AUDIT-002 回归测试：cancel_sales_order 存在 pending 出库草稿时必须拒绝。

根因（P1）：
  cancel_sales_order 此前仅校验 status ∈ {draft,confirmed} 和无已发数量，
  不检查 OutOrder(source_sales_order_id, status='pending')。confirmed 订单
  在已有 pending 草稿时仍可被取消，留下指向 cancelled 订单的孤儿草稿；
  草稿完成后触发 SALES-AUDIT-001 复活链。

修复：
  cancel 前增加 OutOrder.query.filter_by(
      source_sales_order_id=order.id, status='pending').first() 检查，
  存在则拒绝取消并提示先处理出库草稿。

测试用例：
  T1. 无 pending 草稿的 confirmed 订单可正常取消
  T2. 有 pending 草稿的 confirmed 订单取消被拒绝
  T3. 有已完成草稿的订单（无 pending）仍可取消
"""
from __future__ import annotations

import os
import sys
import re
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
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Customer, Material, MaterialCategory, OutOrder, OutOrderItem,
    SalesOrder, SalesOrderItem, Supplier, Unit, User, Warehouse,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="供应商甲")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    cust = Customer(code="C001", name="测试客户")
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=100, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, cust, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "cust": cust, "user": user}


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _make_confirmed_order(cust, mat, qty, order_no):
    order = SalesOrder(
        order_no=order_no,
        customer_id=cust.id,
        warehouse="仓库A",
        date=date.today(),
        status="confirmed",
        shipment_status="pending",
    )
    db.session.add(order)
    db.session.flush()
    item = SalesOrderItem(
        sales_order_id=order.id,
        material_id=mat.id,
        quantity=qty,
        shipped_quantity=0,
        price=10,
        amount=qty * 10,
        tax_rate=0.13,
    )
    db.session.add(item)
    db.session.commit()
    return order, item


def _make_outbound(order, sales_item, mat, qty, order_no, status="pending"):
    outbound = OutOrder(
        order_no=order_no,
        warehouse="仓库A",
        business_type="销售出库",
        source_sales_order_id=order.id,
        status=status,
        date=date.today(),
    )
    db.session.add(outbound)
    db.session.flush()
    item = OutOrderItem(
        out_order_id=outbound.id,
        material_id=mat.id,
        quantity=qty,
        price=10,
        amount=qty * 10,
        source_sales_order_item_id=sales_item.id,
    )
    db.session.add(item)
    db.session.commit()
    return outbound


class TestCancelWithoutPendingOutbound:
    """T1：无 pending 草稿的 confirmed 订单可正常取消。"""

    def test_cancel_succeeds_without_pending_draft(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, _ = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-CAN-001")
            client = _make_client()

            resp = client.post(f"/sales/{order.id}/cancel")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body
            db.session.refresh(order)
            assert order.status == "cancelled"


class TestCancelWithPendingOutboundBlocked:
    """T2：有 pending 草稿的 confirmed 订单取消被拒绝。"""

    def test_cancel_blocked_when_pending_draft_exists(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-CAN-002")
            outbound = _make_outbound(order, sales_item, seed["mat"], 5, "OUT-CAN-002", status="pending")
            client = _make_client()

            resp = client.post(f"/sales/{order.id}/cancel")
            assert resp.status_code == 400, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "error", body
            assert "出库草稿" in body.get("msg", "") or "草稿" in body.get("msg", "")
            # 订单状态保持 confirmed（未被取消）
            db.session.refresh(order)
            assert order.status == "confirmed"


class TestCancelWithCompletedOutboundOnly:
    """T3：有已完成草稿但无 pending 的订单仍可取消（但 shipped>0 应被 T1 校验拦）。

    这里验证：仅有 completed 草稿且 shipped_quantity=0 的边缘情况，cancel 不被
    pending 检查拦截（pending 检查只关心 status='pending'）。
    """

    def test_cancel_not_blocked_by_completed_outbound(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-CAN-003")
            # 创建一张 completed 草稿（但 shipped_quantity 仍为 0，模拟反提交后状态）
            _make_outbound(order, sales_item, seed["mat"], 5, "OUT-CAN-003", status="completed")
            client = _make_client()

            resp = client.post(f"/sales/{order.id}/cancel")
            # shipped_quantity=0 通过校验 + 无 pending 草稿通过校验 → 允许取消
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body
            db.session.refresh(order)
            assert order.status == "cancelled"
