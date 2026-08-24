# -*- coding: utf-8 -*-
"""BUG-2026-08-24-003 回归：SQLite connect 期 PRAGMA 注册不得被 WMS_NO_DB_TOUCH 跳过。

背景：connect 期 PRAGMA（WAL/synchronous/busy_timeout/foreign_keys）原本放在
initialize_database() 的 startup_db_upgrade_disabled() 早退之后。生产启动脚本
（start_wms_offline.bat/start_wms_auto.bat）默认 WMS_NO_DB_TOUCH=1，使
initialize_database() 提前 return，监听器从不注册，ORM 连接退回 sqlite3 默认
5s busy_timeout——打印心跳等高频写与其他写事务相撞即抛 database is locked（心跳 500）。

修复：PRAGMA 注册拆为 _register_sqlite_pragma_listener()，并在早退之前无条件调用。

覆盖：
- 早退路径（startup_db_upgrade_disabled=True）下 initialize_database 仍调用 PRAGMA 注册
- connect 处理器真实生效（busy_timeout=30000、foreign_keys=ON）且函数幂等
"""
from __future__ import annotations

import os
import sqlite3
import sys
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

import app as app_module  # noqa: E402
from app import db  # noqa: E402


@pytest.fixture()
def app_ctx():
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        yield


def test_pragma_registered_despite_no_db_touch(app_ctx, monkeypatch):
    """早退路径（startup_db_upgrade_disabled=True）下 initialize_database 仍调用
    PRAGMA 注册——这是本 bug 的核心（此前注册在早退之后，生产 WMS_NO_DB_TOUCH=1 被跳过）。"""
    called = []
    monkeypatch.setattr(app_module, '_register_sqlite_pragma_listener',
                        lambda: called.append(True))
    monkeypatch.setattr(app_module, 'startup_db_upgrade_disabled', lambda: True)

    app_module.initialize_database()  # 早退路径

    assert called, 'WMS_NO_DB_TOUCH=1 时 PRAGMA 注册被跳过（database is locked 根因）'


def test_register_sqlite_pragma_listener_connect_handler(app_ctx, monkeypatch):
    """connect 处理器真实注册且生效：作用于原始连接后 busy_timeout=30000、
    foreign_keys=ON（非 sqlite3 默认 5000ms / OFF）；重复调用幂等不重复注册。"""
    from sqlalchemy import event as sa_event

    registered = []
    real_listens_for = sa_event.listens_for

    def spy(target, name):
        deco = real_listens_for(target, name)

        def wrapper(fn):
            registered.append((target, name, fn))
            return deco(fn)

        return wrapper

    monkeypatch.setattr(sa_event, 'listens_for', spy)
    monkeypatch.setattr(app_module, '_SQLITE_PRAGMA_REGISTERED', False)

    app_module._register_sqlite_pragma_listener()
    assert app_module._SQLITE_PRAGMA_REGISTERED is True

    connect_handlers = [fn for _t, name, fn in registered if name == 'connect']
    assert len(connect_handlers) == 1, '应注册且仅注册一次 connect 处理器'

    # 幂等：第二次调用（标记已置位）不再重复注册
    app_module._register_sqlite_pragma_listener()
    connect_handlers_after = [fn for _t, name, fn in registered if name == 'connect']
    assert len(connect_handlers_after) == 1

    # 模拟 connect 事件作用于原始 sqlite3 连接，验证 PRAGMA 真正生效
    raw = sqlite3.connect(':memory:')
    try:
        connect_handlers[0](raw, None)
        assert raw.execute('PRAGMA busy_timeout').fetchone()[0] == 30000
        assert raw.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    finally:
        raw.close()
