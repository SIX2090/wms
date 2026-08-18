# -*- coding: utf-8 -*-
"""回填历史无仓库单据到默认仓库（BUG-2026-08-18-005）。

背景：系统早期采购入库单/领料单未强制选择仓库，单据 warehouse 为空字符串。
AGENTS.md 仓库必填规则落地后，报表（入库明细、仓库月报、采购报表、工单领料报表）
一律按仓库过滤，导致这些历史单据“有数据也查不出来”。

本脚本把以下存量数据回填为默认仓库（warehouse 表 is_default=1 且 active 的第一条）：
  1. in_order（采购入库单）           warehouse 为空 -> 默认仓库名
  2. production_requisition（领料单） warehouse 为空 -> 默认仓库名
  3. 上述单据关联的 stock_transaction.location 为空 ->
     默认仓库名（关库位管理时仓库级库存按 location 聚合，台账/月报/库存查询才命中）

幂等：只处理 warehouse/location 为 NULL 或空串的行；重复执行无变化。

安全：默认仅预演（dry-run），必须显式传 --apply 才会写库。
"""
from __future__ import annotations

import argparse
import os
import sqlite3


DEFAULT_DB_PATH = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'app', 'instance', 'inventory.db',
))

# (表名, 单号列, 仓库列, 流水引用类型, 单号展示名)
DOCUMENT_TABLES = (
    ('in_order', 'order_no', 'warehouse', 'in_order', '采购入库单'),
    ('production_requisition', 'req_no', 'warehouse', 'requisition', '领料单'),
)


def resolve_default_warehouse(conn: sqlite3.Connection) -> str | None:
    """取启用中的默认仓库规范名称；未配置或未启用时返回 None。"""
    row = conn.execute(
        "SELECT name FROM warehouse "
        "WHERE is_default = 1 AND status = 'active' "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def find_empty_warehouse_documents(conn: sqlite3.Connection, table: str,
                                   no_col: str, wh_col: str):
    """返回 (id, 单号) 列表：warehouse 为 NULL/空串 的历史单据。"""
    rows = conn.execute(
        f"SELECT id, {no_col} FROM {table} "
        f"WHERE {wh_col} IS NULL OR TRIM({wh_col}) = '' "
        f"ORDER BY id",
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def find_empty_location_transactions(conn: sqlite3.Connection, ref_type: str,
                                     ref_ids: set[int]):
    """返回流水 id 列表：引用指定单据且 location 为空的历史流水。"""
    if not ref_ids:
        return []
    placeholders = ','.join('?' for _ in ref_ids)
    rows = conn.execute(
        f"SELECT id FROM stock_transaction "
        f"WHERE reference_type = ? AND reference_id IN ({placeholders}) "
        f"AND (location IS NULL OR TRIM(location) = '') "
        f"ORDER BY id",
        (ref_type, *ref_ids),
    ).fetchall()
    return [row[0] for row in rows]


def backfill(db_path: str | None = None, apply: bool = False) -> int:
    path = os.path.abspath(db_path or DEFAULT_DB_PATH)
    if not os.path.isfile(path):
        print(f'数据库不存在: {path}')
        return 1

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        default_wh = resolve_default_warehouse(conn)
        if not default_wh:
            print('未找到启用中的默认仓库（warehouse.is_default=1 且 status=active）。')
            print('请先在「仓库管理」中设置默认仓库，再执行本脚本。')
            return 1

        total_docs = 0
        total_txns = 0
        all_changed = []
        for table, no_col, wh_col, ref_type, label in DOCUMENT_TABLES:
            docs = find_empty_warehouse_documents(conn, table, no_col, wh_col)
            ref_ids = {doc_id for doc_id, _ in docs}
            txns = find_empty_location_transactions(conn, ref_type, ref_ids)
            if apply:
                if docs:
                    conn.executemany(
                        f"UPDATE {table} SET {wh_col} = ? WHERE id = ?",
                        [(default_wh, doc_id) for doc_id, _ in docs],
                    )
                if txns:
                    conn.executemany(
                        "UPDATE stock_transaction SET location = ? WHERE id = ?",
                        [(default_wh, txn_id) for txn_id in txns],
                    )
            total_docs += len(docs)
            total_txns += len(txns)
            if docs or txns:
                all_changed.append(
                    f'  [{label}] {table}: 单据 {len(docs)} 条'
                    f'（单号: {", ".join(no for _, no in docs[:5])}'
                    + ('...' if len(docs) > 5 else '')
                    + f'），关联流水 {len(txns)} 条'
                )

        if not all_changed:
            print(f'无需回填：默认仓库 [{default_wh}]，历史单据均已归属仓库。')
            return 0

        print(f'默认仓库: {default_wh}')
        print('待回填明细:')
        print('\n'.join(all_changed))
        print(f'共回填单据 {total_docs} 条、流水 {total_txns} 条，'
              + ('已写库。' if apply else '（dry-run，未写库；加 --apply 执行）'))
        if apply:
            conn.commit()
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='回填历史无仓库单据到默认仓库')
    parser.add_argument('--db', default=None, help='SQLite 数据库路径（默认 app/instance/inventory.db）')
    parser.add_argument('--apply', action='store_true', help='实际写库；缺省仅预演')
    args = parser.parse_args()
    raise SystemExit(backfill(db_path=args.db, apply=args.apply))
