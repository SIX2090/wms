# -*- coding: utf-8 -*-
"""回填 stock_transaction.location 为空的存量流水。

根因（BUG-2026-08-17-00X）：关库位管理时，仓库级库存聚合
（get_warehouse_stock_quantities / 库存台账 / 仓库月报）依赖
StockTransaction.location 匹配仓库名/编码。历史流水由旧代码写入时
location 为 NULL，导致有库存也查不出来。

本脚本按 reference_type 关联单据表，把单据上的仓库字段回填到流水 location，
并统一归一化为仓库主数据的规范名称（name），保证台账/月报按 name 过滤也能命中。

幂等：只处理 location 为 NULL/空 的流水；单据仓库为空时跳过并计数。
"""
import os
import sqlite3
import sys


def _canonical_warehouse_name(conn, raw):
    """把单据上的仓库字符串（可能是 name 或 code）解析为仓库主数据规范 name。"""
    raw = (raw or '').strip()
    if not raw:
        return None
    row = conn.execute(
        'SELECT name FROM warehouse WHERE name = ? OR code = ? LIMIT 1',
        (raw, raw),
    ).fetchone()
    if row:
        return row[0]
    return raw


def backfill(db_path=None, dry_run=False):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', 'app', 'instance', 'inventory.db')
    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        print(f'数据库不存在: {db_path}')
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, reference_type, reference_id FROM stock_transaction "
            "WHERE location IS NULL OR location = ''"
        ).fetchall()
        if not rows:
            print('没有需要回填的流水（location 均非空）')
            return 0

        updated = 0
        skipped = 0
        for row in rows:
            ref_type = row['reference_type']
            ref_id = row['reference_id']
            raw_wh = None
            if ref_type == 'in_order':
                doc = conn.execute(
                    'SELECT warehouse FROM in_order WHERE id = ?', (ref_id,)
                ).fetchone()
                raw_wh = doc['warehouse'] if doc else None
            elif ref_type == 'out_order':
                doc = conn.execute(
                    'SELECT warehouse FROM out_order WHERE id = ?', (ref_id,)
                ).fetchone()
                raw_wh = doc['warehouse'] if doc else None
            else:
                # 其他 reference_type 的流水本就不依赖 location 聚合仓库，
                # 保持原样，不强行回填。
                skipped += 1
                continue

            name = _canonical_warehouse_name(conn, raw_wh)
            if not name:
                skipped += 1
                continue
            if dry_run:
                print(f'[dry-run] txn={row["id"]} {ref_type}#{ref_id} -> {name}')
            else:
                conn.execute(
                    'UPDATE stock_transaction SET location = ? WHERE id = ?',
                    (name, row['id']),
                )
            updated += 1

        if not dry_run:
            conn.commit()
        print(f'共 {len(rows)} 条空 location 流水：回填 {updated} 条，跳过 {skipped} 条'
              + ('（dry-run，未写入）' if dry_run else ''))
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    path = None
    for i, arg in enumerate(sys.argv):
        if arg == '--db' and i + 1 < len(sys.argv):
            path = sys.argv[i + 1]
    sys.exit(backfill(db_path=path, dry_run=dry))
