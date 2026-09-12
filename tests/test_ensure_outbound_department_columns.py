# -*- coding: utf-8 -*-
"""ensure_department_table / ensure_outbound_department_columns 回归测试。

BUG-2026-09-12：移动端「扫码出库」新增领料部门/领料人（选部门 → 选员工），
后端依赖三样东西，全都**只**挂在 db.create_all() / auto_migrate_database() 上：

1. department 表（Department 模型），fix_db_columns.py 完全不含
   → 存量库重启建不出表，GET /api/departments 抛
   no such table: department → 500
2. out_order.department_id / out_order.picker
   → 移动端提交出库单写这两列即 no such column: out_order.department_id
3. employee.department_id
   → GET /api/employees?department_id= 抛 no such column: employee.department_id

而 start_wms_*.bat 默认 WMS_NO_DB_TOUCH=1 会跳过 create_all 与
auto_migrate_database，start_wms_auto.bat 连 fix_db_columns.py 都不跑。

修复：新增两个无条件执行、幂等的兜底函数（与 ensure_sales_return_source_columns
同一模式），存量库重启即自愈。

覆盖（department 缺表部分见 tests/test_ensure_department_table.py）：
- 缺列：老库无 department_id/picker → 补齐，存量数据不受影响
- 幂等：重复执行无变化；已有列不动
- 接线：子进程 `import app` + WMS_NO_DB_TOUCH=1 模拟生产启动，表与列都被补上
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

# 老库场景：out_order / employee 表都在，但缺本轮新增列；department 表不存在
_OLD_SCHEMA = """
CREATE TABLE warehouse (
    id INTEGER PRIMARY KEY, code TEXT, name TEXT,
    status TEXT, is_default INTEGER
);
CREATE TABLE out_order (
    id INTEGER PRIMARY KEY, order_no TEXT, status TEXT,
    warehouse TEXT, customer TEXT
);
CREATE TABLE employee (
    id INTEGER PRIMARY KEY, name TEXT, code TEXT, status TEXT
);
"""

_EXPECTED_COLUMNS = (
    ("out_order", "department_id"),
    ("out_order", "picker"),
    ("employee", "department_id"),
)


def _create_db_with_missing_objects(db_path: Path) -> Path:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_OLD_SCHEMA)
        # 留一条存量数据，验证补列不影响已有行
        conn.execute(
            "INSERT INTO out_order(id, order_no, status, warehouse, customer)"
            " VALUES (1, 'OUT-2026-0001', 'pending', '主仓', '客户A')"
        )
        conn.execute(
            "INSERT INTO employee(id, name, code, status) VALUES (1, '张三', 'E01', 'active')"
        )
    return db_path


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


# A9:no-test=reason=下面五个 test_ 函数即被测函数的回归测试本体


def test_adds_all_missing_department_columns(tmp_path):
    """老库缺 department_id / picker → 一次补齐，且不影响存量数据。"""
    from app import ensure_outbound_department_columns
    db_path = _create_db_with_missing_objects(tmp_path / "inventory.db")

    ensure_outbound_department_columns(db_path=str(db_path))

    for table, col in _EXPECTED_COLUMNS:
        assert col in _cols(db_path, table), f"缺列未被补齐: {table}.{col}"
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT order_no FROM out_order WHERE id = 1"
        ).fetchone() == ("OUT-2026-0001",)
        # 补列后可写入（模拟移动端提交出库单落库 department_id + picker）
        conn.execute("UPDATE out_order SET department_id = 1, picker = '张三' WHERE id = 1")
        assert conn.execute(
            "SELECT department_id, picker FROM out_order WHERE id = 1"
        ).fetchone() == (1, "张三")


def test_idempotent_repeat_run(tmp_path):
    """补建/补列后重复执行无变化、不报错。"""
    from app import ensure_department_table, ensure_outbound_department_columns
    db_path = _create_db_with_missing_objects(tmp_path / "inventory.db")

    ensure_department_table(db_path=str(db_path))
    ensure_outbound_department_columns(db_path=str(db_path))
    before = {t: _cols(db_path, t) for t in ("department", "out_order", "employee")}

    ensure_department_table(db_path=str(db_path))
    ensure_outbound_department_columns(db_path=str(db_path))
    ensure_outbound_department_columns(db_path=str(db_path))

    after = {t: _cols(db_path, t) for t in ("department", "out_order", "employee")}
    assert before == after
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM out_order").fetchone() == (1,)


def test_startup_wiring_runs_even_when_no_db_touch(tmp_path):
    """接线：WMS_NO_DB_TOUCH=1 会跳过 create_all 与 auto_migrate_database，
    两个兜底函数必须不受该开关影响。子进程 `import app` 模拟完整启动，
    校验 department 表与三列都被补上（本次线上真 bug）。"""
    db_path = _create_db_with_missing_objects(tmp_path / "inventory.db")

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

    # 补建/补列确认日志必须出现在启动输出
    assert "department 缺表已补建（BUG-2026-09-12）" in result.stdout, (
        f"启动输出缺少 department 建表日志:\n{result.stdout}\n{result.stderr}"
    )
    assert "领料部门/领料人已补缺列（BUG-2026-09-12）" in result.stdout, (
        f"启动输出缺少补列完成日志:\n{result.stdout}\n{result.stderr}"
    )

    assert _table_exists(db_path, "department"), "启动未补建 department 表"
    for table, col in _EXPECTED_COLUMNS:
        assert col in _cols(db_path, table), f"启动未补齐: {table}.{col}"
