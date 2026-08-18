# -*- coding: utf-8 -*-
"""BUG-2026-08-18-005 回归：历史无仓库单据回填默认仓库脚本。

根因：系统早期采购入库单/领料单未强制选择仓库，单据 warehouse 为空；
报表按仓库过滤后这些历史单据“有数据也查不出来”。
修复：scripts/backfill_document_warehouse.py 把 warehouse/location 为空的
采购入库单、领料单及其关联流水回填为默认仓库名。

测试用例：
  T1. 默认 dry-run 不写库
  T2. --apply 写库：单据 warehouse 与关联流水 location 都回填默认仓库名
  T3. 无默认仓库：返回 1 且不写库
  T4. 幂等：apply 后再跑提示无需回填
  T5. 已归属仓库的单据/已非空流水保持不变，仅回填空值行
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.backfill_document_warehouse import backfill


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


def test_t1_dry_run_does_not_write(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    rc = backfill(db_path=str(db_path), apply=False)

    assert rc == 0
    # 单据与流水均保持原样
    assert _read(db_path, "SELECT warehouse FROM in_order ORDER BY id") == [
        ('',), (None,), ('材料仓',)
    ]
    assert _read(db_path, "SELECT warehouse FROM production_requisition ORDER BY id") == [
        ('',), ('材料仓',)
    ]
    assert _read(db_path, "SELECT location FROM stock_transaction ORDER BY id") == [
        (None,), ('',), ('材料仓',), (None,), (None,), (None,)
    ]


def test_t2_apply_backfills_documents_and_transactions(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    rc = backfill(db_path=str(db_path), apply=True)

    assert rc == 0
    assert _read(db_path, "SELECT order_no, warehouse FROM in_order ORDER BY id") == [
        ('IN-OLD-1', '材料仓'), ('IN-OLD-2', '材料仓'), ('IN-NEW', '材料仓')
    ]
    assert _read(db_path, "SELECT req_no, warehouse FROM production_requisition ORDER BY id") == [
        ('REQ-OLD', '材料仓'), ('REQ-NEW', '材料仓')
    ]
    # 仅受影响单据的空 location 流水回填；已归属的保持不变
    assert _read(db_path, "SELECT id, location FROM stock_transaction ORDER BY id") == [
        (100, '材料仓'), (101, '材料仓'), (102, '材料仓'),
        (103, None),  # 单据 3 未回填，流水保持原样（不强行归默认仓）
        (110, '材料仓'), (111, None),
    ]


def test_t3_no_default_warehouse_noop(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE warehouse SET is_default = 0")
        conn.commit()

    rc = backfill(db_path=str(db_path), apply=True)

    assert rc == 1
    assert _read(db_path, "SELECT warehouse FROM in_order WHERE id = 1") == [( '', )]


def test_t4_idempotent_after_apply(tmp_path, capsys):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)
    backfill(db_path=str(db_path), apply=True)

    rc = backfill(db_path=str(db_path), apply=True)

    assert rc == 0
    assert "无需回填" in capsys.readouterr().out
    assert _read(db_path, "SELECT COUNT(*) FROM in_order WHERE warehouse = '材料仓'") == [(3,)]


def test_t5_preserves_existing_attribution(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    backfill(db_path=str(db_path), apply=True)

    # 已归属仓库的单据仓库未被改写；非本脚本引用类型的流水不动
    assert _read(db_path, "SELECT warehouse FROM in_order WHERE id = 3") == [('材料仓',)]
    assert _read(db_path, "SELECT location FROM stock_transaction WHERE id = 102") == [('材料仓',)]
