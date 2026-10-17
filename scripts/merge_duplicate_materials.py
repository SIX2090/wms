#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一物多码合并工具（审计 §3.7 / BUG-2026-10-17-014）。

默认 dry-run：只打印将把哪些引用从 loser 改到 keeper、库存/流水如何守恒。
--apply --yes：先整库备份，再在单事务内重挂所有指向 material.id 的外键、
合并 location_inventory 同仓同库位数量、合并 stock 后删除 loser；
可选 --create-unique-index 在无冲突时建 uq_material_dedupe_key。

只依赖标准库 sqlite3，不导入 app。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DEDUPE_CONFLICT_SQL = '''
SELECT lower(replace(replace(trim(coalesce(name,'')), ' ', ''), char(12288), '')) k_name,
       lower(replace(replace(trim(coalesce(spec,'')), ' ', ''), char(12288), '')) k_spec,
       lower(replace(replace(trim(coalesce(brand,'')), ' ', ''), char(12288), '')) k_brand,
       COUNT(*) cnt, GROUP_CONCAT(id) ids, GROUP_CONCAT(code) codes
FROM material GROUP BY k_name, k_spec, k_brand HAVING cnt > 1
'''

INDEX_DDL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_material_dedupe_key ON material ("
    "lower(replace(replace(trim(coalesce(name,'')), ' ', ''), char(12288), '')), "
    "lower(replace(replace(trim(coalesce(spec,'')), ' ', ''), char(12288), '')), "
    "lower(replace(replace(trim(coalesce(brand,'')), ' ', ''), char(12288), '')))"
)


