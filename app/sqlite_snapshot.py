"""Publish a verified SQLite snapshot without damaging an earlier backup.

Standard library only; safe to import before Flask or any database startup.
"""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import time


def snapshot_connection(source, destination, *, timeout=30):
    """Snapshot an existing connection, then atomically replace the destination."""
    target = Path(destination)
    if target.is_symlink():
        raise OSError('备份目标不能是链接，请使用独立备份文件')
    target = target.resolve()
    database = next((row[2] for row in source.execute('PRAGMA database_list') if row[1] == 'main'), '')
    if database:
        original = Path(database).resolve()
        if target == original or (target.exists() and os.path.samefile(original, target)):
            raise OSError('源库与备份目标是同一文件，拒绝备份')
    if any(Path(str(target) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise OSError('备份目标有SQLite事务旁文件，请使用独立备份路径')
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.wms-snapshot-', suffix='.db', dir=target.parent)
    os.close(descriptor)
    staging = Path(name)
    deadline = time.monotonic() + timeout

    def _check_deadline(*unused):
        if time.monotonic() > deadline:
            raise TimeoutError('SQLite备份等待超时，原备份保持不变')

    try:
        with closing(sqlite3.connect(staging, timeout=timeout)) as output:
            source.backup(output, pages=256, progress=_check_deadline, sleep=0.05)
            _check_deadline()
            output.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
            if output.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise sqlite3.DatabaseError('备份完整性校验失败，原备份保持不变')
        with staging.open('r+b') as completed:
            os.fsync(completed.fileno())
        if any(Path(str(target) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
            raise OSError('发布前备份目标出现SQLite事务旁文件，原文件保持不变')
        # No live source connection is ever opened on the destination pathname.
        # On failure only our staging file is removed, never an earlier backup.
        os.replace(staging, target)
    finally:
        staging.unlink(missing_ok=True)


def create_snapshot(source, destination, *, timeout=30):
    """Read a correctly escaped file URI; do not create or modify the source."""
    original = Path(source).resolve(strict=True)
    with closing(sqlite3.connect(original.as_uri() + '?mode=ro', uri=True, timeout=timeout)) as connection:
        snapshot_connection(connection, destination, timeout=timeout)
