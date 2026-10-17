# -*- coding: utf-8 -*-
"""BUG-2026-10-17-012-F05：启动备份防抖 + 旁文件清理。

2026-10-17 实测 37 秒内启动 10 次、生成 10 份全库备份，把正常快照挤出保留窗口；
清理只删 .db 还留下 -wal/-shm 孤儿。
"""
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as wms  # noqa: E402


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db_path = tmp_path / 'inventory.db'
    conn = sqlite3.connect(str(db_path))
    conn.execute('create table t (id integer primary key)')
    conn.commit()
    conn.close()
    backup_dir = tmp_path / 'backups'
    with wms.app.app_context():
        monkeypatch.setitem(wms.app.config, 'TESTING', False)
        monkeypatch.setitem(wms.app.config, 'SQLALCHEMY_DATABASE_URI', 'sqlite:///' + db_path.as_posix())
        monkeypatch.setitem(wms.app.config, 'BACKUP_FOLDER', str(backup_dir))
        monkeypatch.setenv('WMS_STARTUP_BACKUP_MIN_INTERVAL_SECONDS', '600')
        yield backup_dir


def test_second_startup_within_interval_is_skipped(env):
    wms.backup_sqlite_on_startup()
    first = list(env.glob('auto_startup_*.db'))
    assert len(first) == 1
    wms.backup_sqlite_on_startup()
    assert len(list(env.glob('auto_startup_*.db'))) == 1


def test_retention_removes_db_and_sidecars(env, monkeypatch):
    monkeypatch.setenv('WMS_STARTUP_BACKUP_KEEP', '2')
    env.mkdir(parents=True, exist_ok=True)
    base = time.time() - 3600
    for i in range(4):
        p = env / f'auto_startup_20260101_00000{i}.db'
        p.write_bytes(b'x')
        (env / (p.name + '-wal')).write_bytes(b'w')
        os.utime(p, (base + i, base + i))
    wms.backup_sqlite_on_startup()
    names = sorted(p.name for p in env.glob('auto_startup_*.db'))
    assert len(names) == 2
    # 旁文件只能随被保留的 .db 存在；被裁剪的 .db 不得留下孤儿 -wal。
    for wal in env.glob('auto_startup_*-wal'):
        assert Path(str(wal)[:-4]).exists(), wal
