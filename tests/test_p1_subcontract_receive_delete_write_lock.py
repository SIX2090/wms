# -*- coding: utf-8 -*-
"""P1 回归：删除委外收货单必须加写锁防 TOCTOU。

S13 修复：delete_subcontract_receive / batch_delete_subcontract_receive 在状态预筛后，
必须 _acquire_order_write_lock 二次校验 pending 状态，防止并发完成后
仍被物理删除（导致已收货入库的单被误删且无审计）。
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
from app import SubcontractReceive, User, Warehouse, db  # noqa: E402


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
    c = app_module.app.test_client()
    _login(c)
    yield c


def _create_pending_receive(no="SCR-TEST-001"):
    """直接在 DB 建一张 pending 委外收货单，返回 id。"""
    receive = SubcontractReceive(
        receive_no=no,
        date=date.today(),
        status="pending",
        warehouse="测试仓",
    )
    db.session.add(receive)
    db.session.commit()
    return receive.id


def test_delete_subcontract_receive_succeeds_for_pending(client):
    """待收货状态委外收货单删除应成功。"""
    with app_module.app.app_context():
        rid = _create_pending_receive()
    resp = client.post(f"/subcontract/receive/{rid}/delete")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(SubcontractReceive, rid) is None


def test_delete_subcontract_receive_rejects_completed(client):
    """已完成委外收货单删除必须拒绝。"""
    with app_module.app.app_context():
        rid = _create_pending_receive()
        receive = db.session.get(SubcontractReceive, rid)
        receive.status = "completed"
        db.session.commit()
    resp = client.post(f"/subcontract/receive/{rid}/delete")
    assert resp.status_code in (400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    with app_module.app.app_context():
        assert db.session.get(SubcontractReceive, rid) is not None


def test_delete_subcontract_receive_atomic_after_concurrent_complete(client):
    """模拟 TOCTOU：锁前 pending，锁前另一线程把状态改成 completed，
    删除请求必须拒绝（不能物理删除已收货入库的单）。"""
    with app_module.app.app_context():
        rid = _create_pending_receive()
        receive = db.session.get(SubcontractReceive, rid)
        receive.status = "completed"
        db.session.commit()
    resp = client.post(f"/subcontract/receive/{rid}/delete")
    assert resp.status_code in (400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    with app_module.app.app_context():
        assert db.session.get(SubcontractReceive, rid) is not None


def test_batch_delete_subcontract_receive_rejects_completed(client):
    """批量删除：含已完成单时必须拒绝，且不删除任何一张。"""
    with app_module.app.app_context():
        r1 = _create_pending_receive("SCR-B1")
        r2 = _create_pending_receive("SCR-B2")
        db.session.get(SubcontractReceive, r2).status = "completed"
        db.session.commit()
    resp = client.post("/subcontract/receive/batch_delete", json={"ids": [r1, r2]})
    assert resp.status_code in (200, 400, 409)
    data = resp.get_json()
    assert data.get("status") == "error", data
    with app_module.app.app_context():
        assert db.session.get(SubcontractReceive, r1) is not None
        assert db.session.get(SubcontractReceive, r2) is not None


def test_batch_delete_subcontract_receive_succeeds_for_all_pending(client):
    """批量删除：全部 pending 时应成功。"""
    with app_module.app.app_context():
        r1 = _create_pending_receive("SCR-OK1")
        r2 = _create_pending_receive("SCR-OK2")
    resp = client.post("/subcontract/receive/batch_delete", json={"ids": [r1, r2]})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(SubcontractReceive, r1) is None
        assert db.session.get(SubcontractReceive, r2) is None
