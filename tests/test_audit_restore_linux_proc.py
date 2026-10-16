"""Linux CI复发锁：不可读的无关FD不代表SQLite目标被占用。"""
import importlib.util
import os
from pathlib import Path

import pytest


@pytest.fixture
def restore():
    source = Path(__file__).resolve().parents[1] / 'scripts/restore_backup.py'
    spec = importlib.util.spec_from_file_location('linux_restore_fixture', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scene(tmp_path):
    target = tmp_path / 'offline.db'
    target.write_bytes(b'only inode identity is inspected')
    proc = tmp_path / 'proc'
    blocked = proc / '101' / 'fd'
    readable = proc / '102' / 'fd'
    blocked.mkdir(parents=True)
    readable.mkdir(parents=True)
    return target, proc, blocked, readable


def test_unreadable_unrelated_process_is_not_target_usage(restore, tmp_path, monkeypatch):
    target, proc, blocked, readable = _scene(tmp_path)
    original = Path.iterdir
    def restricted(path):
        if path == blocked:
            raise PermissionError('protected unrelated process')
        return original(path)
    monkeypatch.setattr(Path, 'iterdir', restricted)
    assert not restore._linux_has_open_file(target, proc, target.stat().st_uid)


def test_unreadable_unrelated_fd_does_not_hide_visible_target(restore, tmp_path, monkeypatch):
    target, proc, blocked, readable = _scene(tmp_path)
    unrelated = blocked / '3'
    unrelated.write_bytes(b'unrelated')
    os.link(target, readable / '4')
    original = Path.stat
    def restricted(path, *args, **kwargs):
        if path == unrelated:
            raise PermissionError('unrelated anonymous fd')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', restricted)
    assert restore._linux_has_open_file(target, proc, target.stat().st_uid)


def test_unreadable_single_fd_does_not_block_offline_restore(restore, tmp_path, monkeypatch):
    target, proc, blocked, readable = _scene(tmp_path)
    unrelated = blocked / '3'
    unrelated.write_bytes(b'unrelated')
    original = Path.stat
    def restricted(path, *args, **kwargs):
        if path == unrelated:
            raise PermissionError('unrelated anonymous fd')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', restricted)
    assert not restore._linux_has_open_file(target, proc, target.stat().st_uid)
