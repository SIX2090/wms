# -*- coding: utf-8 -*-
"""SALES-AUDIT-001 回归测试：cancelled 销售订单不得被出库完成静默复活。

根因（P0）：
  recalculate_sales_order 的 partial/shipped 分支无条件写 order.status
  = 'confirmed'/'closed'，未守卫 cancelled 状态。触发链：
  确认 → 下推草稿 → 取消订单（shipped_quantity=0 通过校验）
  → 完成草稿 → sync_sales_order_shipment 写 shipped_quantity>0
  → recalculate_sales_order 走 partial/shipped 分支 → cancelled 被改回。

修复：
  1. recalculate_sales_order 的 partial/shipped 分支同样加
     `if order.status not in ('draft', 'cancelled')` 守卫；
  2. sync_sales_order_shipment 入口对 cancelled 订单提前 return None
     （防御纵深，阻止 shipped_quantity 被写回）。

测试用例：
  T1. cancelled 订单直接调用 recalculate_sales_order，状态保持 cancelled
  T2. cancelled 订单调用 sync_sales_order_shipment 不写 shipped_quantity
  T3. cancelled 订单经 complete_out_order 完成其 pending 草稿后，
      状态仍为 cancelled，shipped_quantity 保持 0
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
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Customer, Material, MaterialCategory, OutOrder, OutOrderItem,
    SalesOrder, SalesOrderItem, Supplier, Unit, User, Warehouse,
    recalculate_sales_order, sync_sales_order_shipment,
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
    import re
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
    """创建一张 confirmed 销售订单（带明细）。"""
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


def _make_pending_outbound(order, sales_item, mat, qty, order_no):
    """创建一张 pending 销售出库草稿，关联到销售订单/明细。"""
    outbound = OutOrder(
        order_no=order_no,
        warehouse="仓库A",
        business_type="销售出库",
        source_sales_order_id=order.id,
        status="pending",
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


class TestRecalculateCancelledGuard:
    """T1：cancelled 订单直接调用 recalculate_sales_order 状态保持不变。"""

    def test_cancelled_stays_cancelled_when_shipped_qty_positive(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-T1-001")
            # 模拟取消前已下推并发完成的极小概率场景：直接构造 cancelled + shipped>0
            order.status = "cancelled"
            item.shipped_quantity = 10
            db.session.commit()
            # 刷新关系，确保 recalculate 能正确遍历 items
            db.session.refresh(order)
            db.session.refresh(item)

            recalculate_sales_order(order)
            db.session.refresh(order)
            # 关键断言：cancelled 不被覆盖为 closed（shipped 分支守卫生效）
            assert order.status == "cancelled", f"状态被复活为 {order.status}"

    def test_cancelled_stays_cancelled_when_partial(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-T1-002")
            order.status = "cancelled"
            item.shipped_quantity = 3
            db.session.commit()
            db.session.refresh(order)
            db.session.refresh(item)

            recalculate_sales_order(order)
            db.session.refresh(order)
            assert order.status == "cancelled", f"partial 分支复活状态为 {order.status}"


class TestSyncShipmentSkipsCancelled:
    """T2：cancelled 订单调用 sync_sales_order_shipment 不写 shipped_quantity。"""

    def test_sync_does_not_write_shipped_for_cancelled(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-T2-001")
            order.status = "cancelled"
            db.session.commit()

            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-T2-001")
            result = sync_sales_order_shipment(outbound, quantity_sign=1)

            # 防御纵深：返回 None 且不写 shipped_quantity
            assert result is None, "cancelled 订单应被 sync 跳过"
            db.session.refresh(sales_item)
            assert sales_item.shipped_quantity == 0, "shipped_quantity 被错误回写"


class TestCompleteOutboundDoesNotReviveCancelled:
    """T3：经 complete_out_order 路径完成 cancelled 订单的 pending 草稿，
    订单状态保持 cancelled，shipped_quantity 保持 0。"""

    def test_complete_cancelled_order_outbound_no_revive(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-T3-001")
            outbound = _make_pending_outbound(order, sales_item, seed["mat"], 5, "OUT-T3-001")
            # 在草稿存在的情况下取消订单（模拟审计 P0 触发链）
            # 注意：取消后 shipped_quantity 仍为 0，cancel 路径当前允许（SALES-AUDIT-002 将修复）
            order.status = "cancelled"
            db.session.commit()

            client = _make_client()
            resp = client.post(f"/out_order/{outbound.id}/complete?force=true")
            # 完成可能成功（出库本身是仓库动作），但销售订单状态不应被复活
            db.session.refresh(order)
            db.session.refresh(sales_item)
            assert order.status == "cancelled", f"出库完成把 cancelled 复活为 {order.status}"
            # shipped_quantity 也不应被写回（sync 提前跳过）
            assert (sales_item.shipped_quantity or 0) == 0, \
                f"shipped_quantity 被错误回写为 {sales_item.shipped_quantity}"
