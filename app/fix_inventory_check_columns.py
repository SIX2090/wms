# -*- coding: utf-8 -*-
"""一键补齐盘点域缺列（BUG-2026-09-05-001）——不重启也能止血。

背景：盘点域迁移列（inventory_check.frozen_at、
inventory_check_item.counted_by / counted_at / area、
inventory_check_scan.check_id、inventory_check_scan_item.area）
只在 ``app.py`` 的 ``auto_migrate_database()`` 里 ADD COLUMN，而
``WMS_NO_DB_TOUCH=1`` 会整体跳过迁移函数——存量库重启也补不上，
物料编辑保存时命中缺列报
``no such column: inventory_check_item.counted_by`` → 500。

``app.py`` 已新增启动期自愈 ``ensure_inventory_check_columns()``（拉代码
重启即自动补列）。本脚本用于**不方便立刻重启**的场景：直接用 Python 跑
一次即可补齐，随后重启服务让新代码生效。

用法（任意一种）：
    python app/fix_inventory_check_columns.py
    python app/fix_inventory_check_columns.py c:\\wms\\app\\instance\\inventory.db
    双击仓库根目录 fix_inventory_check_columns.bat

特性：
- 幂等：已存在的列不重复 ALTER，可反复执行
- 只 ADD 可空列，不动、不删任何存量数据
- 自动定位数据库（显式参数 → DATABASE_URL → app/instance/inventory.db
  → 上级 instance/inventory.db → 扫描 app/instance/*.db）
- 执行后回读 PRAGMA 校验并打印每个表的最终列清单

注意：列清单必须与 ``app.py`` 的 ``ensure_inventory_check_columns()``
保持一致（由 tests/test_fix_inventory_check_columns.py 断言防漂移）。
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

# (表名, 列信息语句, ((列名, ALTER 语句), ...))
# 表名/列名均为固定白名单标识符（非用户输入），无注入风险。
CHECK_COLUMN_MIGRATIONS = (
    ('inventory_check', 'PRAGMA table_info(inventory_check)', (
        ('frozen_at',
         'ALTER TABLE inventory_check ADD COLUMN frozen_at DATETIME'),
    )),
    ('inventory_check_item', 'PRAGMA table_info(inventory_check_item)', (
        ('counted_by',
         'ALTER TABLE inventory_check_item ADD COLUMN counted_by INTEGER'),
        ('counted_at',
         'ALTER TABLE inventory_check_item ADD COLUMN counted_at DATETIME'),
        ('area',
         "ALTER TABLE inventory_check_item ADD COLUMN area VARCHAR(100) DEFAULT ''"),
    )),
    ('inventory_check_scan', 'PRAGMA table_info(inventory_check_scan)', (
        ('check_id',
         'ALTER TABLE inventory_check_scan ADD COLUMN check_id INTEGER'),
    )),
    ('inventory_check_scan_item', 'PRAGMA table_info(inventory_check_scan_item)', (
        ('area',
         "ALTER TABLE inventory_check_scan_item ADD COLUMN area VARCHAR(100) DEFAULT ''"),
    )),
)


def _candidate_paths(explicit: str | None = None) -> list[Path]:
    here = Path(__file__).resolve().parent  # app/
    root = here.parent
    paths: list[Path] = []
    if explicit:
        paths.append(Path(explicit))
    url = os.environ.get('DATABASE_URL') or ''
    if url.startswith('sqlite:///') and url != 'sqlite:///:memory:':
        raw = url[len('sqlite:///'):]
        paths.append(Path(raw) if os.path.isabs(raw) else here / raw)
    paths += [
        here / 'instance' / 'inventory.db',
        root / 'instance' / 'inventory.db',
        root / 'app' / 'instance' / 'inventory.db',
    ]
    # 兜底扫描：app/instance 下唯一的 .db 文件
    inst = here / 'instance'
    if inst.is_dir():
        dbs = sorted(inst.glob('*.db'))
        if len(dbs) == 1:
            paths.append(dbs[0])
    return paths


def resolve_db_path(explicit: str | None = None) -> Path | None:
    """按优先级返回第一个真实存在的数据库文件；找不到返回 None。"""
    for p in _candidate_paths(explicit):
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def fix(db_path: str | Path) -> list[str]:
    """补齐盘点域缺列，返回本次实际补上的 `表.列` 列表（幂等）。"""
    added: list[str] = []
    conn = sqlite3.connect(str(db_path), timeout=60)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('PRAGMA busy_timeout=60000')
        for tbl, pragma, col_stmts in CHECK_COLUMN_MIGRATIONS:
            exists = cur.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (tbl,),
            ).fetchone()
            if not exists:
                # 全新库：盘点表由启动期 db.create_all() 建全量列，无需补列
                continue
            cur.execute(pragma)
            cols = {r['name'] for r in cur.fetchall()}
            for col, stmt in col_stmts:
                if col in cols:
                    continue
                cur.execute(stmt)
                cols.add(col)
                added.append(f'{tbl}.{col}')
        conn.commit()
    finally:
        conn.close()
    return added


def main(argv: list[str]) -> int:
    """CLI 入口：定位数据库 → 补列 → 回读校验 → 提示重启。"""
    explicit = argv[1] if len(argv) > 1 else None
    db_path = resolve_db_path(explicit)
    if db_path is None:
        searched = '\n  '.join(str(p) for p in _candidate_paths(explicit))
        print('[ERROR] 未找到数据库文件，已尝试：\n  ' + searched)  # allow-print
        print('        用法: python app/fix_inventory_check_columns.py <db路径>')  # allow-print
        return 1

    print(f'[INFO] 数据库: {db_path}')  # allow-print
    try:
        added = fix(db_path)
    except sqlite3.Error as exc:
        print(f'[ERROR] 补列失败: {exc}')  # allow-print
        return 1

    if added:
        print('[OK] 已补列: ' + ', '.join(added))  # allow-print
    else:
        print('[OK] 盘点域列已齐全，无需补列（幂等，未做任何修改）')  # allow-print

    # 回读校验
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        for tbl, pragma, col_stmts in CHECK_COLUMN_MIGRATIONS:
            if not conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
            ).fetchone():
                continue
            cols = [r[1] for r in conn.execute(pragma).fetchall()]
            missing = [c for c, _ in col_stmts if c not in cols]
            flag = 'OK' if not missing else f'仍缺 {missing}'
            print(f'[校验] {tbl}: {len(cols)} 列 -> {flag}')  # allow-print
    finally:
        conn.close()

    print('[提示] 补列只 ADD 可空列，不动存量数据；请重启 WMS 服务让新代码生效。')  # allow-print
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
