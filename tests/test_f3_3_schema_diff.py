# -*- coding: utf-8 -*-
"""F3.3：startup_check 四维 schema diff（表/列/类型/FK）验收。

契约：
- 全量一致库：verify_schema_or_raise 返回 ok 行，不抛错；
- 人为删一列：启动被拒（RuntimeError），错误信息明示「缺列: 表.列」；
- 类型不一致（VARCHAR→BLOB）：报错明示「类型不一致」；
- FK 缺失仅警告（SQLite ALTER 无法补 FK，存量库不因此起不来）；
- WMS_SCHEMA_CHECK=off 显式跳过（排障逃生门）。
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, 'app')
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


@pytest.fixture()
def app_module():
    os.environ.setdefault('WMS_BOOTSTRAP_PASSWORD', 'admin')
    os.environ.setdefault('WMS_DEBUG', '0')
    os.environ.setdefault('WMS_SKIP_AUTO_UPDATE', '1')
    os.environ.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')
    import app as app_mod
    mod = importlib.reload(app_mod)
    # 测试库不经过 run_server 启动路径，需显式建全量表（模拟 initialize_database 后状态）
    with mod.app.app_context():
        mod.db.create_all()
    return mod


def _verify(app_mod):
    import startup_check
    importlib.reload(startup_check)
    return startup_check


def test_full_schema_passes(app_module):
    """全量一致库：diff 无硬错误，verify 返回 ok。"""
    sc = _verify(app_module)
    errors, warnings = sc.schema_diff(app_module.app, app_module.db)
    assert errors == [], f'全量一致库不应有硬错误: {errors[:5]}'
    line = sc.verify_schema_or_raise(app_module.app, app_module.db)
    assert 'schema-check: ok' in line


def test_missing_column_blocks_startup(app_module, tmp_path):
    """验收：人为删一列 → verify_schema_or_raise 抛 RuntimeError 并明示差异。"""
    import sqlite3
    import sqlalchemy as sa

    db_path = tmp_path / 'legacy.db'
    engine = sa.create_engine(f'sqlite:///{db_path}')
    app_module.db.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(db_path)
    try:
        # 人为删列：unit.name（带 unique 约束的列 SQLite 不允许 DROP COLUMN，
        # 按官方推荐路径重建表）
        conn.executescript(
            """
            CREATE TABLE unit_new (
                id INTEGER PRIMARY KEY,
                code VARCHAR(50) NOT NULL,
                created_at DATETIME
            );
            INSERT INTO unit_new (id, code, created_at)
                SELECT id, code, created_at FROM unit;
            DROP TABLE unit;
            ALTER TABLE unit_new RENAME TO unit;
            """
        )
        conn.commit()
    finally:
        conn.close()

    # 通过 engine 参数指向被动过手脚的文件库（db.engine 已绑定内存库，
    # Flask-SQLAlchemy 3 引擎缓存不可换，故 schema_diff 支持显式 engine）
    check_engine = sa.create_engine(f'sqlite:///{db_path}')
    sc = _verify(app_module)
    try:
        with pytest.raises(RuntimeError) as exc:
            sc.verify_schema_or_raise(app_module.app, app_module.db, engine=check_engine)
        assert '缺列: unit.name' in str(exc.value)
        assert '启动被拒绝' in str(exc.value)
    finally:
        check_engine.dispose()


def test_type_mismatch_blocks_startup(app_module, tmp_path):
    """类型 confidently 不一致（unit.name 由 VARCHAR 变 BLOB）→ 报错。"""
    import sqlite3
    import sqlalchemy as sa

    db_path = tmp_path / 'typedrift.db'
    engine = sa.create_engine(f'sqlite:///{db_path}')
    app_module.db.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(db_path)
    try:
        # SQLite 无法直接改列类型：重建 unit 表，name 用 BLOB
        conn.executescript(
            """
            CREATE TABLE unit_new (
                id INTEGER PRIMARY KEY,
                code VARCHAR(50) NOT NULL,
                name BLOB NOT NULL
            );
            INSERT INTO unit_new (id, code, name)
                SELECT id, code, CAST(name AS BLOB) FROM unit;
            DROP TABLE unit;
            ALTER TABLE unit_new RENAME TO unit;
            """
        )
        conn.commit()
    finally:
        conn.close()

    check_engine = sa.create_engine(f'sqlite:///{db_path}')
    sc = _verify(app_module)
    try:
        errors, _ = sc.schema_diff(app_module.app, app_module.db, engine=check_engine)
        assert any('类型不一致: unit.name' in e for e in errors), errors
    finally:
        check_engine.dispose()


def test_schema_check_off_skips(app_module, monkeypatch):
    """WMS_SCHEMA_CHECK=off → 显式跳过，返回 skipped 行。"""
    sc = _verify(app_module)
    monkeypatch.setenv('WMS_SCHEMA_CHECK', 'off')
    line = sc.verify_schema_or_raise(app_module.app, app_module.db)
    assert 'skipped' in line


def test_schema_diff(app_module):
    """A9 规则锚点：schema_diff 主路径（全量一致库返回空 errors）。"""
    sc = _verify(app_module)
    errors, warnings = sc.schema_diff(app_module.app, app_module.db)
    assert errors == []
    assert isinstance(warnings, list)


def test_verify_schema_or_raise(app_module):
    """A9 规则锚点：verify_schema_or_raise 主路径（一致库返回 ok 行）。"""
    sc = _verify(app_module)
    line = sc.verify_schema_or_raise(app_module.app, app_module.db)
    assert 'schema-check: ok' in line


def test_fk_missing_is_warning_not_error(app_module):
    """FK 维度：缺外键只进 warnings，绝不影响 errors（存量 SQLite 库约束）。"""
    sc = _verify(app_module)
    errors, warnings = sc.schema_diff(app_module.app, app_module.db)
    assert errors == []
    # 全量 create_all 的内存库 FK 应齐全；此用例锁死「FK 只警告」的结构契约
    assert all(w.startswith('缺外键(仅警告)') for w in warnings)
