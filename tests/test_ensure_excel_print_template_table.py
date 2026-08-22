# -*- coding: utf-8 -*-
"""ensure_excel_print_template_table 回归测试（BUG-2026-08-22-001）。

背景：ExcelPrintTemplate 模型（表 excel_print_template）只挂在
db.create_all()（initialize_database）里，而 start_wms_offline.bat /
start_wms_auto.bat 默认 WMS_NO_DB_TOUCH=1 会跳过
initialize_database()/auto_migrate_database()，强制运行的 fix_db_columns.py
又不含该表——功能上线前创建的存量库重启也建不出表，打开「Excel打印模板中心」
（/print_templates）即抛 no such table: excel_print_template → 500。

修复：app.py 新增 ensure_excel_print_template_table()，仿照
ensure_print_job_columns 用独立 sqlite 连接、独立于迁移开关无条件执行、
幂等建表（CREATE TABLE/INDEX IF NOT EXISTS，已有表与数据一律不动）。

覆盖：
- 单测：存量老库缺表时直接补建（列与索引齐全）
- 幂等：重复执行无变化、已有数据不受影响
- 已有表：表已存在时静默跳过、数据不动
- 接线：子进程 `import app` + WMS_NO_DB_TOUCH=1 模拟生产启动，缺表被补建
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

MODEL_COLUMNS = (
    "id", "name", "target_type", "target_code", "template_type",
    "excel_template_path", "is_default", "created_at", "updated_at",
)


def _create_old_db_without_table(db_path: Path) -> Path:
    """构造一个功能上线前的存量老库：有业务表、无 excel_print_template。"""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE warehouse (
                id INTEGER PRIMARY KEY, code TEXT, name TEXT,
                status TEXT, is_default INTEGER
            );
            CREATE TABLE "user" (
                id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT
            );
            """
        )
    return db_path


def _table_exists(db_path: Path) -> bool:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='excel_print_template'"
        ).fetchone() is not None


def _cols(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        return [r[1] for r in conn.execute("PRAGMA table_info(excel_print_template)").fetchall()]


def _indexes(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        return [r[1] for r in conn.execute("PRAGMA index_list(excel_print_template)").fetchall()]


# A9:no-test=reason=下四个 test_ 函数即被测函数的回归测试本体


def test_missing_table_is_created(tmp_path):
    """存量老库缺 excel_print_template 表时补建，列与模型一致、索引齐全。"""
    from app import ensure_excel_print_template_table
    db_path = _create_old_db_without_table(tmp_path / "inventory.db")
    assert not _table_exists(db_path)
    ensure_excel_print_template_table(db_path=str(db_path))
    assert _table_exists(db_path)
    cols = _cols(db_path)
    for expected in MODEL_COLUMNS:
        assert expected in cols, f"缺列: {expected} in {cols}"
    indexes = _indexes(db_path)
    assert "ix_excel_print_template_target_type" in indexes
    assert "ix_excel_print_template_target_code" in indexes
    # 原有业务表不受影响
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='warehouse'"
        ).fetchone() is not None


def test_idempotent_repeat_run(tmp_path):
    """补建后重复执行无变化、不报错，已写入的数据保留。"""
    from app import ensure_excel_print_template_table
    db_path = _create_old_db_without_table(tmp_path / "inventory.db")
    ensure_excel_print_template_table(db_path=str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO excel_print_template "
            "(name, target_type, target_code, template_type, excel_template_path, is_default) "
            "VALUES ('测试模板', 'document', 'in_order', 'excel', 'uploads/t.xlsx', 1)"
        )
    before = _cols(db_path)
    ensure_excel_print_template_table(db_path=str(db_path))
    assert _cols(db_path) == before
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT name FROM excel_print_template WHERE id = 1"
        ).fetchone() == ("测试模板",)


def test_existing_table_untouched(tmp_path):
    """表已存在（含数据）时静默跳过，结构与数据一律不动。"""
    from app import ensure_excel_print_template_table
    db_path = _create_old_db_without_table(tmp_path / "inventory.db")
    with sqlite3.connect(db_path) as conn:
        # 老表结构（无 updated_at 列的极端漂移场景）：函数不得试图改表
        conn.execute(
            "CREATE TABLE excel_print_template ("
            "id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, "
            "target_type VARCHAR(30) NOT NULL, target_code VARCHAR(80) NOT NULL, "
            "template_type VARCHAR(20) NOT NULL, excel_template_path VARCHAR(500) NOT NULL)"
        )
        conn.execute(
            "INSERT INTO excel_print_template "
            "(name, target_type, target_code, template_type, excel_template_path) "
            "VALUES ('老模板', 'list', 'inventory', 'excel', 'uploads/old.xlsx')"
        )
    ensure_excel_print_template_table(db_path=str(db_path))  # 不应抛异常
    assert "updated_at" not in _cols(db_path)  # 结构未被改动
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT name FROM excel_print_template WHERE id = 1"
        ).fetchone() == ("老模板",)


def test_startup_wiring_creates_table_even_when_no_db_touch(tmp_path):
    """接线：生产启动脚本默认 WMS_NO_DB_TOUCH=1，会跳过 create_all。
    ensure_excel_print_template_table 必须不受该开关影响。通过子进程
    `import app` 模拟完整启动，校验缺表被补建（本次线上真 bug）。"""
    db_path = _create_old_db_without_table(tmp_path / "inventory.db")

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
        timeout=180,
    )
    assert result.returncode == 0, f"app import failed:\n{result.stdout}\n{result.stderr}"

    # 补建确认日志必须出现在启动输出
    assert "excel_print_template 缺表已补建" in result.stdout, (
        f"启动输出缺少建表完成日志:\n{result.stdout}\n{result.stderr}"
    )
    assert _table_exists(db_path)
