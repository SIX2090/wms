# -*- coding: utf-8 -*-
"""一次性清理已删除采购入库单遗留的库存流水。

默认仅预演，输出候选流水而不写库。只有传入 --confirm-delete 才会执行删除。
清理条件严格限定为 reference_type='in_order'、reference_id 非空，且入库单主表
已不存在的库存流水；仍存在的入库单、其他单据类型和无引用流水一律保留。
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass


DEFAULT_DB_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'app', 'instance', 'inventory.db'
))


@dataclass(frozen=True)
class CleanupResult:
    candidate_ids: list[int]
    deleted_count: int


def _find_orphan_transactions(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT txn.id, txn.reference_id, txn.quantity, txn.location, txn.created_at
        FROM stock_transaction AS txn
        LEFT JOIN in_order AS document ON document.id = txn.reference_id
        WHERE txn.reference_type = ?
          AND txn.reference_id IS NOT NULL
          AND txn.reference_id > 0
          AND document.id IS NULL
        ORDER BY txn.id ASC
        """,
        ('in_order',),
    ).fetchall()


def cleanup_orphan_transactions(db_path: str | None = None, confirm_delete: bool = False) -> CleanupResult:
    """预演或清理引用已删除采购入库单的库存流水。"""
    path = os.path.abspath(db_path or DEFAULT_DB_PATH)
    if not os.path.isfile(path):
        raise FileNotFoundError(f'数据库不存在: {path}')

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        candidates = _find_orphan_transactions(conn)
        candidate_ids = [row['id'] for row in candidates]
        for row in candidates:
            print(
                f"候选流水 id={row['id']} 入库单ID={row['reference_id']} "
                f"数量={row['quantity']} 仓库/库位={row['location'] or '-'} "
                f"时间={row['created_at'] or '-'}"
            )

        if not confirm_delete:
            print(f'预演完成：发现 {len(candidate_ids)} 条历史悬挂采购入库流水，未写入数据库。')
            print('确认无误后执行：python scripts/cleanup_orphan_in_order_transactions.py --confirm-delete')
            return CleanupResult(candidate_ids=candidate_ids, deleted_count=0)

        if candidate_ids:
            before_changes = conn.total_changes
            conn.executemany(
                """
                DELETE FROM stock_transaction
                WHERE id = ?
                  AND reference_type = ?
                  AND reference_id IS NOT NULL
                  AND reference_id > 0
                  AND NOT EXISTS (
                      SELECT 1 FROM in_order
                      WHERE in_order.id = stock_transaction.reference_id
                  )
                """,
                [(transaction_id, 'in_order') for transaction_id in candidate_ids],
            )
            conn.commit()
            deleted_count = conn.total_changes - before_changes
        else:
            deleted_count = 0
        print(f'清理完成：删除 {deleted_count} 条历史悬挂采购入库流水。')
        return CleanupResult(candidate_ids=candidate_ids, deleted_count=deleted_count)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='清理已删除采购入库单遗留的库存流水')
    parser.add_argument('--db', default=DEFAULT_DB_PATH, help='SQLite 数据库路径')
    parser.add_argument('--confirm-delete', action='store_true', help='确认执行删除；未提供时仅预演')
    args = parser.parse_args()
    try:
        cleanup_orphan_transactions(args.db, args.confirm_delete)
    except (FileNotFoundError, sqlite3.Error) as error:
        print(f'清理失败：{error}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
