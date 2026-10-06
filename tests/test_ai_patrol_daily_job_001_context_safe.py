# -*- coding: utf-8 -*-
"""AI-ASSISTANT-PATROL-001 回归：每日定时巡检 job 的上下文安全性。

背景：`_ai_run_warehouse_patrol_agent` 的链路里有 `_ai_create_agent_task`
（取 `current_user.id`、`g.ai_run_id`）和 5 处 `url_for`，二者都依赖
request context。`init_notification_scheduler` 里的 `daily_agent_patrol`
job 由 APScheduler 触发时只有 app context —— 裸调会抛
`AttributeError: 'NoneType' object has no attribute 'is_authenticated'`。
修复：job 内用 `app.test_request_context()` 包装 + `login_user(首位管理员)`。

断言：
  T1. job 在 scheduler 环境下执行不抛异常，且产出 1 个 completed 的
      AIAgentTask（证明 request ctx 包装生效、url_for 不再炸）。
  T2. job 执行后落 1 条 type='ai_patrol' 的站内通知，内容含巡检摘要。
  T3. AI 总开关关闭时 job 静默返回：不建任务、不发通知。
  T4. 无可用管理员时 job 静默返回（不炸、不建任务）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

# A12/R7：模块顶层禁止裸 app context push/pop，统一放 autouse fixture
_ctx = app_module.app.app_context()


import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="module")
def _push_ctx():
    _ctx.push()
    yield
    _ctx.pop()


def _reset(ai_enabled: str = "1", with_admin: bool = True):
    """重建内存库：AI 开关 + 管理员按需配置。"""
    from werkzeug.security import generate_password_hash

    db.drop_all()
    db.create_all()
    if with_admin:
        db.session.add(app_module.User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        ))
    db.session.commit()
    app_module.set_system_setting("ai_feature_global_enabled", ai_enabled)
    db.session.commit()


def _patrol_job_callable():
    """从 init_notification_scheduler 抓出 daily_agent_patrol job 函数。

    不真启动 scheduler（避免后台线程污染测试）；用假 BackgroundScheduler
    捕获 add_job 注册的 job 函数后手动执行，模拟 APScheduler 线程环境
    （无 request context）。
    """
    import apscheduler.schedulers.background as bgmod
    import notifications

    captured = {}

    class _FakeScheduler:
        def add_job(self, func, trigger, **kwargs):
            if kwargs.get("id") == "daily_agent_patrol":
                captured["job"] = func

        def start(self):
            pass

    _real = bgmod.BackgroundScheduler
    bgmod.BackgroundScheduler = _FakeScheduler
    try:
        notifications.init_notification_scheduler(
            app_module.app, db, app_module.Material, app_module.User)
    finally:
        bgmod.BackgroundScheduler = _real
    return captured["job"]


def _patrol_notification_count():
    from app import Notification
    return Notification.query.filter_by(type="ai_patrol").count()


def test_daily_agent_patrol():
    """T1（test_daily_agent_patrol）：job 在无 request context 的环境下执行不炸，且建出巡检任务。"""
    from app import AIAgentTask
    _reset(ai_enabled="1")
    job = _patrol_job_callable()
    # 关键：不进入任何 request context，模拟 APScheduler 线程环境
    job()
    tasks = AIAgentTask.query.filter_by(agent_type="warehouse_patrol").all()
    assert len(tasks) == 1, "job 应创建 1 个 warehouse_patrol 巡检任务"
    assert tasks[0].status == "completed"
    assert len(tasks[0].steps) == 4, "巡检任务应包含 4 个步骤"


def test_daily_agent_patrol_t2_job_creates_notification_with_summary():
    """T2：job 执行后落 1 条 ai_patrol 站内通知，内容含巡检摘要。"""
    from app import Notification
    _reset(ai_enabled="1")
    before = _patrol_notification_count()
    job = _patrol_job_callable()
    job()
    after = _patrol_notification_count()
    assert after == before + 1, "job 应新增 1 条 ai_patrol 通知"
    notif = Notification.query.filter_by(type="ai_patrol").order_by(
        Notification.id.desc()).first()
    assert notif is not None and notif.title.startswith("AI 巡检完成")
    assert notif.content, "通知内容不应为空"


def test_daily_agent_patrol_t3_job_skips_when_ai_disabled():
    """T3：AI 总开关关闭时 job 静默跳过：不建任务、不发通知。"""
    from app import AIAgentTask
    _reset(ai_enabled="0")
    job = _patrol_job_callable()
    job()
    assert AIAgentTask.query.filter_by(
        agent_type="warehouse_patrol").count() == 0, (
        "AI 关闭时不应创建巡检任务")
    assert _patrol_notification_count() == 0, (
        "AI 关闭时不应发 ai_patrol 通知")


def test_daily_agent_patrol_t4_job_skips_when_no_admin():
    """T4：无可用管理员时 job 静默返回，不抛异常。"""
    from app import AIAgentTask
    _reset(ai_enabled="1", with_admin=False)
    job = _patrol_job_callable()
    job()  # 不应抛异常
    assert AIAgentTask.query.filter_by(
        agent_type="warehouse_patrol").count() == 0, (
        "无管理员时不应创建巡检任务")
