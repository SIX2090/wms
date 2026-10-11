#!/usr/bin/env python3
"""离线数据库恢复工具（F1.2 / P0-1）。

用法:
    python scripts/restore_backup.py <备份文件> [--db <目标库路径>] [--yes]

安全约束（不可绕过）：
1. **必须停机恢复**：检测到目标库被占用（WMS 在跑）直接拒绝——
   运行中覆盖 SQLite 文件会双写撕裂；
2. **恢复前校验备份**：PRAGMA integrity_check 不过绝不落盘；
3. **覆盖前自动留底**：当前库先复制为 <db>.before_restore_<时间戳>，
   恢复出错可立即回滚；
4. 恢复后再做一次 integrity_check + 行数抽样比对并打印，供人工确认。
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'app', 'instance', 'inventory.db')


def _integrity_ok(path: str) -> bool:
    try:
        conn = sqlite3.connect(path, timeout=30)
        try:
            row = conn.execute('PRAGMA integrity_check').fetchone()
            return bool(row and row[0] == 'ok')
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def _db_locked(path: str) -> bool:
    """探测目标库是否被别的进程打开（Windows 独占打开测试 + 写锁测试）。"""
    if not os.path.exists(path):
        return False
    try:
        conn = sqlite3.connect(path, timeout=1)
        try:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('ROLLBACK')
        finally:
            conn.close()
        return False
    except sqlite3.OperationalError:
        return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='WMS 离线数据库恢复')
    parser.add_argument('backup', help='备份文件路径')
    parser.add_argument('--db', default=DEFAULT_DB, help='目标库路径（默认 app/instance/inventory.db）')
    parser.add_argument('--yes', action='store_true', help='跳过人工确认（脚本化调用）')
    args = parser.parse_args(argv)

    backup, target = os.path.abspath(args.backup), os.path.abspath(args.db)
    if not os.path.exists(backup):
        print(f'[restore] 备份文件不存在: {backup}', file=sys.stderr)
        return 2

    print('[restore] 1/5 校验备份完整性...')
    if not _integrity_ok(backup):
        print('[restore] 备份 integrity_check 未通过，拒绝恢复！', file=sys.stderr)
        return 2
    print('[restore]    integrity_check = ok')

    print('[restore] 2/5 检查目标库是否停机...')
    if _db_locked(target):
        print('[restore] 目标库正被使用（WMS 未停止？），拒绝在线覆盖！', file=sys.stderr)
        print('[restore] 请先停止 WMS 服务再运行本脚本。', file=sys.stderr)
        return 3

    if not args.yes:
        print(f'[restore] 即将用 {backup}')
        print(f'[restore] 覆盖   {target}')
        answer = input('[restore] 确认恢复？输入 yes 继续: ').strip().lower()
        if answer != 'yes':
            print('[restore] 已取消。')
            return 1

    print('[restore] 3/5 覆盖前留底当前库...')
    safety = None
    if os.path.exists(target):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safety = f'{target}.before_restore_{stamp}'
        # 留底也用在线备份（虽然已停机，但保持一致语义），失败则退回冷拷贝
        try:
            src_uri = f"file:{target.replace(os.sep, '/')}?mode=ro"
            src = sqlite3.connect(src_uri, uri=True, timeout=30)
            try:
                dst = sqlite3.connect(safety, timeout=30)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
        except sqlite3.Error:
            shutil.copy2(target, safety)
        print(f'[restore]    当前库已留底: {safety}')

    print('[restore] 4/5 执行恢复...')
    try:
        shutil.copy2(backup, target)
    except OSError as exc:
        print(f'[restore] 覆盖失败: {exc}', file=sys.stderr)
        return 2

    print('[restore] 5/5 恢复后校验...')
    if not _integrity_ok(target):
        print('[restore] 恢复后 integrity_check 未通过！', file=sys.stderr)
        if safety:
            print(f'[restore] 请用留底文件回滚: {safety}', file=sys.stderr)
        return 2
    conn = sqlite3.connect(target, timeout=30)
    try:
        has_tx = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stock_transaction'"
        ).fetchone()
        if has_tx:
            rows = conn.execute('SELECT COUNT(*) FROM stock_transaction').fetchone()[0]
            latest = conn.execute('SELECT MAX(created_at) FROM stock_transaction').fetchone()[0]
            print(f'[restore]    integrity_check = ok, stock_transaction 行数={rows}, 最新事务={latest}')
        else:
            tables = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            print(f'[restore]    integrity_check = ok（非 WMS 库结构，表数={tables}）')
    finally:
        conn.close()
    print('[restore] 恢复完成。请启动 WMS 并人工抽查关键单据。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
