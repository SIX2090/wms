# -*- coding: utf-8 -*-
"""BUG-2026-08-28-004 回归：WMS_NO_DB_TOUCH 启动时无条件补
stock_transaction.warehouse_id 列。

背景：BUG-2026-08-27-005 把台账/月报/库存汇总的仓库过滤切换到
``StockTransaction.warehouse_id`` 外键精确命中，但该列只在
``auto_migrate_database()`` 里 ADD COLUMN。``start_wms_offline.bat``/
``start_wms_auto.bat`` 默认 ``WMS_NO_DB_TOUCH=1``，
``auto_migrate_database()`` 与 ``backfill_stock_txn_warehouse_id()``
都被 ``startup_db_upgrade_disabled()`` 跳过——存量生产库重启也补不上
列，``_warehouse_scoped_txn_condition`` 构造 SQL 使用 ``warehouse_id``
时报 ``sqlite3.OperationalError: no such column: stock_transaction.warehouse_id``，
库存台账 / 仓库月报 / 库存汇总按仓库查询 500。

修复：仿 ``ensure_print_job_columns``，新增
``ensure_stock_transaction_warehouse_id_column()``——独立 sqlite 连接、
独立于迁移开关无条件执行、幂等补列 + 索引；同时把
``backfill_stock_txn_warehouse_id()`` 调用从 ``startup_db_upgrade_disabled()``
守卫里取出（列刚被上一行无条件补好，backfill 必可用）。

验收：
T1. 已有 stock_transaction 但缺 warehouse_id 列的库 → ensure_xxx_column 补列。
T2. 已有 warehouse_id 列的库 → ensure_xxx_column 不重复 ALTER（幂等）。
T3. stock_transaction 表不存在（全新库）→ ensure_xxx_column 安全 no-op。
T4. 库文件不存在 → ensure_xxx_column 安全 no-op。
T5. 补列后索引 idx_stock_txn_warehouse_id 已建（含列存在场景）。
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402


_BASE_SCHEMA_SQL = """
CREATE TABLE stock_transaction (
    id INTEGER PRIMARY KEY,
    material_id INTEGER,
    transaction_type VARCHAR(20),
    quantity FLOAT,
    location VARCHAR(100),
    reference_type VARCHAR(50),
    reference_id INTEGER,
    remark TEXT,
    operator_id INTEGER,
    created_at DATETIME
);
CREATE TABLE warehouse (id INTEGER PRIMARY KEY, code VARCHAR(20), name VARCHAR(100));
INSERT INTO warehouse(id, code, name) VALUES (1, 'WH001', '项目仓');
"""


def _make_db_without_column() -> str:
    """在临时目录建一个不带 warehouse_id 列的最小 stock_transaction 表。"""
    tmp = tempfile.mkdtemp(prefix="wms-bug-2026-08-28-004-")
    db_path = os.path.join(tmp, "inventory.db")
    conn = sqlite3.connect(db_path)
    try:
        for stmt in _BASE_SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()
    return db_path


def _table_columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    finally:
        conn.close()


def _indexes(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
            (table,),
        ).fetchall()}
    finally:
        conn.close()


class TestEnsureStockTransactionWarehouseIdColumn:
    def test_adds_column_when_missing(self):
        """T1：缺 warehouse_id 列 → ensure_xxx_column 自动补上。"""
        db_path = _make_db_without_column()
        assert "warehouse_id" not in _table_columns(db_path, "stock_transaction")
        app_module.ensure_stock_transaction_warehouse_id_column(db_path)
        cols = _table_columns(db_path, "stock_transaction")
        assert "warehouse_id" in cols, (
            "BUG-2026-08-28-004 复发：缺列库补列失败"
        )

    def test_idempotent_when_column_present(self):
        """T2：列已存在 → ensure_xxx_column 安全 no-op（幂等）。"""
        db_path = _make_db_without_column()
        app_module.ensure_stock_transaction_warehouse_id_column(db_path)
        # 再调一次：不得抛错、不得重复 ALTER
        app_module.ensure_stock_transaction_warehouse_id_column(db_path)
        cols = _table_columns(db_path, "stock_transaction")
        assert "warehouse_id" in cols

    def test_creates_index(self):
        """T3：无论列之前是否存在，索引 idx_stock_txn_warehouse_id 都建好。"""
        db_path = _make_db_without_column()
        app_module.ensure_stock_transaction_warehouse_id_column(db_path)
        indexes = _indexes(db_path, "stock_transaction")
        assert "idx_stock_txn_warehouse_id" in indexes

    def test_no_op_when_table_missing(self):
        """T4：stock_transaction 表不存在（全新库）→ 安全 no-op。"""
        tmp = tempfile.mkdtemp(prefix="wms-bug-2026-08-28-004-empty-")
        db_path = os.path.join(tmp, "inventory.db")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("CREATE TABLE warehouse (id INTEGER PRIMARY KEY)")
            conn.commit()
        finally:
            conn.close()
        # 不得抛错
        app_module.ensure_stock_transaction_warehouse_id_column(db_path)
        # 表仍然不存在（不创建，让 create_all 全权建全量表）
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stock_transaction'"
            ).fetchone()
        finally:
            conn.close()
        assert row is None, "全新库下不应创建 stock_transaction 表"

    def test_no_op_when_db_file_missing(self):
        """T5：库文件不存在 → 安全 no-op（全新部署场景）。"""
        tmp = tempfile.mkdtemp(prefix="wms-bug-2026-08-28-004-missing-")
        db_path = os.path.join(tmp, "nonexistent.db")
        # 不得抛错
        app_module.ensure_stock_transaction_warehouse_id_column(db_path)


class TestStartupWiring:
    def test_module_level_call_after_print_job(self):
        """启动接线位置校验：ensure_stock_transaction_warehouse_id_column()
        必须在 ensure_print_job_columns() 之后被调用（独立于迁移开关）。"""
        app_py = Path(__file__).resolve().parents[1] / "app" / "app.py"
        text = app_py.read_text(encoding="utf-8")
        pj_idx = text.find("ensure_print_job_columns()")
        st_idx = text.find("ensure_stock_transaction_warehouse_id_column()")
        assert pj_idx > 0, "ensure_print_job_columns() 接线缺失"
        assert st_idx > 0, "ensure_stock_transaction_warehouse_id_column() 接线缺失"
        assert pj_idx < st_idx, (
            "ensure_stock_transaction_warehouse_id_column() 必须在 "
            "ensure_print_job_columns() 之后调用，保证列补好后再 backfill"
        )

    def test_backfill_unconditional(self):
        """BUG-2026-08-28-004 配套：backfill_stock_txn_warehouse_id()
        不再被 startup_db_upgrade_disabled() 守卫——列由 ensure 补好后，
        backfill 必须无条件执行，否则治本打折。"""
        app_py = Path(__file__).resolve().parents[1] / "app" / "app.py"
        text = app_py.read_text(encoding="utf-8")
        # 找 backfill 的调用位置（带 try/with app.app_context 的模块级调用）
        bf_idx = text.find("_backfilled = backfill_stock_txn_warehouse_id()")
        assert bf_idx > 0, "backfill 调用缺失"
        # 向前 200 字符内不应出现 startup_db_upgrade_disabled 守卫
        guard_ctx = text[max(0, bf_idx - 400):bf_idx]
        assert "if not startup_db_upgrade_disabled()" not in guard_ctx, (
            "BUG-2026-08-28-004 复发：backfill 仍被 startup_db_upgrade_disabled() "
            "守卫跳过，WMS_NO_DB_TOUCH 下治本失效"
        )
