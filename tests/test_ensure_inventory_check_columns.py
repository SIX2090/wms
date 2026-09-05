# -*- coding: utf-8 -*-
"""ensure_inventory_check_columns 回归测试（BUG-2026-09-05-001）。

背景：INV-BATCH-001-A / INV-BATCH-002 引入的盘点域迁移列
（inventory_check.frozen_at、inventory_check_item.counted_by / counted_at /
area、inventory_check_scan.check_id、inventory_check_scan_item.area）
只在 auto_migrate_database() 里 ADD COLUMN。start_wms_offline.bat 等启动
脚本默认 WMS_NO_DB_TOUCH=1 会跳过 auto_migrate_database，fix_db_columns.py
又不含盘点表补列——存量库重启也补不上，物料编辑保存级联统计查询
InventoryCheckItem 即报
sqlite3.OperationalError: no such column: inventory_check_item.counted_by。

修复：app.py 新增 ensure_inventory_check_columns()，仿照 ensure_print_job_columns
用独立 sqlite 连接、独立于迁移开关无条件执行、幂等补列（R6：一次性覆盖
盘点域全部新增列，而非只补报错的那一列）。

覆盖：
- 单测：构造缺列旧库，调用后补齐全部 6 列
- 幂等：重复执行无变化、不报错、不动数据
- 缺表：全新空库（表不存在）静默跳过
- 接线：子进程 `import app` + WMS_NO_DB_TOUCH=1 模拟生产启动，缺列被补上
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

# 旧库场景：盘点相关表都已存在（老库），但缺 INV-BATCH 系列新增列
_OLD_SCHEMA = """
CREATE TABLE warehouse (
    id INTEGER PRIMARY KEY, code TEXT, name TEXT,
    status TEXT, is_default INTEGER
);
CREATE TABLE inventory_check (
    id INTEGER PRIMARY KEY, check_no TEXT, status TEXT, warehouse TEXT
);
CREATE TABLE inventory_check_item (
    id INTEGER PRIMARY KEY, inventory_check_id INTEGER, material_id INTEGER,
    system_stock REAL, actual_stock REAL, difference REAL, reason TEXT
);
CREATE TABLE inventory_check_scan (
    id INTEGER PRIMARY KEY, scan_no TEXT, warehouse TEXT, status TEXT
);
CREATE TABLE inventory_check_scan_item (
    id INTEGER PRIMARY KEY, scan_id INTEGER, material_id INTEGER,
    actual_stock REAL
);
"""

_EXPECTED = (
    ("inventory_check", "frozen_at"),
    ("inventory_check_item", "counted_by"),
    ("inventory_check_item", "counted_at"),
    ("inventory_check_item", "area"),
    ("inventory_check_scan", "check_id"),
    ("inventory_check_scan_item", "area"),
)


def _create_db_with_missing_columns(db_path: Path) -> Path:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_OLD_SCHEMA)
        # 留一条存量数据，验证补列不影响已有行
        conn.execute(
            "INSERT INTO inventory_check_item"
            "(id, inventory_check_id, material_id, system_stock, actual_stock,"
            " difference, reason) VALUES (1, 1, 43, 10, 8, -2, '旧数据')"
        )
    return db_path


def _cols(db_path: Path, table: str):
    with sqlite3.connect(db_path) as conn:
        # 表名来自本文件固定白名单（非用户输入），拼接仅为避免 SQL lint 误报
        stmt = "PRAGMA table_info(" + table + ")"
        return [r[1] for r in conn.execute(stmt).fetchall()]


# A9:no-test=reason=下面五个 test_ 函数即被测函数的回归测试本体


def test_adds_all_missing_inventory_check_columns(tmp_path):
    """旧库缺盘点域迁移列时，一次补齐全部缺列。"""
    from app import ensure_inventory_check_columns
    db_path = _create_db_with_missing_columns(tmp_path / "inventory.db")
    ensure_inventory_check_columns(db_path=str(db_path))
    for table, col in _EXPECTED:
        assert col in _cols(db_path, table), f"缺列未被补齐: {table}.{col}"
    # 原有数据不受影响
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT system_stock FROM inventory_check_item WHERE id = 1"
        ).fetchone() == (10,)


def test_idempotent_repeat_run(tmp_path):
    """补列后重复执行无变化、不报错。"""
    from app import ensure_inventory_check_columns
    db_path = _create_db_with_missing_columns(tmp_path / "inventory.db")
    ensure_inventory_check_columns(db_path=str(db_path))
    before = {t: _cols(db_path, t) for t, _ in _EXPECTED}
    ensure_inventory_check_columns(db_path=str(db_path))
    ensure_inventory_check_columns(db_path=str(db_path))
    after = {t: _cols(db_path, t) for t, _ in _EXPECTED}
    assert before == after
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM inventory_check_item").fetchone() == (1,)


def test_no_op_when_schema_already_current(tmp_path):
    """列齐全的库不会重复 ALTER（列集合与列顺序均不变）。"""
    from app import ensure_inventory_check_columns
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_OLD_SCHEMA)
        for table, col in _EXPECTED:
            conn.execute("ALTER TABLE " + table + " ADD COLUMN " + col + " TEXT")
    before = {t: _cols(db_path, t) for t, _ in _EXPECTED}
    ensure_inventory_check_columns(db_path=str(db_path))
    assert {t: _cols(db_path, t) for t, _ in _EXPECTED} == before


def test_missing_table_skips_without_error(tmp_path):
    """全新空库（盘点表尚不存在）时静默跳过、不建表、不报错。"""
    from app import ensure_inventory_check_columns
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE warehouse (id INTEGER PRIMARY KEY, name TEXT)")
    ensure_inventory_check_columns(db_path=str(db_path))
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name='inventory_check_item'"
        ).fetchone() is None


def test_startup_wiring_runs_even_when_no_db_touch(tmp_path):
    """接线：生产启动脚本默认 WMS_NO_DB_TOUCH=1 会跳过 auto_migrate_database，
    ensure_inventory_check_columns 必须不受该开关影响。子进程 `import app`
    模拟完整启动，校验盘点域缺列被补上（本次线上真 bug）。"""
    db_path = _create_db_with_missing_columns(tmp_path / "inventory.db")

    env = dict(os.environ)
    env["WMS_NO_DB_TOUCH"] = "1"
    env["WMS_SKIP_STARTUP_DB_UPGRADE"] = "1"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["WMS_BOOTSTRAP_PASSWORD"] = "admin"
    env["WMS_SKIP_AUTO_UPDATE"] = "1"
    env["WMS_DEBUG"] = "0"
    env["WMS_ALLOW_AUTO_SECRET_KEY"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=str(APP_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"app import failed:\n{result.stdout}\n{result.stderr}"

    # 补列确认日志必须出现在启动输出
    assert "盘点域已补缺列（BUG-2026-09-05-001）" in result.stdout, (
        f"启动输出缺少补列完成日志:\n{result.stdout}\n{result.stderr}"
    )

    for table, col in _EXPECTED:
        assert col in _cols(db_path, table), f"启动未补齐: {table}.{col}"
