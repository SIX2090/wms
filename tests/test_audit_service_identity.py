"""Repair task: AUDIT-FULL-20261016-001-F03；所有停止/启动均使用模拟对象。"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import restart
import service_control as control


def process(app_dir, pid=30, script=None):
    exe = r'C:\Python\python.exe'
    script = str(Path(app_dir).resolve() / 'run_server.py') if script is None else script
    return {'pid': pid, 'executable': exe, 'command': f'"{exe}" "{script}"', 'ticks': '1234'}


@pytest.mark.parametrize('kind', ['absolute', 'spaces', 'pythonw', 'forward_slash'])
def test_is_target_process(tmp_path, kind):
    directory = tmp_path / ('WMS Space' if kind == 'spaces' else 'wms')
    p = process(directory)
    if kind == 'pythonw':
        p['executable'] = p['executable'].replace('python.exe', 'pythonw.exe')
        p['command'] = p['command'].replace('python.exe', 'pythonw.exe')
    if kind == 'forward_slash':
        p['command'] = p['command'].replace('\\', '/')
    assert control.is_target_process(p, directory)


@pytest.mark.parametrize('kind', ['relative', 'other_root', 'other_script', 'prefix', 'python_code',
                                  'python_option', 'nonpython', 'missing_command', 'missing_exe'])
def test_ambiguous_or_unrelated_process_is_never_a_target(tmp_path, kind):
    p = process(tmp_path)
    if kind == 'relative':
        p = process(tmp_path, script='run_server.py')
    elif kind == 'other_root':
        p = process(tmp_path / 'another')
    elif kind == 'other_script':
        p = process(tmp_path, script=str(tmp_path / 'audit.py'))
    elif kind == 'prefix':
        p = process(tmp_path, script=str(tmp_path / 'run_server.py.bak'))
    elif kind == 'python_code':
        p['command'] = f'"{p["executable"]}" -c "{tmp_path / "run_server.py"}"'
    elif kind == 'python_option':
        p['command'] = p['command'].replace('" "', '" -c "', 1)
    elif kind == 'nonpython':
        p['executable'] = r'C:\another.exe'
    else:
        p['command' if kind == 'missing_command' else 'executable'] = None
    assert not control.is_target_process(p, tmp_path)


@pytest.mark.parametrize('kind', ['foreign_python', 'legacy_relative', 'no_metadata', 'mixed_owners',
                                  'other_port'])
def test_stop_refuses_unknown_identity_without_terminating(tmp_path, monkeypatch, kind):
    p = process(tmp_path)
    owners = [30]
    if kind == 'foreign_python':
        p = process(tmp_path, script=str(tmp_path / 'different.py'))
    if kind == 'legacy_relative':
        p = process(tmp_path, script='run_server.py')
    if kind == 'other_port':
        owners = []
    if kind == 'mixed_owners':
        owners = [30, 40]
    snapshot = {'listeners': owners, 'processes': [] if kind == 'no_metadata' else [p]}
    monkeypatch.setattr(control, 'process_snapshot', lambda port: snapshot)
    stop = MagicMock()
    monkeypatch.setattr(control, 'stop_process', stop)
    with pytest.raises(RuntimeError):
        control.stop_verified_server(tmp_path, 8080)
    stop.assert_not_called()


def test_stop_verified_server(tmp_path, monkeypatch):
    p = process(tmp_path)
    unrelated = process(tmp_path / 'another', pid=40)
    snapshots = iter([{'listeners': [30], 'processes': [p, unrelated]},
                      {'listeners': [], 'processes': [unrelated]}])
    monkeypatch.setattr(control, 'process_snapshot', lambda port: next(snapshots))
    stop = MagicMock()
    monkeypatch.setattr(control, 'stop_process', stop)
    control.stop_verified_server(tmp_path, 8080)
    stop.assert_called_once_with(p)


def test_empty_port_does_not_stop_unrelated_python(tmp_path, monkeypatch):
    monkeypatch.setattr(control, 'process_snapshot', lambda port: {
        'listeners': [], 'processes': [process(tmp_path / 'another')]})
    stop = MagicMock()
    monkeypatch.setattr(control, 'stop_process', stop)
    control.stop_verified_server(tmp_path, 8080)
    stop.assert_not_called()


def test_stale_pid_check_failure_aborts_restart(tmp_path, monkeypatch):
    p = process(tmp_path)
    monkeypatch.setattr(control, 'process_snapshot', lambda port: {'listeners': [30], 'processes': [p]})
    monkeypatch.setattr(control, 'stop_process', MagicMock(side_effect=RuntimeError('identity changed')))
    with pytest.raises(RuntimeError, match='identity changed'):
        control.stop_verified_server(tmp_path, 8080)


def test_owns_port(tmp_path, monkeypatch):
    monkeypatch.setattr(control, 'process_snapshot', lambda port: {
        'listeners': [40], 'processes': [process(tmp_path, 30), process(tmp_path / 'another', 40)]})
    assert not control.owns_port(30, tmp_path, 8080)
    assert not control.owns_port(40, tmp_path, 8080)
    monkeypatch.setattr(control, 'process_snapshot', lambda port: {
        'listeners': [30], 'processes': [process(tmp_path, 30)]})
    assert control.owns_port(30, tmp_path, 8080)


def setup_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(restart, 'APP_DIR', tmp_path)
    monkeypatch.setattr(restart, 'LOG_DIR', tmp_path / 'logs')
    monkeypatch.setattr(restart.os, 'chdir', lambda path: None)
    monkeypatch.setattr(restart.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(restart, 'stop_verified_server', MagicMock(), raising=False)
    monkeypatch.setenv('WMS_PORT', '18080')
    child = MagicMock(pid=77)
    child.poll.return_value = None
    spawn = MagicMock(return_value=child)
    monkeypatch.setattr(restart.subprocess, 'Popen', spawn)
    response = MagicMock()
    response.__enter__.return_value.status = 200
    request = MagicMock(return_value=response)
    monkeypatch.setattr(restart.urllib.request, 'urlopen', request)
    return child, spawn, request


def test_stop_error_prevents_new_child(tmp_path, monkeypatch):
    child, spawn, request = setup_restart(tmp_path, monkeypatch)
    monkeypatch.setattr(restart, 'stop_verified_server', MagicMock(side_effect=RuntimeError('foreign port')), raising=False)
    assert restart.main() == 1
    spawn.assert_not_called()
    request.assert_not_called()


def test_exited_child_cannot_pass_with_old_http200(tmp_path, monkeypatch):
    child, spawn, request = setup_restart(tmp_path, monkeypatch)
    child.poll.return_value = 1
    monkeypatch.setattr(restart, 'owns_port', lambda *args: False, raising=False)
    assert restart.main() == 1
    request.assert_not_called()


def test_foreign_listener_cannot_pass_http200(tmp_path, monkeypatch):
    child, spawn, request = setup_restart(tmp_path, monkeypatch)
    monkeypatch.setattr(restart, 'owns_port', lambda *args: False, raising=False)
    assert restart.main() == 1
    request.assert_not_called()
    child.terminate.assert_called_once()


def test_new_live_child_owns_port_and_http200_passes(tmp_path, monkeypatch):
    child, spawn, request = setup_restart(tmp_path, monkeypatch)
    ownership = MagicMock(return_value=True)
    monkeypatch.setattr(restart, 'owns_port', ownership, raising=False)
    assert restart.main() == 0
    assert ownership.call_count == 2
    assert spawn.call_args.args[0][1] == str(tmp_path / 'run_server.py')
    assert spawn.call_args.kwargs['env']['WMS_PORT'] == '18080'
    request.assert_called_once_with('http://127.0.0.1:18080/login', timeout=3)
    child.terminate.assert_not_called()


def test_port_hijack_after_http_is_not_success(tmp_path, monkeypatch):
    child, spawn, request = setup_restart(tmp_path, monkeypatch)
    monkeypatch.setattr(restart, 'owns_port', MagicMock(side_effect=[True] + [False] * 16), raising=False)
    assert restart.main() == 1
    child.terminate.assert_called_once()


@pytest.mark.parametrize('name', ['install.bat', 'install_e_wms.bat'])
def test_installers_delegate_identity_and_fail_before_copy(name):
    source = (ROOT / name).read_text(encoding='utf-8')
    section = source[source.index('[2/8]'):source.index('[3/8]')]
    assert 'service_control.py" stop --app-dir "%RUN_DIR%"' in section
    assert 'if errorlevel 1 (' in section and 'exit /b 1' in section
    assert 'Stop-Process' not in section and 'stop_wms.bat' not in section


def test_stop_entry_uses_shared_verifier_and_absolute_start():
    stop = (ROOT / 'app/stop_wms_offline.bat').read_text(encoding='utf-8')
    assert 'service_control.py" stop %*' in stop
    assert 'Stop-Process' not in stop and 'Get-NetTCPConnection' not in stop
    start = (ROOT / 'app/start_wms_offline.bat').read_text(encoding='utf-8')
    assert '"%PYTHON_CMD%" "%~dp0run_server.py"' in start


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell process adapter')
@pytest.mark.parametrize('changed', ['none', 'command', 'executable', 'ticks'])
def test_stop_process(tmp_path, monkeypatch, changed):
    # The PowerShell functions shadow system cmdlets. Fake .Kill writes a temp
    # marker only; no real process lookup, handle or stop operation is possible.
    original = control._powershell
    captured = []
    monkeypatch.setattr(control, '_powershell', lambda source, values: captured.append((source, values)))
    p = process(tmp_path)
    p['ticks'] = '630822816000000000'  # UTC 2000-01-01
    control.stop_process(p)
    source, values = captured[0]
    fake = r'''
$global:fakeExpected=$env:WMS_CONTROL_EXPECTED | ConvertFrom-Json
function Get-Process {
    param($Id, $ErrorAction)
    $x=[pscustomobject]@{Handle=0; StartTime=[DateTime]::Parse('2000-01-01T00:00:00Z').ToUniversalTime()}
    if ($env:WMS_CONTROL_TEST_CHANGE -eq 'ticks') { $x.StartTime=$x.StartTime.AddSeconds(1) }
    $x | Add-Member -MemberType ScriptMethod -Name Kill -Value { [IO.File]::WriteAllText($env:WMS_CONTROL_TEST_MARKER,'fake-only') }
    $x | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { param($ms) return $true }
    return $x
}
function Get-CimInstance {
    param($ClassName, $Filter)
    $x=[pscustomobject]@{ExecutablePath=$global:fakeExpected.executable; CommandLine=$global:fakeExpected.command}
    if ($env:WMS_CONTROL_TEST_CHANGE -eq 'command') { $x.CommandLine='changed' }
    if ($env:WMS_CONTROL_TEST_CHANGE -eq 'executable') { $x.ExecutablePath='changed' }
    return $x
}
'''
    marker = tmp_path / 'fake-kill.txt'
    values.update(WMS_CONTROL_TEST_CHANGE=changed, WMS_CONTROL_TEST_MARKER=str(marker))
    if changed == 'none':
        assert original(fake + source, values) is True
        assert marker.read_text() == 'fake-only'
    else:
        with pytest.raises(RuntimeError):
            original(fake + source, values)
        assert not marker.exists()


def test_process_adapter_uses_no_window_and_checks_errors(monkeypatch):
    monkeypatch.setattr(control, 'os', SimpleNamespace(name='nt', environ=os.environ))
    run = MagicMock(return_value=SimpleNamespace(returncode=1, stdout=''))
    monkeypatch.setattr(control.subprocess, 'run', run)
    with pytest.raises(RuntimeError):
        control._powershell('never executed by this test', {})
    assert run.call_args.kwargs['timeout'] == 20
    run.return_value = SimpleNamespace(returncode=0, stdout='not-json')
    with pytest.raises(RuntimeError):
        control._powershell('never executed by this test', {})


def test_stop_timeout_does_not_expand_target_set(tmp_path, monkeypatch):
    p = process(tmp_path)
    monkeypatch.setattr(control, 'process_snapshot', lambda port: {'listeners': [30], 'processes': [p]})
    monkeypatch.setattr(control.time, 'sleep', lambda seconds: None)
    stop = MagicMock()
    monkeypatch.setattr(control, 'stop_process', stop)
    with pytest.raises(RuntimeError, match='端口仍被占用'):
        control.stop_verified_server(tmp_path, 8080)
    stop.assert_called_once_with(p)


@pytest.mark.parametrize('port,expected', [('18080', 0), ('0', 1)])
def test_control_cli_validates_port_and_exit_status(tmp_path, monkeypatch, port, expected):
    stop = MagicMock()
    monkeypatch.setattr(control, 'stop_verified_server', stop)
    assert control.main(['stop', '--app-dir', str(tmp_path), '--port', port]) == expected
    assert stop.call_count == (1 if expected == 0 else 0)


@pytest.mark.skipif(os.name != 'nt', reason='Windows read-only process inventory')
def test_process_snapshot():
    snapshot = control.process_snapshot(8080)
    assert isinstance(snapshot['listeners'], list)
    assert isinstance(snapshot['processes'], list)
    assert all(isinstance(pid, int) for pid in snapshot['listeners'])
    assert all({'pid', 'executable', 'command', 'ticks'} <= set(p) for p in snapshot['processes'])
