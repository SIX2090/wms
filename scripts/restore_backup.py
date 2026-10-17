#!/usr/bin/env python3
"""离线WMS恢复：占用检测、结构校验、一致留底和SQLite事务恢复。

Windows使用无共享句柄；Linux仅支持当前用户拥有的离线库，检查进程FD。
其他平台拒绝恢复。操作员必须保持服务停止；不冷拷贝主库或删除WAL。
"""
import argparse
import ctypes
import os
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from runtime_guard import acquire_database_lease

# Repair task: AUDIT-FULL-20261016-001-F01
DEFAULT_DB = str(Path(__file__).resolve().parents[1] / 'app/instance/inventory.db')
REQUIRED_SCHEMA = {
    'material': {'id', 'code', 'stock'},
    'warehouse': {'id', 'name'},
    'stock_transaction': {'id', 'material_id', 'quantity', 'warehouse_id', 'created_at'},
    'in_order': {'id', 'order_no', 'status'},
    'out_order': {'id', 'order_no', 'status'},
    'user': {'id', 'username', 'password_hash', 'role'},
    'system_setting': {'id', 'key', 'value'},
}


def _read_connection(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=5)


def _integrity_ok(path):
    try:
        with closing(_read_connection(path)) as conn:
            return conn.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    except (OSError, sqlite3.Error):
        return False


def _schema_error(path):
    try:
        with closing(_read_connection(path)) as conn:
            for table, required in REQUIRED_SCHEMA.items():
                # 表名固定为内部白名单，不接受用户SQL标识符。
                columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
                if not required.issubset(columns):
                    return f'{table} 缺少字段：{", ".join(sorted(required - columns))}'
    except (OSError, sqlite3.Error) as exc:
        return str(exc)
    return None


def _db_locked(path):
    """检测空闲打开连接；不能用SQLite写锁代替停机证明。"""
    if not os.path.exists(path):
        return False
    if sys.platform == 'win32':
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        create = kernel.CreateFileW
        create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                           wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        create.restype = wintypes.HANDLE
        handle = create(str(Path(path).resolve()), 0xC0000000, 0, None, 3, 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            return True
        close = kernel.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        return not bool(close(handle))
    if sys.platform.startswith('linux') and Path('/proc/self/fd').is_dir():
        return _linux_has_open_file(path)
    return True


def _linux_has_open_file(path, proc_root=Path('/proc'), current_uid=None):
    """Linux开发/CI的可见FD补充检查；WMS互斥由全程运行锁保证。

    无关进程的受保护FD可能无法stat，不能据此虚构目标已打开。
    可见目标FD仍必须拒绝；跨用户目标不支持恢复。Windows生产检查不受此分支影响。
    """
    uid = os.getuid() if current_uid is None else current_uid
    target = os.stat(path)
    if target.st_uid != uid:
        return True
    identity = (target.st_dev, target.st_ino)
    for process in Path(proc_root).iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != uid:
                continue
            for fd in (process / 'fd').iterdir():
                try:
                    stat = fd.stat()
                    if (stat.st_dev, stat.st_ino) == identity:
                        return True
                except (FileNotFoundError, PermissionError):
                    continue
        except (FileNotFoundError, PermissionError):
            continue
    return False


def _snapshot(source, destination):
    """SQLite事务快照，失败回滚，等待超时不能无限循环。"""
    deadline = time.monotonic() + 30
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError('SQLite备份等待超时，请确认服务已停止及磁盘可写')
    with closing(_read_connection(source)) as src:
        with closing(sqlite3.connect(destination, timeout=5)) as dst:
            src.backup(dst, pages=256, progress=progress, sleep=0.05)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='WMS 离线数据库恢复')
    parser.add_argument('backup', help='备份文件路径')
    parser.add_argument('--db', default=DEFAULT_DB, help='目标WMS库路径')
    parser.add_argument('--yes', action='store_true', help='仅跳过人工确认，不跳过安全检查')
    parser.add_argument('--validate-only', action='store_true', help='只读校验输入库，不恢复、迁移或初始化')
    args = parser.parse_args(argv)
    # Repair task: AUDIT-FULL-20261016-001-F05；安装已有库时复用校验，绝不进入恢复链。
    if args.validate_only:
        candidate = Path(args.backup).resolve()
        if not candidate.is_file() or not _integrity_ok(candidate) or _schema_error(candidate):
            print('[validate] 不是完整的WMS数据库，保留原文件，请人工检查。', file=sys.stderr)
            return 2
        print('[validate] WMS数据库只读校验通过，未恢复、迁移或初始化。')
        return 0
    backup, target = Path(args.backup).resolve(), Path(args.db).resolve()
    if not backup.is_file() or backup == target or (target.exists() and os.path.samefile(backup, target)):
        print('[restore] 备份不存在或与目标为同一文件，拒绝恢复。', file=sys.stderr)
        return 2
    lease = None
    try:
        lease = acquire_database_lease(target)
        if _db_locked(target):
            print('[restore] 目标库仍被打开或无法确认停机，拒绝恢复。请先停止WMS。', file=sys.stderr)
            return 3
        if not _integrity_ok(backup) or _schema_error(backup):
            print('[restore] 备份不是完整的WMS数据库，拒绝恢复。', file=sys.stderr)
            return 2
        if not args.yes and input(f'[restore] 将用 {backup} 恢复 {target}；输入 yes 确认：').strip().lower() != 'yes':
            return 1
        if not target.parent.is_dir():
            print('[restore] 目标目录不存在，拒绝隐式创建部署目录。', file=sys.stderr)
            return 2
        with tempfile.TemporaryDirectory(prefix='.wms-restore-', dir=target.parent) as staging:
            prepared = Path(staging) / 'validated.db'
            _snapshot(backup, prepared)
            if not _integrity_ok(prepared) or _schema_error(prepared):
                print('[restore] 暂存快照校验失败，目标库未改动。', file=sys.stderr)
                return 2
            if _db_locked(target):
                print('[restore] 确认后目标被重新打开，拒绝恢复。', file=sys.stderr)
                return 3
            if target.exists():
                safety = str(target) + '.before_restore_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                _snapshot(target, safety)
                if not _integrity_ok(safety):
                    raise OSError('恢复前留底校验失败，目标库未改动')
                print(f'[restore] 当前库已留底: {safety}')
            if _db_locked(target):
                print('[restore] 留底期间目标被重新打开，拒绝恢复。', file=sys.stderr)
                return 3
            _snapshot(prepared, target)
            if not _integrity_ok(target) or _schema_error(target):
                raise OSError('恢复后校验失败，请保留现场并使用留底文件人工处理')
        print('[restore] 恢复完成，WMS结构及完整性检查通过。请启动并人工抽查关键单据。')
        return 0
    except RuntimeError as exc:
        print(f'[restore] {exc}', file=sys.stderr)
        return 3
    except (OSError, sqlite3.Error, TimeoutError) as exc:
        print(f'[restore] 恢复未完成：{exc}；请保留恢复前留底并检查磁盘/服务状态。', file=sys.stderr)
        return 2
    finally:
        if lease is not None:
            lease.close()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
