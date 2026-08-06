# -*- coding: utf-8 -*-
"""回归测试：auto_migrate_database() 必须使用 config 中的数据库路径。

根因（BUG-2026-08-06-001）：auto_migrate_database() 原先在 Flask config
加载之前执行，且使用硬编码路径 app/instance/inventory.db 检查数据库，
与 SQLAlchemy 实际使用的数据库（由 SQLALCHEMY_DATABASE_URI 决定）不一致，
导致老库启动时 out_order.picker 等字段未被添加，访问领料单直接报
「no such column: out_order.picker」。

修复：将 config 加载移到迁移调用之前，并新增 _resolve_sqlite_db_path()
从 app.config['SQLALCHEMY_DATABASE_URI'] 解析正确的数据库路径。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")

from app import (  # noqa: E402
    _resolve_sqlite_db_path,
    app as flask_app,
)


def test_resolve_absolute_sqlite_path():
    """绝对 sqlite:/// 路径应原样返回。"""
    p = _resolve_sqlite_db_path("sqlite:////tmp/legacy.db", instance_path="/unused")
    assert p == "/tmp/legacy.db"


def test_resolve_relative_sqlite_path_joins_instance_path():
    """相对 sqlite:/// 路径应拼接到 instance_path。"""
    p = _resolve_sqlite_db_path("sqlite:///inventory.db", instance_path="/data/instance")
    assert p == "/data/instance/inventory.db"


def test_resolve_memory_db_returns_none():
    """内存库不应解析出文件路径。"""
    assert _resolve_sqlite_db_path("sqlite:///:memory:", instance_path="/x") is None


def test_resolve_non_sqlite_returns_none():
    """非 sqlite 数据库不应解析 sqlite 文件路径。"""
    assert _resolve_sqlite_db_path("postgresql://u:p@h/db", instance_path="/x") is None


def test_resolve_uses_app_config_when_uri_none():
    """uri 缺省时读取 app.config.get('SQLALCHEMY_DATABASE_URI')。"""
    old = flask_app.config.get("SQLALCHEMY_DATABASE_URI")
    try:
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cfg_inventory.db"
        p = _resolve_sqlite_db_path(instance_path="/cfg/instance")
        assert p == "/cfg/instance/cfg_inventory.db"
    finally:
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = old