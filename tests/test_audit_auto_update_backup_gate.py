# -*- coding: utf-8 -*-
"""A15 回归锁：更新前备份失败必须阻断本轮代码更新。

AUDIT-FULL-20261016-001-F09-F05（原 A15）：backup_database 旧实现失败只记警告，
main() 随后照常 pull —— 没有可用备份也会改代码。现在返回 bool，main 显式跳过。
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
sys.path.insert(0, str(APP_DIR))
import auto_update  # noqa: E402


def _prepare(tmp_path, make_db):
    app_dir = tmp_path / 'app'
    (app_dir / 'instance').mkdir(parents=True)
    db = app_dir / 'instance' / 'inventory.db'
    make_db(db)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(auto_update, 'APP_DIR', app_dir)
    monkeypatch.setattr(auto_update, 'ROOT_DIR', tmp_path)
    monkeypatch.setattr(auto_update, 'log', lambda *a, **k: None)
    return db, monkeypatch


def test_backup_success_returns_true(tmp_path):
    def make(db):
        conn = sqlite3.connect(str(db))
        conn.execute('create table t (id integer primary key, v text)')
        conn.execute("insert into t (v) values ('x')")
        conn.commit()
        conn.close()

    _, mp = _prepare(tmp_path, make)
    try:
        assert auto_update.backup_database() is True
        backups = list((tmp_path / 'backups').glob('before_auto_update_*.db'))
        assert len(backups) == 1
        conn = sqlite3.connect(str(backups[0]))
        try:
            assert conn.execute('pragma integrity_check').fetchone()[0] == 'ok'
        finally:
            conn.close()
    finally:
        mp.undo()


def test_backup_failure_returns_false(tmp_path):
    def make(db):
        db.write_bytes(b'this is not a sqlite database at all')

    _, mp = _prepare(tmp_path, make)
    try:
        assert auto_update.backup_database() is False
    finally:
        mp.undo()


def test_missing_database_does_not_block(tmp_path):
    def make(db):
        db.unlink(missing_ok=True)

    _, mp = _prepare(tmp_path, make)
    try:
        assert auto_update.backup_database() is True
    finally:
        mp.undo()


def test_main_skips_pull_when_backup_fails():
    source = (APP_DIR / 'auto_update.py').read_text(encoding='utf-8')
    assert 'if not backup_database():' in source
    assert '已跳过本次代码更新' in source
