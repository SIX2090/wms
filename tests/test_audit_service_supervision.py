"""Repair task: AUDIT-FULL-20261016-001-F07B; no real service stop/register."""
import os
import json
from pathlib import Path
import sys
import subprocess
import tempfile
from unittest.mock import MagicMock
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import service_control as control
import service_launcher as launcher
from tests.test_audit_service_identity import process
from tests.test_audit_updater_recovery import u


@pytest.mark.parametrize('kind', ['running', 'stopped', 'root_binding', 'unknown', 'unknown_ancestry'])
def test_assert_unmanaged(tmp_path, kind):
    row = process(tmp_path)
    snapshot = {'listeners': [row['pid']], 'processes': [row], 'service_bindings': []}
    if kind == 'unknown_ancestry':
        row['supervision_unknown'] = True
    elif kind == 'running':
        row['supervisors'] = ['SyntheticWMS']
    else:
        directory = tmp_path.parent if kind == 'root_binding' else tmp_path
        snapshot['service_bindings'] = [{'name': 'SyntheticWMS', 'directories': [str(directory)],
                                         'unknown': kind == 'unknown'}]
    with pytest.raises(RuntimeError, match='服务'):
        control.assert_unmanaged(snapshot, tmp_path)


@pytest.mark.parametrize('kind', ['ordinary', 'other_service', 'prefix', 'empty'])
def test_unrelated_service_does_not_block_ordinary_process(tmp_path, kind):
    directory = str(tmp_path) + '2' if kind == 'prefix' else str(tmp_path / 'foreign')
    row = process(tmp_path if kind == 'ordinary' else tmp_path / 'foreign')
    row['supervisors'] = [] if kind == 'ordinary' else ['OtherService']
    snapshot = {'listeners': [], 'processes': [] if kind == 'empty' else [row],
                'service_bindings': [{'name': 'OtherService', 'directories': [directory], 'unknown': False}]}
    control.assert_unmanaged(snapshot, tmp_path)


def test_registered_alias_directory_cannot_bypass_service_guard(tmp_path):
    assert tmp_path.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())
    actual = tmp_path / 'actual'; actual.mkdir()
    alias = tmp_path / 'alias'
    if os.name == 'nt':
        subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(alias), str(actual)],
                       check=True, capture_output=True, timeout=10)
    else:
        alias.symlink_to(actual, target_is_directory=True)
    assert alias.resolve() == actual.resolve()
    snapshot = {'listeners': [], 'processes': [], 'service_bindings': [
        {'name': 'SyntheticWMS', 'directories': [str(alias)], 'unknown': False}]}
    with pytest.raises(RuntimeError, match='服务'):
        control.assert_unmanaged(snapshot, actual)


@pytest.mark.parametrize('entry', ['stop', 'updater'])
@pytest.mark.parametrize('running', [False, True])
def test_ordinary_maintenance_refuses_registered_service_even_with_empty_port(tmp_path, monkeypatch, entry, running):
    row = process(tmp_path)
    snapshot = {'listeners': [30] if running else [], 'processes': [row] if running else [],
                'service_bindings': [{'name': 'SyntheticWMS', 'directories': [str(tmp_path)], 'unknown': False}]}
    monkeypatch.setattr(control, 'process_snapshot', lambda port: snapshot)
    stop = MagicMock()
    monkeypatch.setattr(control, 'stop_process', stop)
    with pytest.raises(RuntimeError, match='服务托管'):
        if entry == 'stop': control.stop_verified_server(tmp_path, 8080)
        else: u.Services(tmp_path, 8080).current_pid()
    stop.assert_not_called()


def test_process_query_timeout_is_short_and_readable(monkeypatch):
    monkeypatch.setattr(control, 'os', SimpleNamespace(name='nt', environ=os.environ))
    run = MagicMock(side_effect=subprocess.TimeoutExpired(['synthetic-command-do-not-emit'], 20))
    monkeypatch.setattr(control.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='超时') as failure:
        control._powershell('synthetic-source-do-not-emit', {})
    assert 'synthetic-command' not in str(failure.value)
    assert 'synthetic-source' not in str(failure.value)
    assert run.call_args.kwargs['timeout'] == 20


@pytest.mark.parametrize('supervisor,expected', [('SyntheticWMS', True), ('OtherService', False), ('', False)])
def test_service_health_requires_requested_supervisor(tmp_path, monkeypatch, supervisor, expected):
    row = process(tmp_path)
    row['supervisors'] = [supervisor] if supervisor else []
    monkeypatch.setattr(launcher, 'APP_DIR', tmp_path)
    monkeypatch.setattr(control, 'process_snapshot', lambda port: {'listeners': [30], 'processes': [row]})
    monkeypatch.setattr(launcher.time, 'sleep', lambda seconds: None)
    response = MagicMock(); response.__enter__.return_value.status = 200
    http = MagicMock(return_value=response)
    monkeypatch.setattr(launcher.urllib.request, 'urlopen', http)
    if expected:
        assert launcher.check_service_health({'WMS_PORT': '8080'}, 'SyntheticWMS') == 0
    else:
        with pytest.raises(ValueError): launcher.check_service_health({'WMS_PORT': '8080'}, 'SyntheticWMS')
        http.assert_not_called()


def test_cloud_health_passes_explicit_service_name():
    source = (ROOT / 'deploy_cloud.bat').read_text(encoding='utf-8')
    assert 'set "WMS_HEALTH_SERVICE_NAME=%SERVICE_NAME%"' in source
    assert source.index('set "WMS_HEALTH_SERVICE_NAME=%SERVICE_NAME%"') < source.index('service_launcher.py" --health')


