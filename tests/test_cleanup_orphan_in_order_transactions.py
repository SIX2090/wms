# -*- coding: utf-8 -*-
"""历史采购入库流水清理脚本回归测试。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.cleanup_orphan_in_order_transactions import cleanup_orphan_transactions


def _create_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE in_order (id INTEGER PRIMARY KEY, order_no TEXT NOT NULL);
        CREATE TABLE stock_transaction (
            id INTEGER PRIMARY KEY,
            reference_type TEXT,
            reference_id INTEGER,
            quantity REAL,
            location TEXT,
            created_at TEXT,
            remark TEXT
        );
        INSERT INTO in_order(id, order_no) VALUES (1, 'IN-EXISTS');
        INSERT INTO stock_transaction(id, reference_type, reference_id, quantity, remark)
        VALUES
            (10, 'in_order', 1, 10, '保留'),
            (11, 'in_order', 999, 10, '悬挂'),
            (12, 'out_order', 999, -5, '其他类型保留'),
            (13, 'in_order', NULL, 3, '无引用保留');
        """
    )
    conn.commit()
    conn.close()


def test_cleanup_orphan_transactions_dry_run_does_not_delete(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    result = cleanup_orphan_transactions(db_path=str(db_path), confirm_delete=False)

    assert result.candidate_ids == [11]
    assert result.deleted_count == 0
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM stock_transaction WHERE id = 11").fetchone()[0] == 1


def test_cleanup_orphan_transactions_requires_explicit_confirmation(tmp_path):
    db_path = tmp_path / "inventory.db"
    _create_db(db_path)

    result = cleanup_orphan_transactions(db_path=str(db_path), confirm_delete=True)

    assert result.candidate_ids == [11]
    assert result.deleted_count == 1
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM stock_transaction WHERE id = 11").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM stock_transaction WHERE id = 10").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM stock_transaction WHERE id = 12").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM stock_transaction WHERE id = 13").fetchone()[0] == 1
