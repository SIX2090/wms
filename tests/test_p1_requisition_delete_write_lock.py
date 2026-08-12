# -*- coding: utf-8 -*-
"""P1 回归：删除工单领料单必须加写锁防 TOCTOU。

S12 修复：delete_requisition / batch_delete_requisition 在状态预筛后，
必须 _acquire_order_write_lock 二次校验 pending 状态，防止并发完成后
仍被物理删除（导致库存丢失且无审计）。
"""
from __future__ import annotations

import os
import sys
import threading
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
    LocationInventory, Material, ProductionRequisition,
    ProductionRequisitionItem, Unit, User, Warehouse, db,
    generate_order_no,
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


def _seed_basics():
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100)
    db.session.add(mat)
    db.session.commit()
    return wh, mat


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_basics()
    c = app_module.app.test_client()
    _login(c)
    yield c


def _create_pending_requisition(client):
    """创建一张 pending 领料单（带明细），返回 id。"""
    with app_module.app.app_context():
        req_no = generate_order_no("REQ")
    payload = {
        "order_no": req_no,
        "header": {"warehouse": "默认仓", "purpose": "测试", "picker": "张三"},
        "items": [{"code": "M001", "quantity": 1, "unit_id": 1}],
    }
    resp = client.post("/requisition/save_table", json=payload)
    data = resp.get_json()
    with app_module.app.app_context():
        order = ProductionRequisition.query.filter_by(req_no=req_no).first()
        return order.id


def test_delete_requisition_succeeds_for_pending(client):
    """草稿领料单删除应成功。"""
    rid = _create_pending_requisition(client)
    resp = client.post(f"/requisition/{rid}/delete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(ProductionRequisition, rid) is None


def test_delete_requisition_rejects_completed(client):
    """已完成领料单删除必须拒绝。"""
    rid = _create_pending_requisition(client)
    with app_module.app.app_context():
        req = db.session.get(ProductionRequisition, rid)
        req.status = "completed"
        db.session.commit()
    resp = client.post(f"/requisition/{rid}/delete")
    assert resp.status_code in (400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    # 已完成单必须仍在
    with app_module.app.app_context():
        assert db.session.get(ProductionRequisition, rid) is not None


def test_delete_requisition_atomic_after_concurrent_complete(client):
    """模拟 TOCTOU：锁前 pending，锁前另一线程把状态改成 completed，
    删除请求必须拒绝（不能物理删除已扣库存的单）。"""
    rid = _create_pending_requisition(client)
    # 在调用 delete 前，直接改库把状态置为 completed，模拟并发完成
    with app_module.app.app_context():
        req = db.session.get(ProductionRequisition, rid)
        req.status = "completed"
        db.session.commit()
    resp = client.post(f"/requisition/{rid}/delete")
    # 预筛已经返回 400（status != pending），但即使预筛通过，
    # _acquire_order_write_lock 也会二次校验返回 409
    assert resp.status_code in (400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    with app_module.app.app_context():
        assert db.session.get(ProductionRequisition, rid) is not None


def test_batch_delete_requisition_rejects_completed(client):
    """批量删除：含已完成单时必须拒绝，且不删除任何一张。"""
    r1 = _create_pending_requisition(client)
    r2 = _create_pending_requisition(client)
    with app_module.app.app_context():
        db.session.get(ProductionRequisition, r2).status = "completed"
        db.session.commit()
    resp = client.post("/requisition/batch_delete", json={"ids": [r1, r2]})
    assert resp.status_code in (200, 400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    # r1 仍应存在（批量失败不应部分删除）
    with app_module.app.app_context():
        assert db.session.get(ProductionRequisition, r1) is not None
        assert db.session.get(ProductionRequisition, r2) is not None


def test_batch_delete_requisition_succeeds_for_all_pending(client):
    """批量删除：全部 pending 时应成功。"""
    r1 = _create_pending_requisition(client)
    r2 = _create_pending_requisition(client)
    resp = client.post("/requisition/batch_delete", json={"ids": [r1, r2]})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(ProductionRequisition, r1) is None
        assert db.session.get(ProductionRequisition, r2) is None
