# -*- coding: utf-8 -*-
"""ensure_department_table 回归测试（BUG-2026-09-12，移动端领料部门）。

Department 模型只挂在 db.create_all()（initialize_database）里，而
start_wms_*.bat 默认 WMS_NO_DB_TOUCH=1 会跳过它，fix_db_columns.py 又完全
不含该表——功能上线前创建的存量库重启也建不出表，移动端「扫码出库」拉取
部门列表（GET /api/departments）即抛 no such table: department → 500。

修复：app.py 新增 ensure_department_table()，仿照
ensure_excel_print_template_table 用独立 sqlite 连接、独立于迁移开关
无条件执行、幂等（CREATE TABLE IF NOT EXISTS），已有表与数据一律不动。

覆盖：
- 缺表：老库无 department 表 → 补建，列与 Department 模型一致
- 已有表：含数据时绝不重建、不删数据
- 接线：子进程 `import app` + WMS_NO_DB_TOUCH=1 模拟生产启动，表被补建
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

# Department 模型字段（app/app.py class Department）
_DEPARTMENT_COLUMNS = ("id", "code", "name", "status", "remark", "created_at")


def _cols(db_path: Path, table: str):
    with sqlite3.connect(db_path) as conn:
        # 表名来自本文件固定白名单（非用户输入），拼接仅为避免 SQL lint 误报
        stmt = "PRAGMA table_info(" + table + ")"
        return [r[1] for r in conn.execute(stmt).fetchall()]


def _table_exists(db_path: Path, table: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone() is not None


# A9:no-test=reason=下面三个 test_ 函数即被测函数的回归测试本体


def test_ensure_department_table(tmp_path):
    """老库无 department 表 → 补建，列与 Department 模型一致。"""
    from app import ensure_department_table
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE out_order (id INTEGER PRIMARY KEY, order_no TEXT)")
    assert not _table_exists(db_path, "department")

    ensure_department_table(db_path=str(db_path))

    assert _table_exists(db_path, "department"), "department 表未被补建"
    assert _cols(db_path, "department") == list(_DEPARTMENT_COLUMNS)


def test_ensure_department_table_keeps_existing_data(tmp_path):
    """已有 department 表（含数据）时绝不重建、不删数据。"""
    from app import ensure_department_table
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE department (id INTEGER PRIMARY KEY, code TEXT, name TEXT,"
            " status TEXT, remark TEXT, created_at DATETIME)"
        )
        conn.execute(
            "INSERT INTO department(id, code, name, status) VALUES (1, 'D01', '生产部', 'active')"
        )

    ensure_department_table(db_path=str(db_path))

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM department").fetchone() == (1,)
        assert conn.execute("SELECT name FROM department WHERE id = 1").fetchone() == ("生产部",)


def test_ensure_department_table_startup_wiring_no_db_touch(tmp_path):
    """接线：WMS_NO_DB_TOUCH=1 会跳过 create_all，本函数必须不受该开关影响。"""
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE out_order (id INTEGER PRIMARY KEY, order_no TEXT)")

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
    assert "department 缺表已补建（BUG-2026-09-12）" in result.stdout, (
        f"启动输出缺少 department 建表日志:\n{result.stdout}\n{result.stderr}"
    )
    assert _table_exists(db_path, "department"), "启动未补建 department 表"
