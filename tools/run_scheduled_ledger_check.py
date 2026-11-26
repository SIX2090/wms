#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent daily 09:00 three-ledger reconciliation runner.

Does not import Flask/app.py, does not run startup DDL/migrations, does not
touch any outbound network or other scheduled jobs, and does not modify any
business table. Reads a single consistent SQLite snapshot using the exact
logic of app/services/warehouse_stock_service.py:inventory_reconciliation_summary()
and upserts only the single same-day notification row
(type='inventory_reconciliation', target_id=YYYYMMDD).
"""
from __future__ import annotations

import argparse
from datetime import datetime
from itertools import groupby
import json
import logging
from math import fsum
from operator import itemgetter
from pathlib import Path
import sqlite3
import time

LEDGER_QUANTITY_DECIMALS = 4
LEDGER_EPS = 0.5 * 10 ** -LEDGER_QUANTITY_DECIMALS
STOCK_COMPARE_EPSILON = 1e-6

SOURCE_TABLES = (
    ('in_order', 'in_order', 'order_no'),
    ('out_order', 'out_order', 'order_no'),
    ('adjustment', 'adjustment_order', 'adjustment_no'),
    ('after_sale_out_order', 'after_sale_out_order', 'order_no'),
    ('requisition', 'production_requisition', 'req_no'),
    ('subcontract_issue', 'subcontract_issue', 'issue_no'),
    ('subcontract_receive', 'subcontract_receive', 'receive_no'),
)


def _location_management_enabled(cur: sqlite3.Cursor) -> bool:
    row = cur.execute(
        "SELECT value FROM system_setting WHERE key = 'location_management_enabled'"
    ).fetchone()
    if not row or row[0] is None:
        return False
    return str(row[0]).strip() == '1'


def _build_reconciliation_sql(use_bins: bool) -> str:
    source_keys_sql = ', '.join(f"'{kind}'" for kind, _, _ in SOURCE_TABLES)
    union_parts = [
        "SELECT id, 'stock' AS kind, NULL AS wid, stock AS quantity, 0 AS cnt, code AS extra1, NULL AS old_loc FROM material",
        "SELECT material_id, 'txn', warehouse_id, SUM(quantity), COUNT(*), NULL, NULL "
        "FROM stock_transaction GROUP BY material_id, warehouse_id",
    ]
    for kind, table_name, no_col in SOURCE_TABLES:
        union_parts.append(
            f"SELECT m.material_id, '{kind}', m.warehouse_id, m.quantity, m.reference_id, "
            f"CAST(a.warehouse_id AS TEXT), NULL "
            f"FROM movements m "
            f"JOIN {table_name} doc ON doc.id = m.reference_id "
            f"JOIN aliases a ON a.alias = TRIM(doc.warehouse) "
            f"WHERE m.reference_type = '{kind}' AND m.warehouse_id != a.warehouse_id"
        )
        union_parts.append(
            f"SELECT m.material_id, '{kind}', o.warehouse_id, m.quantity, doc.{no_col}, "
            f"CAST(a.warehouse_id AS TEXT), m.legacy_location "
            f"FROM movements m "
            f"JOIN {table_name} doc ON doc.id = m.reference_id "
            f"JOIN aliases a ON a.alias = TRIM(doc.warehouse) "
            f"LEFT OUTER JOIN owners o ON o.value = m.legacy_location "
            f"WHERE m.reference_type = '{kind}' "
            f"AND m.legacy_location IS NOT NULL "
            f"AND (o.warehouse_id IS NULL OR o.warehouse_id != a.warehouse_id)"
        )
    if use_bins:
        union_parts.append(
            "SELECT material_id, 'bin', warehouse_id, SUM(quantity), COUNT(*), NULL, NULL "
            "FROM location_inventory GROUP BY material_id, warehouse_id"
        )

    unions = '\n    UNION ALL\n    '.join(union_parts)
    return f"""
