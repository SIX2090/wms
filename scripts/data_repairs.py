#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计数据修复工具（BUG-2026-10-17-013-F04）。

只读优先：默认 dry-run 只输出问题清单，不写库；写入必须显式 --apply-* 且 --yes。
不导入 app（避免生产硬门禁与迁移副作用），只用标准库 sqlite3。

覆盖：
1. 外键完整性（PRAGMA foreign_key_check）与 ai_cleanup_log.executed_by 脏值；
2. 物料一物多码（与 app.py MATERIAL_DEDUPE 同口径：去空格/全角空格 + 不分大小写 + 品牌）；
3. 三账：总账 vs 流水净额；库位账 vs 同仓流水净额（仅判存在库位账行的物料）。

用法：
  python scripts/data_repairs.py --db app/instance/inventory.db            # 只读报告
  python scripts/data_repairs.py --db app/instance/inventory.db --json
  python scripts/data_repairs.py --db app/instance/inventory.db --apply-fk --yes
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

DEDUPE_KEY = ("lower(replace(replace(trim(coalesce({col},'')), ' ', ''), char(12288), ''))")


def _connect(path, readonly):
    uri = 'file:' + path.replace('\\', '/') + ('?mode=ro' if readonly else '?mode=rw')
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def collect(conn):
    report = {'fk_violations': [], 'ai_cleanup_bad_executor': [],
              'duplicate_materials': [], 'stock_vs_txn': [],
              'location_vs_txn': []}
    report['fk_violations'] = [dict(r) for r in conn.execute('PRAGMA foreign_key_check').fetchall()]
    try:
        report['ai_cleanup_bad_executor'] = [dict(r) for r in conn.execute(
            'SELECT id, log_id, executed_by FROM ai_cleanup_log '
            'WHERE executed_by IS NULL OR executed_by <= 0 '
            'OR executed_by NOT IN (SELECT id FROM user)').fetchall()]
    except sqlite3.Error:
        pass
    key = {'kn': DEDUPE_KEY.format(col='name'),
           'ks': DEDUPE_KEY.format(col='spec'),
           'kb': DEDUPE_KEY.format(col='brand')}
    sql = ("SELECT {kn} AS k_name, {ks} AS k_spec, {kb} AS k_brand, COUNT(*) AS cnt, "
           "GROUP_CONCAT(code) AS codes FROM material GROUP BY k_name, k_spec, k_brand "
           "HAVING cnt > 1").format(**key)
    try:
        report['duplicate_materials'] = [dict(r) for r in conn.execute(sql).fetchall()]
    except sqlite3.Error:
        pass
    try:
        report['stock_vs_txn'] = [dict(r) for r in conn.execute(
            'SELECT m.id, m.code, ROUND(m.stock,4) AS stock, ROUND(COALESCE(t.s,0),4) AS txn '
            'FROM material m LEFT JOIN (SELECT material_id, SUM(quantity) s FROM stock_transaction '
            'GROUP BY material_id) t ON t.material_id = m.id '
            'WHERE ABS(m.stock - COALESCE(t.s,0)) > 0.01').fetchall()]
        report['location_vs_txn'] = [dict(r) for r in conn.execute(
            'SELECT l.material_id, l.warehouse_id, ROUND(SUM(l.quantity),4) AS loc, '
            'ROUND(COALESCE(t.s,0),4) AS txn FROM location_inventory l '
            'LEFT JOIN (SELECT material_id, warehouse_id, SUM(quantity) s FROM stock_transaction '
            'GROUP BY material_id, warehouse_id) t '
            'ON t.material_id = l.material_id AND t.warehouse_id = l.warehouse_id '
            'GROUP BY l.material_id, l.warehouse_id '
            'HAVING ABS(SUM(l.quantity) - COALESCE(t.s,0)) > 0.01').fetchall()]
    except sqlite3.Error:
        pass
    return report


def fix_ai_cleanup(conn):
    row = conn.execute('SELECT id FROM user ORDER BY id LIMIT 1').fetchone()
    if row is None:
        return 0, '库里没有任何 user，无法回填 executed_by'
    executor = row['id']
    cur = conn.execute(
        'UPDATE ai_cleanup_log SET executed_by = ? '
        'WHERE executed_by IS NULL OR executed_by <= 0 '
        'OR executed_by NOT IN (SELECT id FROM user)', (executor,))
    conn.commit()
    return cur.rowcount, f'已回填 executed_by={executor}'


def main(argv=None):
    parser = argparse.ArgumentParser(description='WMS 审计数据修复（默认只读）')
    parser.add_argument('--db', required=True)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--apply-fk', action='store_true',
                        help='把 ai_cleanup_log 的非法 executed_by 回填为最小 user.id')
    parser.add_argument('--yes', action='store_true', help='确认执行写入')
    args = parser.parse_args(argv)
    try:
        conn = _connect(args.db, readonly=not (args.apply_fk and args.yes))
        report = collect(conn)
        applied = None
        if args.apply_fk:
            if not args.yes:
                print('拒绝写入：--apply-fk 需要同时提供 --yes', file=sys.stderr)
                return 2
            applied = fix_ai_cleanup(conn)
        conn.close()
    except (sqlite3.Error, OSError) as exc:
        print(f'读取失败：{exc}', file=sys.stderr)
        return 2
    counts = {k: len(v) for k, v in report.items()}
    if args.json:
        print(json.dumps({'counts': counts, 'applied': applied, 'report': report},
                         ensure_ascii=False, indent=2, default=str))
    else:
        print('== WMS 审计数据检查（只读）==')
        for key, value in counts.items():
            print(f'  {key}: {value}')
        for key in ('ai_cleanup_bad_executor', 'duplicate_materials', 'stock_vs_txn', 'location_vs_txn'):
            for row in report[key][:10]:
                print(f'  [{key}] {dict(row)}')
        if applied:
            print(f'  applied: {applied}')
        print('提示：一物多码/库位账差异不自动修，需人工确认后用业务页面处理。')
    return 1 if any(counts.values()) else 0


if __name__ == '__main__':
    sys.exit(main())
