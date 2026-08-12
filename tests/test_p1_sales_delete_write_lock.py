# -*- coding: utf-8 -*-
"""P1 回归：删除销售订单必须加写锁防 TOCTOU。

S14 修复：delete_sales_order / batch_delete_sales_orders 在状态预筛后，
必须 _acquire_order_write_lock 二次校验 draft 状态，防止并发确认后
仍被物理删除（导致已确认订单丢失且无审计）。
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
from app import Customer, SalesOrder, User, db  # noqa: E402


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


def _seed_customer():
    cust = Customer(code="C001", name="测试客户")
    db.session.add(cust)
    db.session.commit()
    return cust


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_customer()
    c = app_module.app.test_client()
    _login(c)
    yield c


def _create_draft_sales_order():
    """直接在 DB 建一张 draft 销售订单，返回 id。"""
    cust = Customer.query.first()
    order = SalesOrder(
        order_no="SO-TEST-001",
        customer_id=cust.id,
        date=date.today(),
        status="draft",
    )
    db.session.add(order)
    db.session.commit()
    return order.id


def test_delete_sales_order_succeeds_for_draft(client):
    """草稿销售订单删除应成功。"""
    with app_module.app.app_context():
        oid = _create_draft_sales_order()
    resp = client.post(f"/sales/{oid}/delete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(SalesOrder, oid) is None


def test_delete_sales_order_rejects_confirmed(client):
    """已确认销售订单删除必须拒绝。"""
    with app_module.app.app_context():
        oid = _create_draft_sales_order()
        order = db.session.get(SalesOrder, oid)
        order.status = "confirmed"
        db.session.commit()
    resp = client.post(f"/sales/{oid}/delete")
    assert resp.status_code in (400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    with app_module.app.app_context():
        assert db.session.get(SalesOrder, oid) is not None


def test_delete_sales_order_atomic_after_concurrent_confirm(client):
    """模拟 TOCTOU：锁前 draft，锁前另一线程把状态改成 confirmed，
    删除请求必须拒绝（不能物理删除已确认的单）。"""
    with app_module.app.app_context():
        oid = _create_draft_sales_order()
        # 模拟并发确认：直接改库状态
        order = db.session.get(SalesOrder, oid)
        order.status = "confirmed"
        db.session.commit()
    resp = client.post(f"/sales/{oid}/delete")
    # 预筛返回 400，即使预筛通过，写锁二次校验也会返回 409
    assert resp.status_code in (400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    with app_module.app.app_context():
        assert db.session.get(SalesOrder, oid) is not None


def test_batch_delete_sales_orders_rejects_confirmed(client):
    """批量删除：含已确认单时必须拒绝，且不删除任何一张。"""
    with app_module.app.app_context():
        cust = Customer.query.first()
        o1 = SalesOrder(order_no="SO-B1", customer_id=cust.id, date=date.today(), status="draft")
        o2 = SalesOrder(order_no="SO-B2", customer_id=cust.id, date=date.today(), status="confirmed")
        db.session.add_all([o1, o2])
        db.session.commit()
        id1, id2 = o1.id, o2.id
    resp = client.post("/sales/batch_delete", json={"ids": [id1, id2]})
    assert resp.status_code in (200, 400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    # 批量失败不应部分删除
    with app_module.app.app_context():
        assert db.session.get(SalesOrder, id1) is not None
        assert db.session.get(SalesOrder, id2) is not None


def test_batch_delete_sales_orders_succeeds_for_all_draft(client):
    """批量删除：全部 draft 时应成功。"""
    with app_module.app.app_context():
        cust = Customer.query.first()
        o1 = SalesOrder(order_no="SO-OK1", customer_id=cust.id, date=date.today(), status="draft")
        o2 = SalesOrder(order_no="SO-OK2", customer_id=cust.id, date=date.today(), status="draft")
        db.session.add_all([o1, o2])
        db.session.commit()
        id1, id2 = o1.id, o2.id
    resp = client.post("/sales/batch_delete", json={"ids": [id1, id2]})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(SalesOrder, id1) is None
        assert db.session.get(SalesOrder, id2) is None