def test_main_transfers_explicit_service_name_to_health(monkeypatch):
    monkeypatch.setenv('WMS_HEALTH_SERVICE_NAME', 'SyntheticWMS')
    monkeypatch.setattr(launcher, 'build_service_env', lambda env: {})
    monkeypatch.setattr(launcher.subprocess, 'run', MagicMock(return_value=MagicMock(returncode=0)))
    health = MagicMock(return_value=0)
    monkeypatch.setattr(launcher, 'check_service_health', health)
    assert launcher.main(['--health']) == 0
    health.assert_called_once_with({}, 'SyntheticWMS')


@pytest.mark.skipif(os.name != 'nt', reason='Native PowerShell adapter, all cmdlets and kill are fake')
@pytest.mark.parametrize('kind', ['managed', 'reused_parent', 'ordinary', 'missing_birth'])
def test_stop_rechecks_supervisor_before_fake_kill(tmp_path, monkeypatch, kind):
    original = control._powershell
    captured = []
    monkeypatch.setattr(control, '_powershell', lambda source, values: captured.append((source, values)))
    row = process(tmp_path); row['ticks'] = '630822816000000000'
    control.stop_process(row)
    source, values = captured[0]
    marker = tmp_path / 'synthetic-kill.txt'
    values.update(SYNTHETIC_KIND=kind, SYNTHETIC_KILL=str(marker))
    fake = r'''
$global:expected=$env:WMS_CONTROL_EXPECTED | ConvertFrom-Json
function Get-Process {
 param($Id,$ErrorAction)
 $p=[pscustomobject]@{Handle=0;StartTime=[DateTime]::Parse('2000-01-01T00:00:00Z').ToUniversalTime()}
 $p | Add-Member ScriptMethod Kill { [IO.File]::WriteAllText($env:SYNTHETIC_KILL,'fake-only') }
 $p | Add-Member ScriptMethod WaitForExit { param($ms) return $true }
 return $p
}
function Get-CimInstance {
 param($ClassName,$Filter)
 if ($ClassName -eq 'Win32_Service') {
  if ($env:SYNTHETIC_KIND -ne 'ordinary') { [pscustomobject]@{Name='SyntheticWMS';ProcessId=50} }
  return
 }
 if ($Filter -eq 'ProcessId=50') {
  $birth=[DateTime]::Parse('1999-01-01T00:00:00Z').ToUniversalTime()
  if ($env:SYNTHETIC_KIND -eq 'reused_parent') { $birth=$birth.AddYears(3) }
  if ($env:SYNTHETIC_KIND -eq 'missing_birth') { $birth=$null }
  return [pscustomobject]@{ProcessId=50;ParentProcessId=0;CreationDate=$birth}
 }
 return [pscustomobject]@{ProcessId=30;ParentProcessId=50;ExecutablePath=$global:expected.executable;CommandLine=$global:expected.command}
}
'''
    if kind in {'managed', 'missing_birth'}:
        with pytest.raises(RuntimeError): original(fake + source, values)
        assert not marker.exists()
    else:
        assert original(fake + source, values) is True
        assert marker.read_text() == 'fake-only'


@pytest.mark.skipif(os.name != 'nt', reason='Native PowerShell, registry and service metadata are fake')
@pytest.mark.parametrize('kind', ['directory', 'quoted_script', 'unquoted_script', 'batch_application',
                                  'relative', 'missing', 'environment', 'denied'])
def test_registered_service_binding_reads_only_allowed_metadata(tmp_path, kind):
    fake = r'''
function Test-Path { param($LiteralPath,$ErrorAction) return ($env:SYNTHETIC_KIND -ne 'missing') }
function Get-ItemProperty {
 param($LiteralPath,$Name,$ErrorAction)
 if (($Name -join ',') -ne 'Application,AppDirectory,AppParameters') { throw 'Unexpected property access' }
 if ($env:SYNTHETIC_KIND -eq 'denied') { throw 'Synthetic registry denied' }
 $directory=$null; $application='C:\Python\python.exe'; $parameters=''
 switch ($env:SYNTHETIC_KIND) {
  'directory' { $directory='C:\Synthetic WMS\app' }
  'quoted_script' { $parameters='"C:\Synthetic WMS\app\run_server.py" --unused synthetic-do-not-emit' }
  'unquoted_script' { $parameters='C:\SyntheticWMS\app\run_server.py --unused synthetic-do-not-emit' }
  'batch_application' { $application='C:\Synthetic WMS\app\start_wms_auto.bat' }
  'relative' { $directory='relative\app'; $parameters='run_server.py' }
  'environment' { $directory='%UNKNOWN_SERVICE_HOME%\app' }
 }
 [pscustomobject]@{Application=$application;AppDirectory=$directory;AppParameters=$parameters}
}
'''
    script = control._SUPERVISION_PS + r'''
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$services=@([pscustomobject]@{Name='SyntheticWMS';PathName='"C:\Synthetic\nssm.exe"';ProcessId=0})
@(Get-WmsServiceBindings -ServiceRows $services) | ConvertTo-Json -Depth 4 -Compress
'''
    if kind == 'denied':
        with pytest.raises(RuntimeError): control._powershell(fake + script, {'SYNTHETIC_KIND': kind})
        return
    result = control._powershell(fake + script, {'SYNTHETIC_KIND': kind})
    row = result[0] if isinstance(result, list) else result
    assert row['name'] == 'SyntheticWMS'
    assert 'synthetic-do-not-emit' not in json.dumps(row)
    assert row['unknown'] == (kind in {'relative', 'missing', 'environment'})
    if not row['unknown']:
        expected = r'C:\SyntheticWMS\app' if kind == 'unquoted_script' else r'C:\Synthetic WMS\app'
        assert row['directories'] == [expected]
