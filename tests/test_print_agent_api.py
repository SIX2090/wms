# -*- coding: utf-8 -*-
"""PRINT-ROUTING-F01-P3 回归测试：Windows 打印代理 agent API v1（工作站令牌鉴权）。

覆盖：
- 令牌鉴权：无/错令牌 401，停用工作站 401，有效令牌通过
- claim：认领本工作站任务置 printing，重复认领返回 empty，离线工作站返回 empty
- complete/fail：仅允许本工作站任务，跨工作站 404
- heartbeat：工作站置 online + 心跳时间刷新；打印机 upsert 新增/更新；
  未上报打印机置 offline；停用（enabled=False）打印机不受影响
- workstation_is_online：心跳超窗视为离线，NULL 心跳兼容模式仍按 status 判定
- 路由解析：心跳超窗的工作站不再被派发任务
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
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
from app import (PrintDevice, PrintJob, PrintRouteRule, PrintWorkstation,
                 User, Warehouse, db)  # noqa: E402


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    db.session.add(User(
        username="admin", password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    db.session.add(wh)
    db.session.commit()
    return wh


def _seed_workstation(wh, code="WS-1", token="tok-ws-1", status="online",
                      heartbeat=None, enabled=True):
    ws = PrintWorkstation(
        code=code, name=code, device_id=f"device-{code}",
        warehouse_id=wh.id, status=status, enabled=enabled,
        auth_token=token, last_heartbeat=heartbeat,
    )
    db.session.add(ws)
    db.session.commit()
    return ws


def _seed_job(ws, printer=None, status="pending"):
    job = PrintJob(
        job_type="out_order", target_id=11, copies=1, status=status,
        created_by=1, workstation_id=ws.id,
        printer_id=printer.id if printer else None,
        source_event="scan_outbound",
    )
    db.session.add(job)
    db.session.commit()
    return job


def _login(client, username="admin"):
    return client.post(
        "/login",
        data={"username": username, "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed()
    c = app_module.app.test_client()
    _login(c)
    yield c


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


# ==================== 令牌鉴权 ====================

def test_agent_api_rejects_missing_or_wrong_token(client):
    resp = client.post("/print_queue/api/v1/claim", json={})
    assert resp.status_code == 401
    resp = client.post("/print_queue/api/v1/claim", json={}, headers=_hdr("wrong-token"))
    assert resp.status_code == 401
    resp = client.post("/print_queue/api/v1/heartbeat", json={"printers": []})
    assert resp.status_code == 401
    resp = client.post("/print_queue/api/v1/jobs/1/complete", json={})
    assert resp.status_code == 401


def test_agent_api_rejects_disabled_workstation_token(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        _seed_workstation(wh, code="WS-DIS", token="tok-disabled", enabled=False)
    resp = client.post("/print_queue/api/v1/claim", json={}, headers=_hdr("tok-disabled"))
    assert resp.status_code == 401


# ==================== claim ====================

def test_agent_claim_returns_and_locks_job(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws = _seed_workstation(wh)
        job = _seed_job(ws)
        job_id = job.id
    resp = client.post("/print_queue/api/v1/claim", json={}, headers=_hdr("tok-ws-1"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["job"]["id"] == job_id
    assert body["job"]["job_type"] == "out_order"
    assert body["job"]["print_url"] == f"/out_order/11/print"
    # 再次认领：任务已 printing，队列为空
    resp2 = client.post("/print_queue/api/v1/claim", json={}, headers=_hdr("tok-ws-1"))
    assert resp2.get_json()["status"] == "empty"
    with app_module.app.app_context():
        job = db.session.get(PrintJob, job_id)
        assert job.status == "printing"
        assert job.attempts == 1


def test_agent_claim_rejects_stale_heartbeat_workstation(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws = _seed_workstation(
            wh, code="WS-STALE", token="tok-stale",
            heartbeat=datetime.now() - timedelta(minutes=30),
        )
        _seed_job(ws)
    resp = client.post("/print_queue/api/v1/claim", json={}, headers=_hdr("tok-stale"))
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "empty"


# ==================== complete / fail ====================

def test_agent_complete_and_fail_own_job_only(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws1 = _seed_workstation(wh, code="WS-A", token="tok-a")
        _seed_workstation(wh, code="WS-B", token="tok-b")
        ws1_id = ws1.id
        job = _seed_job(ws1)
        job_id = job.id
    # 跨工作站上报：404
    resp = client.post(f"/print_queue/api/v1/jobs/{job_id}/complete",
                       json={}, headers=_hdr("tok-b"))
    assert resp.status_code == 404
    resp = client.post(f"/print_queue/api/v1/jobs/{job_id}/fail",
                       json={"error_msg": "x"}, headers=_hdr("tok-b"))
    assert resp.status_code == 404
    # 本工作站：complete 成功
    resp = client.post(f"/print_queue/api/v1/jobs/{job_id}/complete",
                       json={}, headers=_hdr("tok-a"))
    assert resp.status_code == 200
    with app_module.app.app_context():
        assert db.session.get(PrintJob, job_id).status == "done"
    # fail：再造一条任务
    with app_module.app.app_context():
        ws1 = db.session.get(PrintWorkstation, ws1_id)
        job2 = _seed_job(ws1)
        job2_id = job2.id
    resp = client.post(f"/print_queue/api/v1/jobs/{job2_id}/fail",
                       json={"error_msg": "缺纸"}, headers=_hdr("tok-a"))
    assert resp.status_code == 200
    with app_module.app.app_context():
        job2 = db.session.get(PrintJob, job2_id)
        assert job2.status == "failed"
        assert job2.error_msg == "缺纸"


# ==================== heartbeat ====================

def test_agent_heartbeat_syncs_workstation_and_printers(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws = _seed_workstation(wh, status="offline")
        ws_id = ws.id
        # 预置一台打印机：本次心跳不再上报 → 应置 offline
        db.session.add(PrintDevice(
            workstation_id=ws.id, system_name="OldPrinter", display_name="旧打印机",
            status="online", enabled=True,
        ))
        # 预置一台已停用打印机：本次不上报也不应改动 enabled
        disabled = PrintDevice(
            workstation_id=ws.id, system_name="DisabledPrinter", display_name="停用打印机",
            status="online", enabled=False,
        )
        db.session.add(disabled)
        db.session.commit()
    resp = client.post("/print_queue/api/v1/heartbeat", json={
        "version": "1.0.0",
        "printers": [
            {"system_name": "Zebra ZD421", "status": "ready", "is_default": True},
            {"system_name": "HP LaserJet", "status": "error"},
        ],
    }, headers=_hdr("tok-ws-1"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["data"]["printers_online"] == 2
    assert body["data"]["printers_created"] == 2
    with app_module.app.app_context():
        ws = db.session.get(PrintWorkstation, ws_id)
        assert ws.status == "online"
        assert ws.last_heartbeat is not None
        devices = {d.system_name: d for d in PrintDevice.query.filter_by(workstation_id=ws_id).all()}
        assert devices["Zebra ZD421"].status == "online"
        assert devices["Zebra ZD421"].is_default is True
        assert devices["HP LaserJet"].status == "error"
        assert devices["OldPrinter"].status == "offline"      # 未上报 → 离线
        assert devices["DisabledPrinter"].enabled is False    # 停用打印机不受心跳影响
        # 第二次心跳：不重复创建
        resp2 = client.post("/print_queue/api/v1/heartbeat", json={
            "printers": [{"system_name": "Zebra ZD421"}],
        }, headers=_hdr("tok-ws-1"))
        assert resp2.get_json()["data"]["printers_created"] == 0
        devices2 = {d.system_name: d for d in PrintDevice.query.filter_by(workstation_id=ws_id).all()}
        assert devices2["Zebra ZD421"].status == "online"
        assert devices2["HP LaserJet"].status == "offline"    # 第二次未上报 → 离线


def test_agent_heartbeat_rejects_bad_payload(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        _seed_workstation(wh)
    resp = client.post("/print_queue/api/v1/heartbeat", json={
        "printers": [{"system_name": ""}],
    }, headers=_hdr("tok-ws-1"))
    assert resp.status_code == 400


# ==================== workstation_is_online 单元行为 ====================

def test_workstation_is_online():
    from routes.print_queue import workstation_is_online
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        # status=offline → False
        ws = _seed_workstation(wh, code="WS-OFF", token="t1", status="offline")
        assert workstation_is_online(ws) is False
        # 心跳为 NULL：兼容模式，按 status 判定 → True
        ws.status = "online"
        assert workstation_is_online(ws) is True
        # 心跳新鲜 → True
        ws.last_heartbeat = datetime.now() - timedelta(seconds=30)
        assert workstation_is_online(ws) is True
        # 心跳超窗 → False
        ws.last_heartbeat = datetime.now() - timedelta(minutes=30)
        assert workstation_is_online(ws) is False


# ==================== 路由解析感知心跳超窗 ====================

def test_route_resolution_skips_stale_heartbeat_workstation(client):
    """心跳超窗的工作站不再接收新任务（enqueue 不定向，走公共队列）。"""
    from routes.print_queue import enqueue_auto_print_job
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        stale = _seed_workstation(
            wh, code="WS-STALE2", token="tok-stale2",
            heartbeat=datetime.now() - timedelta(hours=1),
        )
        printer = PrintDevice(
            workstation_id=stale.id, system_name="P1", display_name="P1",
            status="online", enabled=True,
        )
        db.session.add(printer)
        db.session.flush()
        db.session.add(PrintRouteRule(
            name="规则", business_event="out_order", warehouse_id=wh.id,
            workstation_id=stale.id, printer_id=printer.id, priority=10, enabled=True,
        ))
        db.session.commit()
        # 心跳超窗：enqueue 不定向（返回 None），任务不创建
        assert enqueue_auto_print_job("out_order", 99, wh.name,
                                      source_event="scan_outbound") is None
        # 心跳恢复后：同一路由规则恢复派发
        stale.last_heartbeat = datetime.now()
        db.session.commit()
        job = enqueue_auto_print_job("out_order", 99, wh.name,
                                     source_event="scan_outbound")
        assert job is not None
        assert job.workstation_id == stale.id
        db.session.rollback()