WITH alias_rows(alias, warehouse_id) AS (
    SELECT name, id FROM warehouse
    UNION ALL
    SELECT code, id FROM warehouse
),
aliases(alias, warehouse_id) AS (
    SELECT alias, MIN(warehouse_id)
    FROM alias_rows
    WHERE alias != ''
    GROUP BY alias
    HAVING MIN(warehouse_id) = MAX(warehouse_id)
),
movements AS (
    SELECT material_id, reference_type, reference_id, warehouse_id,
           CASE WHEN warehouse_id IS NULL THEN location ELSE NULL END AS legacy_location,
           SUM(quantity) AS quantity
    FROM stock_transaction
    WHERE reference_type IN ({source_keys_sql})
      AND (warehouse_id IS NOT NULL OR TRIM(location) != '')
    GROUP BY material_id, reference_type, reference_id, warehouse_id,
             CASE WHEN warehouse_id IS NULL THEN location ELSE NULL END
    HAVING ABS(SUM(quantity)) > {STOCK_COMPARE_EPSILON}
),
owner_claims(value, warehouse_id) AS (
    SELECT TRIM(name), id FROM warehouse
    UNION ALL
    SELECT TRIM(code), id FROM warehouse
    UNION ALL
    SELECT DISTINCT TRIM(location), warehouse_id
    FROM location_inventory
    WHERE warehouse_id IS NOT NULL
),
owners(value, warehouse_id) AS (
    SELECT value, MIN(warehouse_id)
    FROM owner_claims
    WHERE value != ''
    GROUP BY value
    HAVING MIN(warehouse_id) = MAX(warehouse_id)
)
SELECT * FROM (
    {unions}
) AS data
ORDER BY data.id
"""


def compute_reconciliation_summary(db_path: Path) -> tuple[str, str, dict]:
    """Read a single read-only SQLite snapshot and compute the exact summary."""
    uri = f'file:{db_path.resolve().as_posix()}?mode=ro'
    con = sqlite3.connect(uri, uri=True, timeout=15.0)
    try:
        con.execute('PRAGMA query_only = ON')
        con.execute('PRAGMA busy_timeout = 15000')
        cur = con.cursor()
        cur.execute('BEGIN DEFERRED')
        use_bins = _location_management_enabled(cur)
        rows = cur.execute(_build_reconciliation_sql(use_bins)).fetchall()
        cur.execute('COMMIT')
    finally:
        con.close()

    global_diff = bin_diff = warehouse_diff = source_diff = unassigned = 0
    legacy_unknown = legacy_conflicts = 0
    examples = []
    prec = LEDGER_QUANTITY_DECIMALS

    for mid, group in groupby(rows, key=itemgetter(0)):
        code, stock, ledger, bins, source_examples = str(mid), 0, {}, {}, []
        for _, kind, wid, quantity, count, material_code, old_location in group:
            if kind == 'stock':
                code, stock = material_code or str(mid), quantity or 0
            elif kind == 'txn':
                ledger[wid] = quantity or 0
                if wid is None:
                    unassigned += count
            elif kind == 'bin':
                bins[wid] = quantity or 0
            elif old_location is not None:
                if wid is None:
                    legacy_unknown += 1
                    match = '旧位置无法唯一归仓'
                else:
                    legacy_conflicts += 1
                    match = f'旧位置匹配仓库ID {wid}'
                if len(examples) + len(source_examples) < 10:
                    source_examples.append(
                        f'单据 {count} 旧位置「{old_location}」净额 {quantity:g} / {match} / 单据仓库ID {material_code}'
                    )
            else:
                source_diff += 1
                if len(examples) + len(source_examples) < 10:
                    source_examples.append(
                        f'{kind} #{count} 流水仓库ID {wid} 净额 {quantity:g} / 单据仓库ID {material_code}'
                    )
        examples.extend(f'{code} {value}' for value in source_examples)
        txn_total = fsum(ledger.values())
        if abs(stock - txn_total) > LEDGER_EPS:
            global_diff += 1
            if len(examples) < 10:
                examples.append(f'{code} 总账 {stock:.{prec}f} / 流水 {txn_total:.{prec}f}')
        if use_bins:
            bin_total = fsum(bins.values())
            if abs(stock - bin_total) > LEDGER_EPS:
                bin_diff += 1
                if len(examples) < 10:
                    examples.append(f'{code} 总账 {stock:.{prec}f} / 库位 {bin_total:.{prec}f}')
            for wid in sorted((ledger.keys() | bins.keys()) - {None}):
                txn_qty, bin_qty = ledger.get(wid, 0), bins.get(wid, 0)
                if abs(txn_qty - bin_qty) > LEDGER_EPS:
                    warehouse_diff += 1
                    if len(examples) < 10:
                        examples.append(f'{code} 仓库ID {wid} 流水 {txn_qty:.{prec}f} / 库位 {bin_qty:.{prec}f}')

    if global_diff or bin_diff or warehouse_diff or source_diff:
        status = '发现差异'
    elif unassigned:
        status = '数量相符，仓库归属待核'
    else:
        status = '数量相符'

    scope = f'总账与库位差异 {bin_diff}，仓库分布差异 {warehouse_diff}' if use_bins else '库位核对关闭'
    summary = (
        f'总账与流水差异 {global_diff}，{scope}。流水与来源单据仓库不一致 {source_diff} 组。'
        f'仓库外键为空的流水 {unassigned} 条。'
    )
    if legacy_unknown or legacy_conflicts:
        summary += (
            f' 旧位置无法唯一归仓 {legacy_unknown} 组，'
            f'旧位置与来源单据仓库冲突 {legacy_conflicts} 组。'
        )
    if examples:
        summary += ' 差异示例：' + '；'.join(examples)

    metrics = {
        'use_bins': use_bins,
        'status': status,
        'global_diff': global_diff,
        'bin_diff': bin_diff,
        'warehouse_diff': warehouse_diff,
        'source_diff': source_diff,
        'unassigned': unassigned,
        'legacy_unknown': legacy_unknown,
        'legacy_conflicts': legacy_conflicts,
    }
    return '全仓账簿核对 · ' + status, summary, metrics


def upsert_reconciliation_notification(
    db_path: Path, title: str, content: str, *, now: datetime | None = None
) -> dict:
    """Upsert today's single inventory_reconciliation notification with lock retry."""
    now = now or datetime.now()
    target_id = int(now.strftime('%Y%m%d'))
    created_at = now.strftime('%Y-%m-%d %H:%M:%S.%f')
    last_error = None
    for attempt in range(4):
        con = sqlite3.connect(str(db_path.resolve()), timeout=15.0, isolation_level=None)
        try:
            con.execute('PRAGMA busy_timeout = 15000')
            con.execute('BEGIN IMMEDIATE')
            cur = con.execute(
                """
                UPDATE notification
                   SET title = ?,
                       content = ?,
                       is_read = CASE WHEN content != ? THEN 0 ELSE is_read END,
                       created_at = ?
                 WHERE type = 'inventory_reconciliation' AND target_id = ?
                """,
                (title, content, content, created_at, target_id),
            )
            if cur.rowcount == 0:
                con.execute(
                    """
                    INSERT INTO notification (type, target_id, title, content, is_read, created_at)
                    VALUES ('inventory_reconciliation', ?, ?, ?, 0, ?)
                    """,
                    (target_id, title, content, created_at),
                )
                action = 'inserted'
            else:
                action = 'updated'
            con.execute('COMMIT')
            return {'action': action, 'target_id': target_id, 'created_at': created_at}
        except sqlite3.OperationalError as exc:
            last_error = exc
            try:
                con.execute('ROLLBACK')
            except Exception:
                pass
            if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
        finally:
            con.close()
    raise RuntimeError(f'写入全仓账簿核对通知失败（数据库锁超时）: {last_error}')


