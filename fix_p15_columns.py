# -*- coding: utf-8 -*-
"""一次性止血脚本：补齐 P1-5 销售退货入库缺失的三列（幂等，可重复执行）。

适用症状（2026-09-12 生产事故）：
    sqlalchemy.exc.OperationalError: (sqlite3.OperationalError)
    no such column: in_order.source_sales_order_id

根因：P1-5 给 in_order / in_order_item 新增的来源销售订单列只加在
app.py auto_migrate_database() 里，而 start_wms_*.bat 默认
WMS_NO_DB_TOUCH=1 会整体跳过它，兜底的 app/fix_db_columns.py 又没同步，
存量库重启后补不上，首页 index() 一查 in_order 就 500。

用法（Windows，在 C:\\wms 目录下执行）：
    python fix_p15_columns.py                 # 自动探测数据库路径
    python fix_p15_columns.py C:\\wms\\app\\instance\\inventory.db   # 指定路径

执行完**重启 WMS 服务**即可（脚本只改表结构，不动任何业务数据）。
"""
from __future__ import annotations

import os
import sqlite3
import sys

# (表名, 列名, ALTER 类型) —— 与 app/app.py auto_migrate_database() 的定义一致
MIGRATIONS = (
    ('in_order', 'source_sales_order_id', 'INTEGER'),
    ('in_order', 'source_sales_order_no', 'VARCHAR(50)'),
    ('in_order_item', 'source_sales_order_item_id', 'INTEGER'),
)


def candidate_paths() -> list[str]:
    """按可能性排序的数据库路径候选（覆盖常见部署布局）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(here, 'app', 'instance', 'inventory.db'),
        os.path.join(here, 'instance', 'inventory.db'),
        os.path.join(here, 'inventory.db'),
        os.path.join(here, 'app', 'inventory.db'),
        os.path.join(here, 'app', 'instance', 'wms.db'),
        os.path.join(here, 'instance', 'wms.db'),
        os.path.join(here, 'wms.db'),
    ]
    env_url = os.environ.get('DATABASE_URL') or os.environ.get('WMS_DATABASE_URI') or ''
    for prefix in ('sqlite:///', 'sqlite://'):
        if env_url.startswith(prefix):
            raw = env_url[len(prefix):]
            if raw and raw != ':memory:':
                cands.insert(0, os.path.abspath(raw))
    seen, out = set(), []
    for p in cands:
        p = os.path.abspath(p)
        if p not in seen and os.path.exists(p):
            seen.add(p)
            out.append(p)
    return out


def _columns(conn, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def fix(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    changed = 0
    try:
        for table, column, ddl_type in MIGRATIONS:
            if not _table_exists(conn, table):
                print(f'  - 跳过 {table}（表不存在，全新库由 db.create_all 建表自带）')
                continue
            cols = _columns(conn, table)
            if column in cols:
                print(f'  - {table}.{column} 已存在')
                continue
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}')
            conn.commit()
            changed += 1
            print(f'  + 已添加 {table}.{column} {ddl_type}')
    finally:
        conn.close()
    return changed


def main() -> int:
    paths = [sys.argv[1]] if len(sys.argv) > 1 else candidate_paths()
    if not paths:
        print('✗ 未找到数据库文件。请显式指定路径：')
        print(r'    python fix_p15_columns.py C:\wms\app\instance\inventory.db')
        return 1
    total = 0
    for path in paths:
        print(f'▶ 处理数据库：{path}')
        total += fix(path)
    print(f'\n✓ 完成，共补列 {total} 处。请重启 WMS 服务。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
