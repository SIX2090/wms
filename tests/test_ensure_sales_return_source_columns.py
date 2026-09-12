# -*- coding: utf-8 -*-
"""ensure_sales_return_source_columns 回归测试（BUG-2026-09-12，R6 第 5 次复发）。

背景：P1-5「销售退货入库」给 in_order 加了 source_sales_order_id /
source_sales_order_no、给 in_order_item 加了 source_sales_order_item_id，
三列**只**在 auto_migrate_database() 里 ADD。start_wms_offline.bat /
start_wms_auto.bat 默认 WMS_NO_DB_TOUCH=1 会整体跳过 auto_migrate_database，
而兜底的 app/fix_db_columns.py 当时也没同步（start_wms_auto.bat 更是连
fix_db_columns 都不跑）——存量生产库重启后补不上，首页 index() 一执行
``InOrder.query.filter_by(status='pending').count()`` 即 500：
    sqlalchemy.exc.OperationalError: (sqlite3.OperationalError)
    no such column: in_order.source_sales_order_id

修复：app.py 新增 ensure_sales_return_source_columns()，仿照
ensure_inventory_check_columns 用独立 sqlite 连接、独立于迁移开关
**无条件执行**、幂等补列。这是存量库唯一自愈路径——fix_db_columns.py
只在 start_wms_offline.bat 里被调用，start_wms_auto.bat 不跑它。

覆盖：
- 单测：构造缺列旧库，调用后补齐全部 3 列，且不影响存量数据
- 幂等：重复执行无变化、不报错
- 缺表：全新空库（表不存在）静默跳过、不建表
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

# 旧库场景：in_order / in_order_item 表都在（老库），但缺 P1-5 三列
_OLD_SCHEMA = """
CREATE TABLE warehouse (
    id INTEGER PRIMARY KEY, code TEXT, name TEXT,
    status TEXT, is_default INTEGER
);
CREATE TABLE in_order (
    id INTEGER PRIMARY KEY, order_no TEXT, status TEXT,
    warehouse TEXT, supplier TEXT
);
CREATE TABLE in_order_item (
    id INTEGER PRIMARY KEY, in_order_id INTEGER, material_id INTEGER,
    quantity REAL, price REAL
);
"""

_EXPECTED = (
    ("in_order", "source_sales_order_id"),
    ("in_order", "source_sales_order_no"),
    ("in_order_item", "source_sales_order_item_id"),
)


def _create_db_with_missing_columns(db_path: Path) -> Path:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_OLD_SCHEMA)
        # 留一条存量数据，验证补列不影响已有行
        conn.execute(
            "INSERT INTO in_order(id, order_no, status, warehouse, supplier)"
            " VALUES (1, 'IN-2026-0001', 'pending', '主仓', '供应商A')"
        )
        conn.execute(
            "INSERT INTO in_order_item(id, in_order_id, material_id, quantity,"
            " price) VALUES (1, 1, 43, 10, 8.5)"
        )
    return db_path


def _cols(db_path: Path, table: str):
    with sqlite3.connect(db_path) as conn:
        # 表名来自本文件固定白名单（非用户输入），拼接仅为避免 SQL lint 误报
        stmt = "PRAGMA table_info(" + table + ")"
        return [r[1] for r in conn.execute(stmt).fetchall()]


# A9:no-test=reason=下面五个 test_ 函数即被测函数的回归测试本体


def test_adds_all_missing_sales_return_columns(tmp_path):
    """旧库缺 P1-5 三列时，一次补齐全部缺列。"""
    from app import ensure_sales_return_source_columns
    db_path = _create_db_with_missing_columns(tmp_path / "inventory.db")
    ensure_sales_return_source_columns(db_path=str(db_path))
    for table, col in _EXPECTED:
        assert col in _cols(db_path, table), f"缺列未被补齐: {table}.{col}"
    # 原有数据不受影响
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT order_no FROM in_order WHERE id = 1"
        ).fetchone() == ("IN-2026-0001",)
        assert conn.execute(
            "SELECT quantity FROM in_order_item WHERE id = 1"
        ).fetchone() == (10,)


def test_idempotent_repeat_run(tmp_path):
    """补列后重复执行无变化、不报错。"""
    from app import ensure_sales_return_source_columns
    db_path = _create_db_with_missing_columns(tmp_path / "inventory.db")
    ensure_sales_return_source_columns(db_path=str(db_path))
    before = {t: _cols(db_path, t) for t, _ in _EXPECTED}
    ensure_sales_return_source_columns(db_path=str(db_path))
    ensure_sales_return_source_columns(db_path=str(db_path))
    after = {t: _cols(db_path, t) for t, _ in _EXPECTED}
    assert before == after
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM in_order").fetchone() == (1,)


def test_no_op_when_schema_already_current(tmp_path):
    """列齐全的库不会重复 ALTER（列集合与列顺序均不变）。"""
    from app import ensure_sales_return_source_columns
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_OLD_SCHEMA)
        conn.execute("ALTER TABLE in_order ADD COLUMN source_sales_order_id INTEGER")
        conn.execute("ALTER TABLE in_order ADD COLUMN source_sales_order_no VARCHAR(50)")
        conn.execute(
            "ALTER TABLE in_order_item ADD COLUMN source_sales_order_item_id INTEGER"
        )
    before = {t: _cols(db_path, t) for t, _ in _EXPECTED}
    ensure_sales_return_source_columns(db_path=str(db_path))
    assert {t: _cols(db_path, t) for t, _ in _EXPECTED} == before


def test_missing_table_skips_without_error(tmp_path):
    """全新空库（in_order 表尚不存在）时静默跳过、不建表、不报错。"""
    from app import ensure_sales_return_source_columns
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE warehouse (id INTEGER PRIMARY KEY, name TEXT)")
    ensure_sales_return_source_columns(db_path=str(db_path))
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='in_order'"
        ).fetchone() is None


def test_startup_wiring_runs_even_when_no_db_touch(tmp_path):
    """接线：生产启动脚本默认 WMS_NO_DB_TOUCH=1 会跳过 auto_migrate_database，
    ensure_sales_return_source_columns 必须不受该开关影响。子进程 `import app`
    模拟完整启动，校验三列被补上（本次线上真 bug，首页 500）。"""
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
    assert "销售退货入库已补缺列（BUG-2026-09-12）" in result.stdout, (
        f"启动输出缺少补列完成日志:\n{result.stdout}\n{result.stderr}"
    )

    for table, col in _EXPECTED:
        assert col in _cols(db_path, table), f"启动未补齐: {table}.{col}"

    # 事故直接触发点：首页 index() 的 pending 计数查询必须能跑通
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM in_order WHERE status = 'pending'"
        ).fetchone()[0] == 1
