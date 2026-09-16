# -*- coding: utf-8 -*-
"""「提交后自动打印」总开关回归（BUG-2026-09-16-008）。

背景：手机扫码/移动端提交入库、出库成功后，enqueue_auto_print_job 无条件
自动创建打印任务（"任务始终创建"）。用户从未使用打印、也没有任何在线
打印工作站，任务永远 pending；打印巡检按「同一任务当日只告警一次」去重，
导致同一滞留任务每天零点重复产生「任务滞留」告警（用户原话：我没有打印
为什么有这个消息）。

修复：新增系统设置 auto_print_on_submit（默认开，保持既有行为）：
  1. 关闭后 enqueue_auto_print_job 直接返回 None 不建任务（手动打印不受影响）；
  2. check_print_health 巡检把滞留的自动来源 pending 任务逐批作废
     （status='cancelled'），手动任务与阈值内新任务不动。

覆盖：
  - 默认开启：提交自动建任务（既有行为不变）
  - 开关关闭：不建任务、返回 None、业务不受影响
  - 开关关闭巡检：滞留自动任务作废（含作废原因文案）、手动滞留任务不动、
    阈值内新任务不动、作废后不再产生滞留告警
  - 开关开启巡检：不作废（既有告警行为不变）
  - 静态接线：设置项已注册、enqueue 已设闸、巡检已接入、来源事件常量
    覆盖全部自动调用点的 source_event 字面量
"""
from __future__ import annotations

import os
import re
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
from app import Notification, PrintJob, SystemSetting, User, Warehouse, db  # noqa: E402
from routes.print_alerts import check_print_health  # noqa: E402
from routes.print_queue import (AUTO_PRINT_SOURCE_EVENTS,  # noqa: E402
                                enqueue_auto_print_job)


@pytest.fixture()
def ctx():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add(Warehouse(code="AWH0", name="默认仓", status="active", is_default=True))
        db.session.commit()
        yield
        db.session.remove()


def _switch(off=True):
    db.session.add(SystemSetting(
        key="auto_print_on_submit", value="0" if off else "1"))
    db.session.commit()


def _make_job(source_event, age_min):
    job = PrintJob(
        job_type="out_order", target_id=169, copies=1, status="pending",
        created_by=1, source_event=source_event,
        created_at=datetime.now() - timedelta(minutes=age_min),
    )
    db.session.add(job)
    db.session.commit()
    return job


# A9:no-test=reason=以下 test_ 函数即被测开关的回归测试本体


def test_auto_print_on_submit_enabled(ctx):
    """auto_print_on_submit_enabled：未设置默认 True，写入 0 后 False。"""
    from routes.print_queue import auto_print_on_submit_enabled
    with app_module.app.app_context():
        assert auto_print_on_submit_enabled() is True
        _switch(off=True)
        assert auto_print_on_submit_enabled() is False


def test_default_on_enqueue_creates_job(ctx):
    """未设置开关（默认开）：提交自动建任务，既有行为不变。"""
    with app_module.app.app_context():
        job = enqueue_auto_print_job("out_order", 169, "默认仓",
                                     created_by=1, source_event="scan_submit_out")
        assert job is not None and job.id
        assert job.status == "pending"
        assert PrintJob.query.count() == 1


def test_switch_off_enqueue_returns_none_creates_nothing(ctx):
    """开关关闭：不建任务、返回 None（调用点均不使用返回值，业务照常提交）。"""
    with app_module.app.app_context():
        _switch(off=True)
        job = enqueue_auto_print_job("out_order", 169, "默认仓",
                                     created_by=1, source_event="scan_submit_out")
        assert job is None
        assert PrintJob.query.count() == 0


def test_switch_off_health_check_cancels_only_stale_auto_jobs(ctx):
    """关闭巡检：滞留自动任务作废、手动滞留不动、新任务不动、不再告警。"""
    with app_module.app.app_context():
        _switch(off=True)
        stale_auto = _make_job("scan_submit_out", age_min=60)     # → 作废
        stale_manual = _make_job("manual", age_min=60)            # → 不动（手动打印）
        fresh_auto = _make_job("scan_inbound", age_min=2)         # → 不动（阈值内）

        stats = check_print_health()

        assert stats["auto_cancelled"] == 1
        db.session.expire_all()
        assert db.session.get(PrintJob, stale_auto.id).status == "cancelled"
        assert "自动作废" in (db.session.get(PrintJob, stale_auto.id).error_msg or "")
        assert db.session.get(PrintJob, stale_manual.id).status == "pending"
        assert db.session.get(PrintJob, fresh_auto.id).status == "pending"
        # 作废的自动任务不再产生滞留告警（仍 pending 的手动任务告警属正常链路）
        alerted_targets = {
            n.target_id for n in Notification.query.filter_by(
                type="print_pending_timeout").all()
        }
        assert stale_auto.id not in alerted_targets
        assert fresh_auto.id not in alerted_targets


def test_switch_on_health_check_does_not_cancel(ctx):
    """开启巡检：滞留自动任务不作废、照常当日一次告警（既有行为不变）。"""
    with app_module.app.app_context():
        _switch(off=False)
        job = _make_job("scan_submit_out", age_min=60)

        stats = check_print_health()

        assert stats["auto_cancelled"] == 0
        db.session.expire_all()
        assert db.session.get(PrintJob, job.id).status == "pending"
        assert stats["pending_timeout"] == 1


def test_settings_registered_and_call_sites_covered_static():
    """静态接线：设置项注册、enqueue 设闸、巡检接入；来源事件常量覆盖
    全部自动调用点的 source_event 字面量（新增调用点事件漏登记即报红）。"""
    app_src = (APP_DIR / "app.py").read_text(encoding="utf-8")
    assert "'key': 'auto_print_on_submit'" in app_src
    assert "提交后自动打印" in app_src

    queue_src = (APP_DIR / "routes" / "print_queue.py").read_text(encoding="utf-8")
    assert "if not auto_print_on_submit_enabled():" in queue_src
    alerts_src = (APP_DIR / "routes" / "print_alerts.py").read_text(encoding="utf-8")
    assert "AUTO_PRINT_SOURCE_EVENTS" in alerts_src
    assert "auto_print_on_submit_enabled" in alerts_src

    # 全部自动调用点的 source_event 字面量必须 ⊆ AUTO_PRINT_SOURCE_EVENTS
    used = {"auto"}  # enqueue_auto_print_job 的默认形参值
    for fname in ("mobile.py", "native_api.py"):
        src = (APP_DIR / "routes" / fname).read_text(encoding="utf-8")
        for m in re.finditer(r"enqueue_auto_print_job\((.*?)\)", src, re.S):
            used.update(re.findall(r"source_event='([a-z_]+)'", m.group(1)))
    missing = used - set(AUTO_PRINT_SOURCE_EVENTS)
    assert not missing, f"调用点事件未登记进 AUTO_PRINT_SOURCE_EVENTS: {missing}"
    # 手动建任务必须保持 'manual' 域，不得被自动作废误伤
    model_src = (APP_DIR / "models" / "print.py").read_text(encoding="utf-8")
    assert "default='manual'" in model_src
