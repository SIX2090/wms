# -*- coding: utf-8 -*-
"""历史悬挂流水清理脚本回归测试（BUG-2026-09-10-001 配套）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.cleanup_orphan_document_transactions import cleanup_orphan_transactions


def _create_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE out_order (id INTEGER PRIMARY KEY, order_no TEXT NOT NULL);
        CREATE TABLE production_requisition (id INTEGER PRIMARY KEY, req_no TEXT NOT NULL);
        CREATE TABLE transfer_order (id INTEGER PRIMARY KEY, transfer_no TEXT NOT NULL);
        CREATE TABLE adjustment_order (id INTEGER PRIMARY KEY, adjustment_no TEXT NOT NULL);
        CREATE TABLE after_sale_out_order (id INTEGER PRIMARY KEY, order_no TEXT NOT NULL);
        CREATE TABLE subcontract_issue (id INTEGER PRIMARY KEY, issue_no TEXT NOT NULL);
        CREATE TABLE subcontract_receive (id INTEGER PRIMARY KEY, receive_no TEXT NOT NULL);
        CREATE TABLE inventory_check (id INTEGER PRIMARY KEY, check_no TEXT NOT NULL);
        CREATE TABLE stock_transaction (
            id INTEGER PRIMARY KEY,
            reference_type TEXT,
            reference_id INTEGER,
            quantity REAL,
            location TEXT,
            created_at TEXT,
            remark TEXT
        );
        INSERT INTO out_order(id, order_no) VALUES (1, 'OU-EXISTS');
        INSERT INTO transfer_order(id, transfer_no) VALUES (1, 'TR-EXISTS');
        INSERT INTO stock_transaction(id, reference_type, reference_id, quantity, remark)
        VALUES
            (10, 'out_order', 1, -1, '保留：单据仍存在'),
            (11, 'out_order', 999, -1, '悬挂：领料单已删除'),
            (12, 'out_order', 999, 1, '悬挂：反提交反向流水'),
            (13, 'requisition', 888, -2, '悬挂：工单领料单已删除'),
            (14, 'transfer', 1, -4, '保留：调拨单仍存在'),
            (15, 'transfer', 777, -4, '悬挂：调拨单已删除'),
            (16, 'adjustment', 666, 6, '悬挂：调整单已删除'),
            (17, 'after_sale_out_order', 555, -2, '悬挂：售后出库单已删除'),
            (18, 'subcontract_issue', 444, -7, '悬挂：委外发料单已删除'),
            (19, 'subcontract_receive', 333, 8, '悬挂：委外收货单已删除'),
            (20, 'check', 222, 1, '悬挂：历史盘点流水'),
            (21, 'in_order', 999, 10, '保留：in_order 由 17-006 脚本负责'),
            (22, 'out_order', NULL, -1, '保留：无引用流水'),
            (23, 'unknown_type', 999, 1, '保留：未知引用类型');
        """
    )
    conn.commit()
    conn.close()


def test_cleanup_dry_run_does_not_delete(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    result = cleanup_orphan_transactions(db_path=str(db_path), confirm_delete=False)

    assert sorted(result.candidate_ids) == [11, 12, 13, 15, 16, 17, 18, 19, 20]
    assert result.deleted_count == 0
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM stock_transaction").fetchone()[0] == 14


def test_cleanup_requires_explicit_confirmation(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    result = cleanup_orphan_transactions(db_path=str(db_path), confirm_delete=True)

    assert result.deleted_count == 9
    with sqlite3.connect(db_path) as conn:
        remaining = {
            row[0]
            for row in conn.execute("SELECT id FROM stock_transaction").fetchall()
        }
    # 只保留：单据仍存在的(10,14)、in_order 范畴(21)、无引用(22)、未知类型(23)
    assert remaining == {10, 14, 21, 22, 23}


def test_cleanup_does_not_touch_recreated_document(tmp_path):
    """预演后若同 ID 单据被重建，确认删除时不得误删其流水（删除走二次回连校验）。"""
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    dry = cleanup_orphan_transactions(db_path=str(db_path), confirm_delete=False)
    assert 11 in dry.candidate_ids

    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO out_order(id, order_no) VALUES (999, 'OU-RECREATED')")
        conn.commit()

    result = cleanup_orphan_transactions(db_path=str(db_path), confirm_delete=True)
    with sqlite3.connect(db_path) as conn:
        # 单据 999 已重建，其流水 11/12 必须保留
        assert conn.execute(
            "SELECT COUNT(*) FROM stock_transaction WHERE reference_type='out_order' AND reference_id=999"
        ).fetchone()[0] == 2
    assert result.deleted_count == 7
