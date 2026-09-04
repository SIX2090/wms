# -*- coding: utf-8 -*-
"""BUG-2026-09-04-002 回归测试：内置打印代理写库心跳遇锁降级（R4）。

现象：打印代理 _heartbeat 的 db.session.commit() 在 SQLite 写锁竞争时抛
`sqlite3.OperationalError: database is locked`，异常冒泡到 _agent_loop 后走
`log.exception()` 整段刷 SQLAlchemy traceback（2026-09-03 15:30:29 日志实证），
违反 AGENTS.md R4「busy_timeout + 低频重试 + 降级静默，禁止裸抛 traceback 刷屏」。

修复：
1) 新增 _is_db_locked(exc)：识别 SQLAlchemy 包装的 database is locked
   （str(exc) 与 exc.orig 双通道精确匹配 `database is locked`）；
2) _heartbeat 内 commit 包守卫：遇锁 → rollback + 单行节流 WARNING +
   返回 False（外层按 ~30s 低频重试）；非锁异常保持原样 re-raise；
3) _agent_loop 异常分支同判锁 → 单行节流告警继续轮询（与 _heartbeat 共享
   lock_warned 状态），不再刷 traceback。
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WMS_DATABASE_URI", "sqlite:///:memory:")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
import local_print_agent as lpa  # noqa: E402
from app import PrintWorkstation, db  # noqa: E402


@pytest.fixture()
def app_ctx():
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        yield


def _seed_builtin_ws():
    ws = PrintWorkstation(
        code=lpa.BUILTIN_WS_CODE, name=lpa.BUILTIN_WS_NAME,
        device_id=lpa.BUILTIN_WS_DEVICE_ID,
        status='online', enabled=True, auth_token='test-token',
        last_heartbeat=datetime.now(),
    )
    db.session.add(ws)
    db.session.commit()
    return ws


def _make_locked_error():
    """构造 SQLAlchemy 包装的 database is locked 异常（与生产日志同形态）。"""
    return OperationalError(
        "UPDATE print_workstation SET last_heartbeat=? WHERE print_workstation.id = ?",
        {},
        sqlite3.OperationalError("database is locked"),
    )


# ==================== _is_db_locked 判定 ====================

def test_is_db_locked_operational_error_with_orig():
    """SQLAlchemy OperationalError + orig 带锁标志 → True。"""
    assert lpa._is_db_locked(_make_locked_error()) is True


def test_is_db_locked_plain_sqlite_error():
    """裸 sqlite3.OperationalError('database is locked') → True。"""
    assert lpa._is_db_locked(sqlite3.OperationalError("database is locked")) is True


def test_is_db_locked_false_for_unrelated():
    """非锁异常 / 空值不得误判。"""
    assert lpa._is_db_locked(ValueError("boom")) is False
    assert lpa._is_db_locked(RuntimeError("database is locked")) is True  # 含标准标记仍算锁
    assert lpa._is_db_locked(None) is False
    assert lpa._is_db_locked(OperationalError("SELECT 1", {}, sqlite3.OperationalError("no such table: x"))) is False


# ==================== _heartbeat 遇锁降级 ====================

def test_heartbeat_locked_returns_false_without_traceback(app_ctx, monkeypatch):
    """心跳 commit 遇锁 → 返回 False、不抛异常、置 lock_warned 节流标记。"""
    _seed_builtin_ws()
    monkeypatch.setattr(lpa, "enumerate_local_printers", lambda: None)

    real_commit = db.session.commit
    calls = {"n": 0}

    def flaky_commit():
        if calls["n"] == 0:
            calls["n"] += 1
            raise _make_locked_error()
        return real_commit()

    monkeypatch.setattr(db.session, "commit", flaky_commit)

    state = {}
    # 第一次：遇锁降级，不抛异常
    assert lpa._heartbeat(state) is False
    assert state.get("lock_warned") is True


def test_heartbeat_recovers_after_lock(app_ctx, monkeypatch):
    """锁恢复后下一轮心跳正常返回 True 并清除节流标记。"""
    _seed_builtin_ws()
    monkeypatch.setattr(lpa, "enumerate_local_printers", lambda: None)

    real_commit = db.session.commit
    calls = {"n": 0}

    def flaky_commit():
        if calls["n"] == 0:
            calls["n"] += 1
            raise _make_locked_error()
        return real_commit()

    monkeypatch.setattr(db.session, "commit", flaky_commit)

    state = {}
    assert lpa._heartbeat(state) is False
    assert state.get("lock_warned") is True
    # 第二轮恢复
    assert lpa._heartbeat(state) is True
    assert state.get("lock_warned") is False


def test_heartbeat_rethrows_non_lock_error(app_ctx, monkeypatch):
    """非锁异常必须保持原行为向上抛（由 _agent_loop 兜底），不得被静默吞掉。"""
    _seed_builtin_ws()
    monkeypatch.setattr(lpa, "enumerate_local_printers", lambda: None)

    def bad_commit():
        raise ValueError("unexpected business error")

    monkeypatch.setattr(db.session, "commit", bad_commit)
    with pytest.raises(ValueError):
        lpa._heartbeat({})


def test_lock_degrade_anchors():
    """锚点：锁降级单行告警与节流标记必须存在于打印代理源文本，防实现回退。"""
    src = (ROOT / "app" / "local_print_agent.py").read_text(encoding="utf-8")
    assert "_is_db_locked" in src
    assert "database is locked" in src
    assert "lock_warned" in src
    assert "本轮心跳降级跳过" in src