def connect(path, readonly):
    uri = 'file:' + path.replace('\\', '/') + ('?mode=ro' if readonly else '?mode=rw')
    conn = sqlite3.connect(uri, uri=True, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=60000')
    return conn


def material_fk_columns(conn):
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    out = {}
    for t in tables:
        cols = {r['name'] for r in conn.execute('PRAGMA table_info("%s")' % t)}
        if 'material_id' in cols:  # 语义约定列（部分历史表未声明 FK）
            out.setdefault(t, set()).add('material_id')
        for fk in conn.execute('PRAGMA foreign_key_list("%s")' % t):
            if fk['table'] == 'material':
                out.setdefault(t, set()).add(fk['from'])
    return out


def snapshot(conn, ids):
    ids = list(ids)
    ph = ','.join('?' * len(ids))
    rows = {r['id']: dict(r) for r in conn.execute(
        'SELECT * FROM material WHERE id IN (%s)' % ph, ids)}
    txn = {r['material_id']: r['s'] for r in conn.execute(
        'SELECT material_id, SUM(quantity) s FROM stock_transaction WHERE material_id IN (%s) '
        'GROUP BY material_id' % ph, ids)}
    loc = {}
    for r in conn.execute(
            'SELECT material_id, warehouse_id, location, SUM(quantity) s FROM location_inventory '
            'WHERE material_id IN (%s) GROUP BY material_id, warehouse_id, location' % ph, ids):
        loc.setdefault(r['material_id'], []).append(dict(r))
    return rows, txn, loc


def plan(conn, loser, keeper):
    fks = material_fk_columns(conn)
    actions = []
    for table, cols in fks.items():
        for col in cols:
            n = conn.execute('SELECT COUNT(*) FROM "%s" WHERE "%s"=?' % (table, col),
                             (loser,)).fetchone()[0]
            if n:
                actions.append({'table': table, 'column': col, 'rows': n})
    return actions


def backup(conn, db_path, backup_dir):
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / ('manual_merge_%s.db' % datetime.now().strftime('%Y%m%d_%H%M%S'))
    dst = sqlite3.connect(str(target))
    with dst:
        conn.backup(dst)
    dst.close()
    return str(target)


def merge_pair(conn, loser, keeper):
    fks = material_fk_columns(conn)
    # 1. location_inventory 先按 (warehouse, location) 合并，避免唯一约束冲突
    if 'location_inventory' in fks:
        for row in conn.execute(
                'SELECT * FROM location_inventory WHERE material_id=?', (loser,)).fetchall():
            existing = conn.execute(
                'SELECT id, quantity FROM location_inventory WHERE material_id=? '
                'AND warehouse_id IS ? AND location IS ?',
                (keeper, row['warehouse_id'], row['location'])).fetchone()
            if existing:
                conn.execute('UPDATE location_inventory SET quantity=? WHERE id=?',
                             ((existing['quantity'] or 0) + (row['quantity'] or 0), existing['id']))
                conn.execute('DELETE FROM location_inventory WHERE id=?', (row['id'],))
            else:
                conn.execute('UPDATE location_inventory SET material_id=? WHERE id=?',
                             (keeper, row['id']))
    # 2. 其余外键直接改指 keeper
    for table, cols in fks.items():
        if table == 'location_inventory':
            continue
        for col in cols:
            conn.execute('UPDATE "%s" SET "%s"=? WHERE "%s"=?' % (table, col, col),
                         (keeper, loser))
    # 3. 合并总账后删除 loser
    loser_row = conn.execute('SELECT stock, price FROM material WHERE id=?', (loser,)).fetchone()
    keeper_row = conn.execute('SELECT stock, price FROM material WHERE id=?', (keeper,)).fetchone()
    if loser_row is None or keeper_row is None:
        raise RuntimeError('loser/keeper 不存在')
    conn.execute('UPDATE material SET stock=? WHERE id=?',
                 ((keeper_row['stock'] or 0) + (loser_row['stock'] or 0), keeper))
    conn.execute('DELETE FROM material WHERE id=?', (loser,))


def verify(conn):
    fk = conn.execute('PRAGMA foreign_key_check').fetchall()
    dupes = conn.execute(DEDUPE_CONFLICT_SQL).fetchall()
    stock_mismatch = conn.execute(
        'SELECT COUNT(*) FROM material m LEFT JOIN '
        '(SELECT material_id, SUM(quantity) s FROM stock_transaction GROUP BY material_id) t '
        'ON t.material_id=m.id WHERE ABS(m.stock - COALESCE(t.s,0)) > 0.01').fetchone()[0]
    loc_mismatch = 0
    try:
        loc_mismatch = conn.execute(
            'SELECT COUNT(*) FROM (SELECT l.material_id, l.warehouse_id, SUM(l.quantity) loc, '
            'COALESCE((SELECT SUM(quantity) FROM stock_transaction t WHERE t.material_id=l.material_id '
            'AND t.warehouse_id=l.warehouse_id),0) txn FROM location_inventory l '
            'GROUP BY l.material_id,l.warehouse_id HAVING ABS(loc-txn)>0.01)').fetchone()[0]
    except sqlite3.Error:
        pass
    return {'fk_violations': len(fk), 'duplicate_groups': len(dupes),
            'stock_vs_txn_mismatch': stock_mismatch, 'location_vs_txn_mismatch': loc_mismatch}


def main(argv=None):
    p = argparse.ArgumentParser(description='一物多码合并（默认 dry-run）')
    p.add_argument('--db', required=True)
    p.add_argument('--pairs', required=True, help='loser:keeper,loser:keeper')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--yes', action='store_true')
    p.add_argument('--create-unique-index', action='store_true')
    p.add_argument('--backup-dir', default='app/backups')
    p.add_argument('--json', action='store_true')
    args = p.parse_args(argv)

    pairs = []
    for item in args.pairs.split(','):
        if not item.strip():
            continue
        loser, keeper = [int(x) for x in item.split(':')]
        if loser == keeper:
            print('loser 与 keeper 不能相同: %s' % item, file=sys.stderr)
            return 2
        pairs.append((loser, keeper))

    conn = connect(args.db, readonly=not args.apply)
    try:
        losers = [l for l, _ in pairs]
        keepers = [k for _, k in pairs]
        before_rows, before_txn, before_loc = snapshot(conn, losers + keepers)
        report = {'pairs': [], 'backup': None}
        for loser, keeper in pairs:
            if loser not in before_rows or keeper not in before_rows:
                print('material %s 不存在' % (loser if loser not in before_rows else keeper),
                      file=sys.stderr)
                return 2
            report['pairs'].append({'loser': loser, 'keeper': keeper,
                                    'loser_code': before_rows[loser]['code'],
                                    'keeper_code': before_rows[keeper]['code'],
                                    'actions': plan(conn, loser, keeper)})
        if not args.apply:
            report['mode'] = 'dry-run'
            report['before'] = {'stock': {str(i): (before_rows[i]['stock'] or 0)
                                          for i in before_rows},
                                'txn': {str(k): v for k, v in before_txn.items()},
                                'location': {str(k): v for k, v in before_loc.items()}}
            print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
            return 0
        if not args.yes:
            print('拒绝写入：--apply 需要同时提供 --yes', file=sys.stderr)
            return 2
        report['backup'] = backup(conn, args.db, args.backup_dir)
        try:
            conn.execute('BEGIN IMMEDIATE')
            for loser, keeper in pairs:
                merge_pair(conn, loser, keeper)
            if args.create_unique_index:
                conn.execute(INDEX_DDL)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            print('合并失败，已回滚：%s' % exc, file=sys.stderr)
            return 3
        report['after'] = verify(conn)
        report['mode'] = 'applied'
        print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
        return 0 if report['after']['fk_violations'] == 0 else 1
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
