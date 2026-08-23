# -*- coding: utf-8 -*-
"""PRINT-ROUTING-F01-P7 回归测试：打印失败/异常系统内告警。

覆盖：
- mark_job_printed 失败建告警、成功不建；告警异常不阻断任务回写
- 当日同类型同目标去重；print_alert_enabled 开关关闭不建
- 僵尸回收次数耗尽置 failed 时补告警
- check_print_health：pending 滞留超阈值告警（未超不报/当日去重）；
  离线工作站仍有定向 pending 任务告警（无定向任务不报，LOCAL-SERVER 云端场景）
- /print_alerts 列表页权限（未登录 302 / admin 200）与标记已读（422/成功/全部）
- context processor：未登录页面不注入未读数
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
from app import (Notification, PrintJob, PrintWorkstation, SystemSetting,  # noqa: E402
                 User, Warehouse, db)
from routes.print_alerts import check_print_health, create_print_alert  # noqa: E402
from routes.print_queue import (MAX_ATTEMPTS, _recover_zombie_printing_jobs,  # noqa: E402
                                mark_job_printed)


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    db.session.add(User(
        username="admin", password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    wh = Warehouse(code="AWH0", name="默认仓", status="active", is_default=True)
    db.session.add(wh)
    db.session.commit()
    return wh


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


def _make_job(status="pending", ws=None, created_at=None, attempts=0,
              printing_started_at=None):
    job = PrintJob(
        job_type="out_order", target_id=21, copies=1, status=status,
        created_by=1, workstation_id=ws.id if ws else None,
        attempts=attempts, printing_started_at=printing_started_at,
        source_event="scan_submit_out",
    )
    if created_at is not None:
        job.created_at = created_at
    db.session.add(job)
    db.session.commit()
    return job


def _alerts(alert_type=None):
    query = Notification.query
    if alert_type:
        query = query.filter(Notification.type == alert_type)
    return query.all()


# ==================== 失败挂点 ====================

def test_create_print_alert(client):
    """create_print_alert：正常创建 + 当日去重 + 开关关闭拒绝。"""
    with app_module.app.app_context():
        note = create_print_alert("print_failed", 1, "打印失败：测试", "内容A")
        assert note is not None and note.id
        # 当日同类型同目标去重
        assert create_print_alert("print_failed", 1, "打印失败：测试", "内容B") is None
        # 不同目标可再建
        assert create_print_alert("print_failed", 2, "打印失败：测试2", "内容C") is not None
        # 开关关闭后不建
        db.session.add(SystemSetting(key="print_alert_enabled", value="0"))
        db.session.commit()
        assert create_print_alert("print_failed", 3, "t", "c") is None


def test_notify_print_failed(client):
    """notify_print_failed：按任务信息组装告警（含单号解析与错误原因）。"""
    from routes.print_alerts import notify_print_failed
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=2)
        job.error_msg = "kiosk 浏览器未找到"
        notify_print_failed(job)
        rows = _alerts("print_failed")
        assert len(rows) == 1
        assert rows[0].target_id == job.id
        assert "kiosk" in rows[0].content
        assert "已尝试 2 次" in rows[0].content


def test_check_print_health(client):
    """check_print_health：滞留与离线统计返回 + 开关关闭全跳过。"""
    with app_module.app.app_context():
        old = datetime.now() - timedelta(minutes=30)
        _make_job(created_at=old)
        stats = check_print_health()
        assert stats == {"pending_timeout": 1, "workstation_offline": 0}
        db.session.add(SystemSetting(key="print_alert_enabled", value="0"))
        db.session.commit()
        assert check_print_health() == {"pending_timeout": 0, "workstation_offline": 0}


def test_mark_failed_creates_alert(client):
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "打印机缺纸")
        assert job.status == "failed"
        rows = _alerts("print_failed")
        assert len(rows) == 1
        assert rows[0].target_id == job.id
        assert "缺纸" in rows[0].content
        assert rows[0].is_read is False


def test_mark_success_no_alert(client):
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, True)
        assert job.status == "done"
        assert _alerts() == []


def test_alert_dedup_same_day(client):
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "缺纸")
        # 同一任务当日第二次失败不再重复建
        job.status = "printing"
        db.session.commit()
        mark_job_printed(job, False, "缺纸")
        assert len(_alerts("print_failed")) == 1


def test_alert_disabled_by_switch(client):
    with app_module.app.app_context():
        db.session.add(SystemSetting(key="print_alert_enabled", value="0"))
        db.session.commit()
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "缺纸")
        assert job.status == "failed"
        assert _alerts() == []


def test_alert_error_does_not_block_writeback(client, monkeypatch):
    import routes.print_alerts as alerts_module

    def _boom(job):
        raise RuntimeError("alert subsystem broken")

    monkeypatch.setattr(alerts_module, "notify_print_failed", _boom)
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "缺纸")
        db.session.refresh(job)
        assert job.status == "failed"
        assert "缺纸" in (job.error_msg or "")


# ==================== 僵尸回收 ====================

def test_zombie_exhausted_creates_alert(client):
    with app_module.app.app_context():
        stale = datetime.now() - timedelta(minutes=10)
        job = _make_job(status="printing", attempts=MAX_ATTEMPTS,
                        printing_started_at=stale)
        recovered = _recover_zombie_printing_jobs()
        assert recovered == 1
        db.session.refresh(job)
        assert job.status == "failed"
        rows = _alerts("print_failed")
        assert len(rows) == 1
        assert "超时" in rows[0].content


def test_zombie_reset_to_pending_no_alert(client):
    with app_module.app.app_context():
        stale = datetime.now() - timedelta(minutes=10)
        job = _make_job(status="printing", attempts=1,
                        printing_started_at=stale)
        recovered = _recover_zombie_printing_jobs()
        assert recovered == 1
        db.session.refresh(job)
        assert job.status == "pending"
        assert _alerts() == []


# ==================== 巡检：pending 滞留 ====================

def test_pending_timeout_alert_and_dedup(client):
    with app_module.app.app_context():
        old = datetime.now() - timedelta(minutes=30)
        _make_job(created_at=old)
        stats = check_print_health()
        assert stats["pending_timeout"] == 1
        rows = _alerts("print_pending_timeout")
        assert len(rows) == 1
        # 当日去重：再次巡检不重复告警
        stats2 = check_print_health()
        assert stats2["pending_timeout"] == 0
        assert len(_alerts("print_pending_timeout")) == 1


def test_pending_fresh_job_no_alert(client):
    with app_module.app.app_context():
        _make_job(created_at=datetime.now())
        stats = check_print_health()
        assert stats["pending_timeout"] == 0
        assert _alerts("print_pending_timeout") == []


# ==================== 巡检：工作站离线 ====================

def test_offline_workstation_with_directed_pending(client):
    with app_module.app.app_context():
        stale_hb = datetime.now() - timedelta(minutes=30)
        ws = PrintWorkstation(
            code="WS-OFF", name="仓库打印电脑", device_id="dev-ws-off",
            status="online", enabled=True, auth_token="tok-off",
            last_heartbeat=stale_hb,
        )
        db.session.add(ws)
        db.session.commit()
        _make_job(ws=ws)  # 定向 pending，created_at 新鲜（不触发滞留告警）
        stats = check_print_health()
        assert stats["workstation_offline"] == 1
        rows = _alerts("print_workstation_offline")
        assert len(rows) == 1
        assert "WS-OFF" in rows[0].content
        # 当日去重
        stats2 = check_print_health()
        assert stats2["workstation_offline"] == 0


def test_undirected_pending_no_workstation_alert(client):
    """LOCAL-SERVER 云端无打印机场景：非定向 pending 不产生工作站误报。"""
    with app_module.app.app_context():
        _make_job(ws=None)  # 非定向
        stats = check_print_health()
        assert stats["workstation_offline"] == 0
        assert _alerts("print_workstation_offline") == []


def test_online_workstation_no_alert(client):
    with app_module.app.app_context():
        ws = PrintWorkstation(
            code="WS-ON", name="打印电脑", device_id="dev-ws-on",
            status="online", enabled=True, auth_token="tok-on",
            last_heartbeat=datetime.now(),
        )
        db.session.add(ws)
        db.session.commit()
        _make_job(ws=ws)
        stats = check_print_health()
        assert stats["workstation_offline"] == 0
        assert _alerts() == []


# ==================== 页面与标记已读 ====================

def test_page_requires_login():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.app_context():
        _reset_db()
        _seed()
    anon = app_module.app.test_client()
    resp = anon.get("/print_alerts")
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


def test_page_renders_for_admin(client):
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "缺纸")
    resp = client.get("/print_alerts")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "打印失败" in html
    assert "缺纸" in html


def test_mark_read_validation_and_success(client):
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "缺纸")
        note = _alerts("print_failed")[0]
        note_id = note.id
    # 空请求 422
    resp = client.post("/print_alerts/mark_read", json={})
    assert resp.status_code == 422
    # 非法类型 422
    resp = client.post("/print_alerts/mark_read", json={"ids": "abc"})
    assert resp.status_code == 422
    # 指定 ID 标记
    resp = client.post("/print_alerts/mark_read", json={"ids": [note_id]})
    assert resp.status_code == 200
    with app_module.app.app_context():
        assert db.session.get(Notification, note_id).is_read is True


def test_mark_read_all(client):
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "缺纸")
        old = datetime.now() - timedelta(minutes=30)
        _make_job(created_at=old)
        check_print_health()
        assert len(_alerts()) >= 2
    resp = client.post("/print_alerts/mark_read", json={"all": True})
    assert resp.status_code == 200
    with app_module.app.app_context():
        unread = Notification.query.filter(Notification.is_read.is_(False)).count()
        assert unread == 0


# ==================== context processor ====================

def test_context_processor_skips_anonymous():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.app_context():
        _reset_db()
        _seed()
    anon = app_module.app.test_client()
    resp = anon.get("/login")
    assert resp.status_code == 200  # 未登录渲染不报错（processor 守卫生效）


def test_bell_badge_shows_unread_count(client):
    with app_module.app.app_context():
        job = _make_job(status="printing", attempts=1)
        mark_job_printed(job, False, "缺纸")
    resp = client.get("/")
    html = resp.get_data(as_text=True)
    assert "print-alert-bell" in html
    assert "print-alert-badge" in html
