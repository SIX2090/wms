# -*- coding: utf-8 -*-
"""SALES-AUDIT-003 + SALES-AUDIT-004 回归测试。

SALES-AUDIT-003：
  create_sales_outbound_draft / batch_create_sales_outbound 此前无写锁，
  build_sales_outbound_draft 的 pending 去重是 check-then-act，并发可生成
  重复草稿导致超扣。修复：两个路由调用 _acquire_order_write_lock 加锁。

SALES-AUDIT-004：
  sync_sales_order_shipment 对 shipped_quantity 用非原子 read-modify-write，
  并发完成引用同一销售订单的多张出库单时丢失更新。修复：改为条件 UPDATE
  + expire，对照 deduct_stock_atomic。

测试用例：
  T1. create_sales_outbound_draft 正常生成草稿（加锁后行为不变）
  T2. create_sales_outbound_draft 对非 confirmed 订单返回错误
  T3. batch_create_sales_outbound 正常批量生成（逐张加锁，每张独立提交）
  T4. batch_create_sales_outbound 跳过非 confirmed 订单
  T5. sync_sales_order_shipment 原子回写 shipped_quantity（基础正向）
  T6. sync_sales_order_shipment 负向回写（quantity_sign=-1 反提交）
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
    sync_sales_order_shipment,
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


class TestCreateOutboundDraftWithLock:
    """T1/T2：create_sales_outbound_draft 加写锁后行为不变。"""

    def test_create_draft_succeeds_for_confirmed(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, _ = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-LOCK-001")
            client = _make_client()
            resp = client.post(f"/sales/{order.id}/create_outbound", json={})
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body
            # 验证草稿已生成
            outbound = OutOrder.query.filter_by(source_sales_order_id=order.id).first()
            assert outbound is not None
            assert outbound.status == "pending"

    def test_create_draft_rejects_draft_status(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, _ = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-LOCK-002")
            order.status = "draft"
            db.session.commit()
            client = _make_client()
            resp = client.post(f"/sales/{order.id}/create_outbound", json={})
            assert resp.status_code == 400
            body = resp.get_json()
            assert body["status"] == "error"


class TestBatchCreateOutboundWithLock:
    """T3/T4：batch_create_sales_outbound 逐张加锁。"""

    def test_batch_create_succeeds(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            o1, _ = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-BATCH-001")
            o2, _ = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-BATCH-002")
            client = _make_client()
            resp = client.post("/sales/batch_create_outbound", json={"ids": [o1.id, o2.id]})
            assert resp.status_code == 200, resp.get_data(as_text=True)
            body = resp.get_json()
            assert body["status"] == "success", body
            assert len(body["created"]) == 2
            # 验证两张草稿都已生成
            ob1 = OutOrder.query.filter_by(source_sales_order_id=o1.id).first()
            ob2 = OutOrder.query.filter_by(source_sales_order_id=o2.id).first()
            assert ob1 is not None and ob2 is not None

    def test_batch_create_skips_non_confirmed(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            o1, _ = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-BATCH-003")
            o2, _ = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-BATCH-004")
            o2.status = "draft"
            db.session.commit()
            client = _make_client()
            resp = client.post("/sales/batch_create_outbound", json={"ids": [o1.id, o2.id]})
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["status"] == "success"
            assert len(body["created"]) == 1
            assert len(body["skipped"]) == 1


class TestSyncShipmentAtomicWriteback:
    """T5/T6：sync_sales_order_shipment 原子回写 shipped_quantity。"""

    def test_sync_writes_shipped_quantity_positive(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-SYNC-001")
            outbound = _make_outbound(order, sales_item, seed["mat"], 4, "OUT-SYNC-001")
            sync_sales_order_shipment(outbound, quantity_sign=1)
            db.session.commit()
            db.session.refresh(sales_item)
            assert sales_item.shipped_quantity == 4

    def test_sync_writes_shipped_quantity_negative(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-SYNC-002")
            # 先模拟已发货 6
            sales_item.shipped_quantity = 6
            db.session.commit()
            # 反提交出库 4（回退）
            outbound = _make_outbound(order, sales_item, seed["mat"], 4, "OUT-SYNC-002")
            sync_sales_order_shipment(outbound, quantity_sign=-1)
            db.session.commit()
            db.session.refresh(sales_item)
            assert sales_item.shipped_quantity == 2

    def test_sync_accumulates_across_multiple_calls(self):
        """连续两次 sync 累加正确（验证不是覆盖而是累加）。"""
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            order, sales_item = _make_confirmed_order(seed["cust"], seed["mat"], 10, "SO-SYNC-003")
            outbound1 = _make_outbound(order, sales_item, seed["mat"], 3, "OUT-SYNC-003A")
            sync_sales_order_shipment(outbound1, quantity_sign=1)
            db.session.commit()
            db.session.refresh(sales_item)
            assert sales_item.shipped_quantity == 3

            outbound2 = _make_outbound(order, sales_item, seed["mat"], 5, "OUT-SYNC-003B")
            sync_sales_order_shipment(outbound2, quantity_sign=1)
            db.session.commit()
            db.session.refresh(sales_item)
            # 累加：3 + 5 = 8
            assert sales_item.shipped_quantity == 8
