# -*- coding: utf-8 -*-
"""BUG-2026-08-18-005 回归：启动期自动回填历史无仓库单据到默认仓库。

与 scripts/backfill_document_warehouse.py 同源逻辑的启动集成：
app.backfill_empty_warehouse_documents 在系统启动时把 warehouse/location
为空的采购入库单/领料单及其关联流水回填为默认仓库名，无需人工执行命令。

测试用例：
  T1. 有默认仓库：单据 warehouse 与关联流水 location 都回填默认仓库名
  T2. 无默认仓库：跳过不写库
  T3. 幂等：重复执行无变化
  T4. 已归属仓库的单据/流水保持不变
  T5. 启动接线：即使 WMS_NO_DB_TOUCH=1（start_wms_offline.bat 默认设置、
     会跳过 auto_migrate_database），回填仍在 app 导入启动时执行
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app import backfill_empty_warehouse_documents

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _create_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE warehouse (
            id INTEGER PRIMARY KEY,
            name TEXT,
            code TEXT,
            status TEXT,
            is_default INTEGER
        );
        CREATE TABLE in_order (
            id INTEGER PRIMARY KEY,
            order_no TEXT,
            warehouse TEXT
        );
        CREATE TABLE production_requisition (
            id INTEGER PRIMARY KEY,
            req_no TEXT,
            warehouse TEXT
        );
        CREATE TABLE stock_transaction (
            id INTEGER PRIMARY KEY,
            reference_type TEXT,
            reference_id INTEGER,
            location TEXT
        );
        INSERT INTO warehouse(id, name, code, status, is_default)
        VALUES (1, '材料仓', 'WH001', 'active', 1);
        INSERT INTO in_order(id, order_no, warehouse)
        VALUES
            (1, 'IN-OLD-1', ''),
            (2, 'IN-OLD-2', NULL),
            (3, 'IN-NEW',   '材料仓');
        INSERT INTO production_requisition(id, req_no, warehouse)
        VALUES
            (10, 'REQ-OLD', ''),
            (11, 'REQ-NEW', '材料仓');
        INSERT INTO stock_transaction(id, reference_type, reference_id, location)
        VALUES
            (100, 'in_order', 1, NULL),
            (101, 'in_order', 2, ''),
            (102, 'in_order', 3, '材料仓'),
            (103, 'in_order', 3, NULL),
            (110, 'requisition', 10, NULL),
            (111, 'requisition', 11, NULL);
        """
    )
    conn.commit()
    conn.close()


def _read(path: Path, sql: str):
    with sqlite3.connect(path) as conn:
        return conn.execute(sql).fetchall()


def test_t1_backfills_documents_and_transactions(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    backfill_empty_warehouse_documents(db_path=str(db_path))

    assert _read(db_path, "SELECT order_no, warehouse FROM in_order ORDER BY id") == [
        ('IN-OLD-1', '材料仓'), ('IN-OLD-2', '材料仓'), ('IN-NEW', '材料仓')
    ]
    assert _read(db_path, "SELECT req_no, warehouse FROM production_requisition ORDER BY id") == [
        ('REQ-OLD', '材料仓'), ('REQ-NEW', '材料仓')
    ]
    # 仅受影响单据的空 location 流水回填；单据 3 未回填，其空流水保持原样
    assert _read(db_path, "SELECT id, location FROM stock_transaction ORDER BY id") == [
        (100, '材料仓'), (101, '材料仓'), (102, '材料仓'),
        (103, None),
        (110, '材料仓'), (111, None),
    ]


def test_t2_no_default_warehouse_skips(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE warehouse SET is_default = 0")
        conn.commit()

    backfill_empty_warehouse_documents(db_path=str(db_path))

    assert _read(db_path, "SELECT warehouse FROM in_order WHERE id = 1") == [('',)]


def test_t3_idempotent(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)
    backfill_empty_warehouse_documents(db_path=str(db_path))

    backfill_empty_warehouse_documents(db_path=str(db_path))

    assert _read(db_path, "SELECT COUNT(*) FROM in_order WHERE warehouse = '材料仓'") == [(3,)]
    assert _read(db_path, "SELECT COUNT(*) FROM stock_transaction WHERE location = '材料仓'") == [(4,)]


def test_t4_preserves_existing_attribution(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    backfill_empty_warehouse_documents(db_path=str(db_path))

    assert _read(db_path, "SELECT warehouse FROM in_order WHERE id = 3") == [('材料仓',)]
    assert _read(db_path, "SELECT location FROM stock_transaction WHERE id = 102") == [('材料仓',)]


def test_t5_startup_wiring_runs_backfill_even_when_no_db_touch(tmp_path):
    """T5：生产启动脚本 start_wms_offline.bat 默认设置 WMS_NO_DB_TOUCH=1，
    会跳过 auto_migrate_database。回填必须不受该开关影响，否则生产重启永远不生效
    （本次线上真 bug）。通过子进程 `import app` 模拟完整启动，校验 DB 被回填。"""
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

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

    # 回填确认日志必须出现在启动输出（回填调用放在日志配置之后，日志行不丢失）
    assert "历史单据仓库回填完成" in result.stdout, (
        f"启动输出缺少回填完成日志:\n{result.stdout}\n{result.stderr}"
    )

    assert _read(db_path, "SELECT order_no, warehouse FROM in_order ORDER BY id") == [
        ('IN-OLD-1', '材料仓'), ('IN-OLD-2', '材料仓'), ('IN-NEW', '材料仓')
    ]
    assert _read(db_path, "SELECT req_no, warehouse FROM production_requisition ORDER BY id") == [
        ('REQ-OLD', '材料仓'), ('REQ-NEW', '材料仓')
    ]
    assert _read(db_path, "SELECT id, location FROM stock_transaction ORDER BY id") == [
        (100, '材料仓'), (101, '材料仓'), (102, '材料仓'),
        (103, None),
        (110, '材料仓'), (111, None),
    ]
