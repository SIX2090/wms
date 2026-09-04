# -*- coding: utf-8 -*-
"""BUG-2026-09-04-001 回归测试：AI-R14 自动清理预览保存日志外键失败。

现象：AI-R14-F01 每日 02:00 自动清理预览保存 ai_cleanup_log 时报
`sqlite3.IntegrityError: FOREIGN KEY constraint failed`
（2026-09-03 / 2026-09-04 连续两天同参数复现，executed_by=0）。

根因：系统自动任务没有真实登录用户，代码写 executed_by=0，而
ai_cleanup_log.executed_by 是 user.id 的非空外键，users 表不存在 id=0 行，
SQLite 开启 foreign_keys 后 INSERT 必违反约束（R5 审计链路断点）。

修复（R6 已排查全部 executed_by=0 消费点，仅 notifications.py 一处）：
1) app.app 新增 _ai_dr_resolve_system_executor_id()：优先
   WMS_BOOTSTRAP_USERNAME/admin 账号，无 admin 取最小 id 用户，无用户返回 None；
2) _ai_dr_save_log 兜底：入参 executed_by<=0 或用户不存在时解析系统归属账号，
   无账号可归时跳过落库并告警（不再让外键异常刷日志）；
3) notifications.py 每日预览改传解析结果，源文本不再出现 executed_by=0（锚点断言）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import AICleanupLog, User, db  # noqa: E402
from ai.ops.data_retention import CleanupLogEntry  # noqa: E402


@pytest.fixture()
def app_ctx():
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        yield


def _add_user(username: str, role: str = "admin"):
    user = User(username=username, password_hash="!", role=role)
    db.session.add(user)
    db.session.commit()
    return user


def _make_entry(executed_by, log_id="auto-preview-test"):
    return CleanupLogEntry(
        log_id=log_id,
        executed_by=executed_by,
        categories=("images",),
        dry_run=True,
        deleted_count=0,
        kept_count=3,
        exempt_count=0,
        protected_count=0,
        failed_count=0,
        cutoff_date="2026-09-03T02:00:00",
        executed_at="2026-09-04T02:00:00",
        notes="系统自动预览（未实际删除）",
    )


def test_resolve_prefers_bootstrap_admin(app_ctx):
    """优先返回 admin（WMS_BOOTSTRAP_USERNAME 默认）账号 id。"""
    normal = _add_user("worker", role="user")
    admin = _add_user("admin", role="admin")
    resolved = app_module._ai_dr_resolve_system_executor_id()
    assert resolved == admin.id
    assert resolved != normal.id


def test_resolve_uses_bootstrap_username_env(app_ctx, monkeypatch):
    """配置 WMS_BOOTSTRAP_USERNAME 时优先该账号。"""
    _add_user("admin", role="admin")
    boss = _add_user("boss", role="admin")
    monkeypatch.setenv("WMS_BOOTSTRAP_USERNAME", "boss")
    assert app_module._ai_dr_resolve_system_executor_id() == boss.id


def test_resolve_falls_back_to_first_user_when_no_admin(app_ctx):
    """无 admin 账号时回退到最小 id 用户。"""
    first = _add_user("alice", role="user")
    _add_user("bob", role="user")
    assert app_module._ai_dr_resolve_system_executor_id() == first.id


def test_resolve_none_when_no_users(app_ctx):
    """库中无任何用户时返回 None（调用方据此跳过落库并告警）。"""
    assert app_module._ai_dr_resolve_system_executor_id() is None


def test_save_log_zero_resolves_to_admin(app_ctx):
    """executed_by=0（历史系统自动写法）兜底落到 admin 名下，外键不再失败。"""
    admin = _add_user("admin")
    entry = _make_entry(0)
    app_module._ai_dr_save_log(entry)
    row = AICleanupLog.query.filter_by(log_id=entry.log_id).first()
    assert row is not None
    assert row.executed_by == admin.id


def test_save_log_nonexistent_user_falls_back(app_ctx):
    """指向不存在用户的 id 同样兜底到系统归属账号。"""
    _add_user("admin")
    entry = _make_entry(999999)
    app_module._ai_dr_save_log(entry)
    row = AICleanupLog.query.filter_by(log_id=entry.log_id).first()
    assert row is not None
    assert row.executed_by == _add_user("admin").id if False else row.executed_by == \
        app_module._ai_dr_resolve_system_executor_id()


def test_save_log_valid_user_passthrough(app_ctx):
    """真实用户 id 原样落库，不改变既有行为。"""
    worker = _add_user("worker", role="user")
    entry = _make_entry(worker.id)
    app_module._ai_dr_save_log(entry)
    row = AICleanupLog.query.filter_by(log_id=entry.log_id).first()
    assert row is not None
    assert row.executed_by == worker.id


def test_save_log_no_users_skips_gracefully(app_ctx):
    """无任何用户时跳过落库不抛异常（返回原 entry，告警由调用方日志承载）。"""
    entry = _make_entry(0)
    result = app_module._ai_dr_save_log(entry)
    assert result is entry
    assert AICleanupLog.query.filter_by(log_id=entry.log_id).first() is None


def test_save_log_negative_skips_gracefully(app_ctx):
    """负数 executed_by 也归为系统自动，防止再触发外键异常。"""
    _add_user("admin")
    entry = _make_entry(-1)
    app_module._ai_dr_save_log(entry)
    row = AICleanupLog.query.filter_by(log_id=entry.log_id).first()
    assert row is not None
    assert row.executed_by == app_module._ai_dr_resolve_system_executor_id()


def test_notifications_preview_no_longer_writes_zero(app_ctx):
    """锚点：notifications.py 每日自动预览必须经解析函数取执行人，禁止写 0。"""
    src = (ROOT / "app" / "notifications.py").read_text(encoding="utf-8")
    # 历史错误写法整体消失
    assert "executed_by=0,  # 系统自动执行" not in src
    # 执行代码必须引用解析函数取值
    assert "executed_by=executor_id" in src
    assert "_ai_dr_resolve_system_executor_id" in src
