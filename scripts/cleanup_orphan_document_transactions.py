# -*- coding: utf-8 -*-
"""一次性清理已删除单据遗留的库存流水（BUG-2026-09-10-001 历史数据配套）。

背景：BUG-2026-08-17-006 只修了采购入库单删除清流水；领料单/工单领料单/
调拨单/库存调整单/售后出库单/委外发料单/委外收货单的删除路由在
BUG-2026-09-10-001 之前不清理流水，反提交+删除后 stock_transaction 中残留
指向已删除单据的悬挂引用，库存台账因此仍显示"已删除"的单据。

默认仅预演，输出候选流水而不写库。只有传入 --confirm-delete 才会执行删除。
清理条件严格限定为 reference_type 属于已知单据类型、reference_id 非空，且
对应单据主表已不存在的库存流水；仍存在的单据、未知引用类型和无引用流水
一律保留。采购入库单（in_order）的历史悬挂流水请使用
scripts/cleanup_orphan_in_order_transactions.py（BUG-2026-08-17-006 配套）。
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass, field


DEFAULT_DB_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', 'app', 'instance', 'inventory.db'
))

# reference_type -> 单据主表（表名与 app/app.py ORM __tablename__ 一致）
DOCUMENT_TABLES = {
    'out_order': 'out_order',
    'requisition': 'production_requisition',
    'transfer': 'transfer_order',
    'adjustment': 'adjustment_order',
    'after_sale_out_order': 'after_sale_out_order',
    'subcontract_issue': 'subcontract_issue',
    'subcontract_receive': 'subcontract_receive',
    # 历史遗留：早期盘点直接写 reference_type='check' 的流水
    # （现版本盘点经调整单写 reference_type='adjustment'），一并兜底清理。
    'check': 'inventory_check',
}


@dataclass(frozen=True)
class CleanupResult:
    candidate_ids: list[int]
    deleted_count: int
    by_type: dict[str, int] = field(default_factory=dict)


def _find_orphan_transactions(conn: sqlite3.Connection):
    """按 reference_type 逐类找出主表已不存在的悬挂流水。"""
    orphans = []
    for reference_type, table in DOCUMENT_TABLES.items():
        rows = conn.execute(
            f"""
            SELECT txn.id, txn.reference_type, txn.reference_id, txn.quantity,
                   txn.location, txn.created_at
            FROM stock_transaction AS txn
            LEFT JOIN {table} AS document ON document.id = txn.reference_id
            WHERE txn.reference_type = ?
              AND txn.reference_id IS NOT NULL
              AND txn.reference_id > 0
              AND document.id IS NULL
            ORDER BY txn.id ASC
            """,
            (reference_type,),
        ).fetchall()
        orphans.extend(rows)
    return orphans


def cleanup_orphan_transactions(db_path: str | None = None, confirm_delete: bool = False) -> CleanupResult:
    """预演或清理引用已删除单据的库存流水。"""
    path = os.path.abspath(db_path or DEFAULT_DB_PATH)
    if not os.path.isfile(path):
        raise FileNotFoundError(f'数据库不存在: {path}')

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        candidates = _find_orphan_transactions(conn)
        candidate_ids = [row['id'] for row in candidates]
        by_type: dict[str, int] = {}
        for row in candidates:
            by_type[row['reference_type']] = by_type.get(row['reference_type'], 0) + 1
            print(
                f"候选流水 id={row['id']} 类型={row['reference_type']} "
                f"单据ID={row['reference_id']} 数量={row['quantity']} "
                f"仓库/库位={row['location'] or '-'} 时间={row['created_at'] or '-'}"
            )

        if not confirm_delete:
            print(f'预演完成：发现 {len(candidate_ids)} 条历史悬挂流水（按类型：{by_type}），未写入数据库。')
            print('确认无误后执行：python scripts/cleanup_orphan_document_transactions.py --confirm-delete')
            return CleanupResult(candidate_ids=candidate_ids, deleted_count=0, by_type=by_type)

        deleted_count = 0
        if candidate_ids:
            # 删除时按类型回连主表二次确认，防止预演后单据被重建而误删
            for reference_type, table in DOCUMENT_TABLES.items():
                before_changes = conn.total_changes
                conn.execute(
                    f"""
                    DELETE FROM stock_transaction
                    WHERE reference_type = ?
                      AND reference_id IS NOT NULL
                      AND reference_id > 0
                      AND NOT EXISTS (
                          SELECT 1 FROM {table}
                          WHERE {table}.id = stock_transaction.reference_id
                      )
                    """,
                    (reference_type,),
                )
                deleted_count += conn.total_changes - before_changes
            conn.commit()
        print(f'清理完成：删除 {deleted_count} 条历史悬挂流水。')
        return CleanupResult(candidate_ids=candidate_ids, deleted_count=deleted_count, by_type=by_type)
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description='清理已删除单据遗留的库存流水（领料/工单领料/调拨/调整/售后出库/委外/盘点）')
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
