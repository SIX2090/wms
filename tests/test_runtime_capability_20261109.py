"""OS-bound runtime capabilities; no external server, real account or database."""
import os
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

GUARD = Path(__file__).resolve().parents[1] / 'scripts/verify_db_guard.py'


def test_require_isolated_test_runtime():
    result = runpy.run_path(str(GUARD))['require_isolated_test_runtime']()
    assert result.name == 'AC' and result.parent.name.startswith('wms.synthetic.')


@pytest.mark.parametrize('raw', ['', '0', '-1', '1', 'invalid', '0x10', str(2**63)])
def test_forged_handle_is_not_a_capability(monkeypatch, raw):
    monkeypatch.setenv('WMS_TEST_RUNTIME_HANDLE', raw)
    with pytest.raises(SystemExit):
        runpy.run_path(str(GUARD))['require_isolated_test_runtime']()


@pytest.mark.parametrize('key', ['DATABASE_URL', 'WMS_DATABASE_URI', 'FLASK_ENV'])
def test_inherited_non_test_target_refused_before_app(monkeypatch, key):
    monkeypatch.setenv(key, 'synthetic-invalid-target')
    with pytest.raises(SystemExit):
        runpy.run_path(str(GUARD))['require_isolated_test_runtime']()


def test_copied_file_in_writable_area_is_not_proof(tmp_path, monkeypatch):
    import msvcrt
    guard = runpy.run_path(str(GUARD))
    profile = guard['require_owned_test_profile']()
    directory = tmp_path / 'wms-supervisor-state-forged'
    directory.mkdir()
    fake = directory / (profile.parent.name + '.runtime.json')
    fake.write_text('{}', encoding='utf-8')
    descriptor = os.open(fake, os.O_RDONLY)
    try:
        monkeypatch.setenv('WMS_TEST_RUNTIME_HANDLE', str(msvcrt.get_osfhandle(descriptor)))
        with pytest.raises(SystemExit):
            guard['require_isolated_test_runtime']()
    finally:
        os.close(descriptor)


def test_child_cannot_replay_parent_process_capability():
    handle = int(os.environ['WMS_TEST_RUNTIME_HANDLE'])
    startup = subprocess.STARTUPINFO()
    startup.lpAttributeList = {'handle_list': [handle]}
    code = 'import runpy;runpy.run_path(' + repr(str(GUARD)) + ")[\"require_isolated_test_runtime\"]()"
    process = subprocess.run(
        [sys.executable, '-I', '-S', '-B', '-c', code], startupinfo=startup,
        capture_output=True, timeout=15,
        env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
    assert process.returncode != 0 and b'Traceback' not in process.stderr, process.stdout + process.stderr
