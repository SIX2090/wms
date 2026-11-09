"""Owned fake files: conflicting targets must be rejected before any SQLite I/O."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_restore():
    spec = importlib.util.spec_from_file_location('sidecar_restore', ROOT / 'scripts/restore_backup.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('suffix', ['-wal', '-shm', '-journal'])
@pytest.mark.parametrize('target_exists', [False, True])
def test_restore_refuses_target_sidecars_without_opening_any_database(tmp_path, monkeypatch, suffix, target_exists):
    module = load_restore()
    source = tmp_path / 'source.db'; source.write_bytes(b'owned fake source')
    target = tmp_path / 'target.db'
    if target_exists:
        target.write_bytes(b'owned fake target')
    sidecar = Path(str(target) + suffix); sidecar.write_bytes(b'owned fake sidecar')
    def refuse_sql(*args, **kwargs):
        raise AssertionError('sidecar refusal must precede any database connection')
    monkeypatch.setattr(module, '_read_connection', refuse_sql)
    assert module.main([str(source), '--db', str(target), '--yes']) == 3
    assert source.read_bytes() == b'owned fake source'
    assert target.exists() == target_exists
    if target_exists:
        assert target.read_bytes() == b'owned fake target'
    assert sidecar.read_bytes() == b'owned fake sidecar'


@pytest.mark.parametrize('stage', ['prepared', 'safety'])
def test_restore_rechecks_sidecars_after_preparation_and_safety_snapshot(tmp_path, monkeypatch, stage):
    module = load_restore()
    source = tmp_path / 'source.db'; source.write_bytes(b'owned source')
    target = tmp_path / 'target.db'; target.write_bytes(b'owned target')
    sidecar = Path(str(target) + '-wal'); calls = []
    @contextmanager
    def staging(**kwargs):
        yield str(tmp_path)
    def snapshot(origin, destination):
        calls.append((Path(origin), Path(destination)))
        Path(destination).write_bytes(Path(origin).read_bytes())
        if len(calls) == (1 if stage == 'prepared' else 2):
            sidecar.write_bytes(b'owned late sidecar')
    monkeypatch.setattr(module, 'acquire_database_lease', lambda *_: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(module, '_db_locked', lambda *_: False)
    monkeypatch.setattr(module, '_integrity_ok', lambda *_: True)
    monkeypatch.setattr(module, '_schema_error', lambda *_: None)
    monkeypatch.setattr(module, 'tempfile', SimpleNamespace(TemporaryDirectory=staging))
    monkeypatch.setattr(module, 'datetime', SimpleNamespace(now=lambda: SimpleNamespace(strftime=lambda _: 'owned-fixed')))
    monkeypatch.setattr(module, '_snapshot', snapshot)
    assert module.main([str(source), '--db', str(target), '--yes']) == 3
    assert len(calls) == (1 if stage == 'prepared' else 2)
    assert target.read_bytes() == b'owned target' and source.read_bytes() == b'owned source'
    assert sidecar.read_bytes() == b'owned late sidecar'
