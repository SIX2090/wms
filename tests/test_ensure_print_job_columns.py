# -*- coding: utf-8 -*-
"""ensure_print_job_columns 回归测试（BUG-2026-08-20-001）。

背景：start_wms_offline.bat / start_wms_auto.bat 默认设置 WMS_NO_DB_TOUCH=1，
会跳过 auto_migrate_database；fix_db_columns.py 又不含 print_job 补列。
叠加导致线上 print_job 缺 printing_started_at / workstation_id / printer_id /
route_rule_id / source_event 列的库重启也补不上，打印代理 claim 一直报
no such column。

修复：app.py 新增 ensure_print_job_columns()，仿照 backfill_empty_warehouse_documents
用独立 sqlite 连接、独立于迁移开关无条件执行、幂等补列。

覆盖：
- 单测：构造缺列 print_job 表，调用直接补列
- 幂等：重复执行无变化、不报错
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


def _create_db_with_missing_columns(db_path: Path) -> Path:
    """构造一个缺 print_job 迁移列的旧库。

    注意：print_job 表本身已存在（老库场景）；故意只建核心列，
    缺 workstation_id/printer_id/route_rule_id/source_event/printing_started_at。
    """
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE warehouse (
                id INTEGER PRIMARY KEY, code TEXT, name TEXT,
                status TEXT, is_default INTEGER
            );
            CREATE TABLE print_job (
                id INTEGER PRIMARY KEY,
                job_type TEXT,
                target_id INTEGER,
                status TEXT DEFAULT 'pending',
                copies INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at DATETIME
            );
            INSERT INTO print_job(id, job_type, target_id, status, copies, created_at)
            VALUES (1, 'out_order', 9, 'pending', 1, datetime('now'));
            """
        )
    return db_path


def _cols(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        return [r[1] for r in conn.execute("PRAGMA table_info(print_job)").fetchall()]


# A9:no-test=reason=下三个 test_ 函数即被测函数的回归测试本体


def test_ensures_columns_are_added(tmp_path):
    """旧库缺 print_job 迁移列时，ensure_print_job_columns 补齐全部缺列。"""
    from app import ensure_print_job_columns
    db_path = _create_db_with_missing_columns(tmp_path / "inventory.db")
    ensure_print_job_columns(db_path=str(db_path))
    cols = _cols(db_path)
    for expected in ("workstation_id", "printer_id", "route_rule_id",
                     "source_event", "printing_started_at"):
        assert expected in cols, f"缺列未被补齐: {expected} in {cols}"
    # 原有数据不受影响
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT status FROM print_job WHERE id = 1").fetchone() == ("pending",)


def test_idempotent_repeat_run(tmp_path):
    """补列后重复执行无变化、不报错。"""
    from app import ensure_print_job_columns
    db_path = _create_db_with_missing_columns(tmp_path / "inventory.db")
    ensure_print_job_columns(db_path=str(db_path))
    before = _cols(db_path)
    ensure_print_job_columns(db_path=str(db_path))
    assert _cols(db_path) == before
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM print_job").fetchone() == (1,)


def test_missing_table_skips_without_error(tmp_path):
    """库中无 print_job 表（全新空库）时静默跳过不报错。"""
    from app import ensure_print_job_columns
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE warehouse (id INTEGER PRIMARY KEY, name TEXT)")
    ensure_print_job_columns(db_path=str(db_path))  # 不应抛异常
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='print_job'"
        ).fetchone() is None


def test_startup_wiring_runs_even_when_no_db_touch(tmp_path):
    """接线：生产启动脚本默认 WMS_NO_DB_TOUCH=1，会跳过 auto_migrate_database。
    ensure_print_job_columns 必须不受该开关影响。通过子进程 `import app`
    模拟完整启动，校验 print_job 缺列被补上（本次线上真 bug）。"""
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
        timeout=180,
    )
    assert result.returncode == 0, f"app import failed:\n{result.stdout}\n{result.stderr}"

    # 补列确认日志必须出现在启动输出
    assert "print_job 已补缺列（含 printing_started_at）" in result.stdout, (
        f"启动输出缺少补列完成日志:\n{result.stdout}\n{result.stderr}"
    )

    cols = _cols(db_path)
    assert "printing_started_at" in cols
    assert "workstation_id" in cols