def run_ledger_check(
    db_path: Path,
    *,
    dry_run: bool = False,
    status_file: Path | None = None,
    now: datetime | None = None,
) -> dict:
    if not db_path.is_file():
        raise FileNotFoundError(f'数据库文件不存在: {db_path}')
    now = now or datetime.now()
    title, content, metrics = compute_reconciliation_summary(db_path)
    write_result = None
    if not dry_run:
        write_result = upsert_reconciliation_notification(db_path, title, content, now=now)
    record = {
        'ok': True,
        'dry_run': dry_run,
        'ran_at': now.isoformat(timespec='seconds'),
        'database': str(db_path.resolve()),
        'title': title,
        'content': content,
        'metrics': metrics,
        'write_result': write_result,
    }
    if status_file is not None and not dry_run:
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='独立执行每日全仓三账核对并写入当日站内通知，不加载WMS应用或外发任务'
    )
    parser.add_argument('--source', type=Path, required=True, help='SQLite 数据库路径')
    parser.add_argument('--status-file', type=Path, default=None, help='最近一次运行结果 JSON 路径')
    parser.add_argument('--dry-run', action='store_true', help='仅只读计算并输出结果，不写通知')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        record = run_ledger_check(
            args.source,
            dry_run=args.dry_run,
            status_file=args.status_file,
        )
        logging.info('%s | %s', record['title'], record['content'])
        return 0
    except Exception:
        logging.exception('每日全仓三账核对执行失败')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
