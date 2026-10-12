# -*- coding: utf-8 -*-
"""F2.10 ③：location_inventory 回填工具（scripts/backfill_location_inventory.py）测试。

覆盖：
  * 纯计划函数 ``compute_plan``（A9）——补建/调平/幂等/不猜归属/人工兜底；
  * 基于临时 SQLite 库的端到端——dry-run 只读、--apply 生效、重跑幂等。

本文件不导入 app（脚本本身只用 sqlite3 直连），故无需内存库/生产门禁。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import backfill_location_inventory as b  # noqa: E402


WH_NAMES = {1: ("项目仓", "WH001"), 2: ("库存仓", "WH002")}


class TestComputePlan:
    """compute_plan 纯逻辑（不碰 DB）。"""

    def test_consistent_is_skipped(self):
        plan = b.compute_plan(
            txn_net={(100, 1): 10.0},
            loc_rows=[(1, 100, 1, "项目仓", 10.0)],
            warehouse_names=WH_NAMES)
        assert plan["skipped_consistent"] == 1
        assert plan["inserts"] == [] and plan["adjusts"] == []

    def test_missing_row_inserts_with_warehouse_name(self):
        plan = b.compute_plan(
            txn_net={(100, 1): 10.0}, loc_rows=[], warehouse_names=WH_NAMES)
        assert plan["inserts"] == [{
            "material_id": 100, "warehouse_id": 1,
            "location": "项目仓", "quantity": 10.0}]

    def test_insert_falls_back_to_code_when_name_empty(self):
        plan = b.compute_plan(
            txn_net={(100, 1): 3.0}, loc_rows=[],
            warehouse_names={1: ("", "WH001")})
        assert plan["inserts"][0]["location"] == "WH001"

    def test_existing_bucket_row_reduced(self):
        # 审计 §1.3 的 m615 型：库位账 5、流水净额 0 → 调平到 0
        plan = b.compute_plan(
            txn_net={}, loc_rows=[(7, 615, 1, "WH001", 5.0)],
            warehouse_names=WH_NAMES)
        assert len(plan["adjusts"]) == 1
        adj = plan["adjusts"][0]
        assert (adj["id"], adj["from"], adj["to"]) == (7, 5.0, 0.0)

    def test_existing_bucket_row_increased(self):
        # 审计 §1.3 的 m727 型：库位账 1.0、流水净额 0.4 → 调平到 0.4
        plan = b.compute_plan(
            txn_net={(727, 2): 0.4}, loc_rows=[(1, 727, 2, "WH002", 1.0)],
            warehouse_names=WH_NAMES)
        assert plan["adjusts"][0]["to"] == 0.4

    def test_skip_adjust_only_inserts(self):
        plan = b.compute_plan(
            txn_net={(615, 1): 0.0, (100, 1): 10.0},
            loc_rows=[(7, 615, 1, "WH001", 5.0)],
            warehouse_names=WH_NAMES, skip_adjust=True)
        assert plan["inserts"] and not plan["adjusts"]
        assert plan["skipped_adjust"] == 1

    def test_unattributed_location_row_ignored(self):
        # warehouse_id IS NULL 的库位行不参与、不猜归属
        plan = b.compute_plan(
            txn_net={}, loc_rows=[(1, 100, None, "项目仓", 5.0)],
            warehouse_names=WH_NAMES)
        assert plan["keys_total"] == 0
        assert not plan["inserts"] and not plan["adjusts"]

    def test_no_bucket_row_but_needs_reduce_goes_manual_review(self):
        # 只有非桶行 5，却要降到 3，且无桶行可调 → 人工核对，不自动改
        plan = b.compute_plan(
            txn_net={(100, 1): 3.0}, loc_rows=[(9, 100, 1, "A-01", 5.0)],
            warehouse_names=WH_NAMES)
        assert not plan["inserts"] and not plan["adjusts"]
        assert len(plan["manual_review"]) == 1

    def test_non_bucket_row_plus_missing_bucket_inserts_delta(self):
        # 非桶行 5 + 目标 8 → 新建桶行 3（合计回到 8）
        plan = b.compute_plan(
            txn_net={(100, 1): 8.0}, loc_rows=[(9, 100, 1, "A-01", 5.0)],
            warehouse_names=WH_NAMES)
        assert plan["inserts"][0]["quantity"] == 3.0


_SCHEMA = """
CREATE TABLE warehouse (id INTEGER PRIMARY KEY, name VARCHAR(100), code VARCHAR(50));
CREATE TABLE material (id INTEGER PRIMARY KEY, code VARCHAR(50), stock FLOAT DEFAULT 0);
CREATE TABLE stock_transaction (id INTEGER PRIMARY KEY, material_id INTEGER,
    quantity FLOAT, warehouse_id INTEGER);
CREATE TABLE location_inventory (id INTEGER PRIMARY KEY, material_id INTEGER NOT NULL,
    warehouse_id INTEGER, location VARCHAR(100) NOT NULL, quantity FLOAT,
    created_at DATETIME, updated_at DATETIME,
    UNIQUE (material_id, warehouse_id, location));
"""


def _make_db(tmp_path):
    """建一个最小 schema 的临时库：仓库1 + 物料100 + 流水 +10，无库位账行。"""
    path = str(tmp_path / "inv.db")
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.execute("INSERT INTO warehouse (id, name, code) VALUES (1, '项目仓', 'WH001')")
    conn.execute("INSERT INTO material (id, code, stock) VALUES (100, 'M100', 10)")
    conn.execute("INSERT INTO stock_transaction (id, material_id, quantity, warehouse_id) "
                 "VALUES (1, 100, 10, 1)")
    conn.commit()
    conn.close()
    return path


def _count(db, table):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


class TestEndToEnd:
    """对临时 SQLite 库跑真实脚本：dry-run 只读 / apply 生效 / 幂等。"""

    def test_dry_run_writes_nothing(self, tmp_path):
        db = _make_db(tmp_path)
        assert _count(db, "location_inventory") == 0
        rc = b.backfill(db_path=db, apply=False)
        assert rc == 0
        assert _count(db, "location_inventory") == 0

    def test_apply_creates_row_then_rerun_is_idempotent(self, tmp_path):
        db = _make_db(tmp_path)
        assert b.backfill(db_path=db, apply=True) == 0
        conn = sqlite3.connect(db)
        try:
            row = conn.execute(
                "SELECT material_id, warehouse_id, location, quantity "
                "FROM location_inventory").fetchone()
        finally:
            conn.close()
        assert row == (100, 1, "项目仓", 10.0)

        # 幂等：重跑 compute_plan 应零变更
        conn = sqlite3.connect(db)
        try:
            plan = b.compute_plan(b.collect_txn_net(conn),
                                  b.collect_location_rows(conn),
                                  b.collect_warehouse_names(conn))
        finally:
            conn.close()
        assert plan["inserts"] == [] and plan["adjusts"] == []
        assert plan["skipped_consistent"] == 1

    def test_missing_db_returns_error(self, tmp_path):
        assert b.backfill(db_path=str(tmp_path / "nope.db")) == 1
