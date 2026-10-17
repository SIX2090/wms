"""Windows WMS启停的严格进程身份检查；不导入应用或访问数据库。"""
from __future__ import annotations

import argparse
import json
import ntpath
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Repair task: AUDIT-FULL-20261016-001-F03
# Repair task: AUDIT-FULL-20261016-001-F07B
_SUPERVISION_PS = r'''
# Repair task: AUDIT-FULL-20261016-001-F07B. Read metadata only, never service environment.
function Get-WmsSupervisors {
    param($ProcessRow, $StartTicks, $ServiceRows, $ProcessMap)
    if ($null -eq $ServiceRows) { $ServiceRows=@(Get-CimInstance Win32_Service) }
    $active=@($ServiceRows | Where-Object { $_.ProcessId -gt 0 })
    if (!$active.Count) { return }
    $row=$ProcessRow
    $birth=$StartTicks
    $seen=@{}
    for ($depth=0; $depth -lt 64; $depth++) {
        $processId=[int]$row.ProcessId
        if ($seen.ContainsKey($processId)) { throw 'Cannot verify service ancestry cycle' }
        $seen[$processId]=$true
        $matched=@($active | Where-Object { [int]$_.ProcessId -eq $processId })
        if ($matched.Count) { $matched | ForEach-Object { $_.Name }; return }
        $parentId=[int]$row.ParentProcessId
        if (!$parentId) { return }
        if ($null -ne $ProcessMap) { $parent=$ProcessMap[$parentId] }
        else { $parent=Get-CimInstance Win32_Process -Filter ('ProcessId='+$parentId) }
        if (!$parent) { return }
        if (!$birth -or !$parent.CreationDate) { throw 'Cannot verify parent creation time' }
        $parentBirth=$parent.CreationDate.ToUniversalTime().Ticks
        # A later parent PID belongs to a different process, not the original supervisor.
        if ($parentBirth -gt [long]$birth) { return }
        $row=$parent
        $birth=$parentBirth
    }
    throw 'Cannot verify service ancestry depth'
}

function Get-WmsServiceBindings {
    param($ServiceRows)
    foreach ($service in $ServiceRows) {
        if (!$service.Name) { continue }
        $key='Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\'+$service.Name+'\Parameters'
        $nssm=[bool]($service.PathName -match '(?i)(^|[\\/])nssm(?:\.exe)?(?:["\s]|$)')
        if (!(Test-Path -LiteralPath $key -ErrorAction Stop)) {
            if ($nssm) { @{name=$service.Name; directories=@(); unknown=$true} }
            continue
        }
        # Explicit allowlist: never retrieve AppEnvironmentExtra (may contain secrets).
        $settings=Get-ItemProperty -LiteralPath $key -Name Application,AppDirectory,AppParameters -ErrorAction SilentlyContinue
        if (!$settings -or !$settings.Application) {
            if ($nssm) { @{name=$service.Name; directories=@(); unknown=$true} }
            continue
        }
        $directories=@()
        if ($settings.AppDirectory) { $directories += [string]$settings.AppDirectory }
        $application=([string]$settings.Application).Trim('"')
        if ([IO.Path]::IsPathRooted($application) -and [IO.Path]::GetFileName($application) -match '^(?i:run_server\.py|start_wms_(auto|offline)\.bat)$') {
            $directories += Split-Path -Parent $application
        }
        $values=@([string]$settings.Application,[string]$settings.AppParameters)
        foreach ($value in $values) {
            foreach ($match in [regex]::Matches($value,'(?i)(?:"(?<path>[A-Z]:[\\/][^"]*[\\/](?:run_server\.py|start_wms_(?:auto|offline)\.bat))"|(?<path>[A-Z]:[\\/][^\s"]*[\\/](?:run_server\.py|start_wms_(?:auto|offline)\.bat)))(?=\s|$)')) {
                $directories += Split-Path -Parent $match.Groups['path'].Value
            }
        }
        $unknown=(!$directories.Count -or [bool](@($directories | Where-Object { $_ -match '%' -or ![IO.Path]::IsPathRooted($_) }).Count))
        @{name=$service.Name; directories=@($directories | Select-Object -Unique); unknown=$unknown}
    }
}

'''


def is_target_process(process, app_dir):
    """只接受完整解释器+完整脚本路径；相对脚本的旧实例需人工确认停止。"""
    executable = str(process.get('executable') or '').replace('/', '\\')
    if executable.rsplit('\\', 1)[-1].lower() not in {'python.exe', 'pythonw.exe'}:
        return False
    script = str(Path(app_dir).resolve() / 'run_server.py').replace('/', '\\')

    def _token(value):
        quoted = '"' + re.escape(value) + '"'
        return '(?:' + quoted + ('' if re.search(r'\s', value) else '|' + re.escape(value)) + ')'

    pattern = r'^\s*' + _token(executable) + r'\s+' + _token(script) + r'(?:\s|$)'
    command = str(process.get('command') or '').replace('/', '\\')
    return bool(re.match(pattern, command, re.IGNORECASE))


def _powershell(source, values):
    if os.name != 'nt':
        raise RuntimeError('自动启停仅支持Windows；请人工管理当前平台的WMS服务')
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', source],
            env=dict(os.environ, **values), capture_output=True, text=True,
            encoding='utf-8-sig', errors='replace', timeout=20,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('系统进程/服务查询超时，已拒绝继续；请检查系统负载后重试，不会强行停止进程。') from exc
    if result.returncode:
        raise RuntimeError('无法核对或停止WMS进程，请检查权限并人工确认；未按端口强制结束进程')
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError('进程查询未返回有效身份数据，已拒绝继续') from exc


def process_snapshot(port):
    """从系统取监听PID、解释器、完整命令和启动时间；任一步失败即拒绝。"""
    return _powershell(_SUPERVISION_PS + r'''
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$services=@(Get-CimInstance Win32_Service)
$allProcesses=@(Get-CimInstance Win32_Process)
$processMap=@{}
foreach ($row in $allProcesses) { $processMap[[int]$row.ProcessId]=$row }
$listeners=@(Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq ([int]$env:WMS_CONTROL_PORT) | Select-Object -ExpandProperty OwningProcess -Unique)
$processes=@($allProcesses | Where-Object { $_.Name -in @('python.exe','pythonw.exe') } | ForEach-Object {
    $ticks=$null
    try { $p=Get-Process -Id $_.ProcessId -ErrorAction Stop; $ticks=$p.StartTime.ToUniversalTime().Ticks.ToString() } catch {}
    $supervisors=@(); $unknown=$false
    try { $supervisors=@(Get-WmsSupervisors -ProcessRow $_ -StartTicks $ticks -ServiceRows $services -ProcessMap $processMap) } catch { $unknown=$true }
    @{pid=[int]$_.ProcessId; executable=$_.ExecutablePath; command=$_.CommandLine; ticks=$ticks; supervisors=$supervisors; supervision_unknown=$unknown}
})
@{listeners=$listeners; processes=$processes; service_bindings=@(Get-WmsServiceBindings -ServiceRows $services)} | ConvertTo-Json -Depth 5 -Compress
''', {'WMS_CONTROL_PORT': str(port)})


def stop_process(process):
    """重新核对命令/解释器/启动时间，并持有进程句柄，避免PID复用误杀。"""
    _powershell(_SUPERVISION_PS + r'''
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$expected=$env:WMS_CONTROL_EXPECTED | ConvertFrom-Json
$p=Get-Process -Id ([int]$expected.pid) -ErrorAction Stop
$handle=$p.Handle
$live=Get-CimInstance Win32_Process -Filter ('ProcessId='+$expected.pid)
if (!$live -or $live.ExecutablePath -cne $expected.executable -or $live.CommandLine -cne $expected.command -or $p.StartTime.ToUniversalTime().Ticks.ToString() -ne $expected.ticks) { throw 'Process identity changed' }
if (@(Get-WmsSupervisors -ProcessRow $live -StartTicks $expected.ticks).Count) { throw 'Service-managed process; use service maintenance' }
$p.Kill()
if (!$p.WaitForExit(10000)) { throw 'Process did not stop' }
'true'
''', {'WMS_CONTROL_EXPECTED': json.dumps(process, ensure_ascii=True)})


def stop_verified_server(app_dir, port):
    snapshot = process_snapshot(port)
    assert_unmanaged(snapshot, app_dir)
    owners = set(snapshot['listeners'])
    targets = [p for p in snapshot['processes'] if is_target_process(p, app_dir)]
    if not owners:
        if targets:
            raise RuntimeError('本目录存在未监听指定端口的实例，请人工确认；未自动停止')
        return
    matched = [p for p in targets if p['pid'] in owners]
    if len(matched) != 1 or owners != {matched[0]['pid']}:
        raise RuntimeError('端口进程不是可确认的本目录WMS；旧版相对路径实例须人工停止，其他程序不会被结束')
    stop_process(matched[0])
    for _ in range(10):
        if not process_snapshot(port)['listeners']:
            return
        time.sleep(0.2)
    raise RuntimeError('端口仍被占用，已拒绝启动新实例')


def assert_unmanaged(snapshot, app_dir):
    """Repair task: AUDIT-FULL-20261016-001-F07B; include stopped service bindings."""
    directories = {ntpath.normcase(ntpath.normpath(str(Path(app_dir).resolve()))),
                   ntpath.normcase(ntpath.normpath(str(Path(app_dir).resolve().parent)))}
    managed = any(is_target_process(row, app_dir) and (row.get('supervisors') or row.get('supervision_unknown'))
                  for row in snapshot['processes'])
    for binding in snapshot.get('service_bindings', []):
        if binding.get('unknown') or any(ntpath.normcase(ntpath.normpath(str(Path(value).resolve()))) in directories
                                         for value in binding.get('directories', [])):
            managed = True
    if managed:
        raise RuntimeError('本目录由Windows服务托管或服务归属无法确认，普通启停/更新已拒绝；请使用服务维护流程，不能只结束Python子进程。')


def owns_port(pid, app_dir, port):
    snapshot = process_snapshot(port)
    return set(snapshot['listeners']) == {pid} and any(
        p['pid'] == pid and is_target_process(p, app_dir) for p in snapshot['processes'])


def main(argv=None):
    parser = argparse.ArgumentParser(description='仅停止身份明确的本目录WMS实例')
    parser.add_argument('action', choices=['stop'])
    parser.add_argument('--app-dir', default=str(Path(__file__).resolve().parent))
    parser.add_argument('--port', type=int, default=os.environ.get('WMS_PORT') or '8080')
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError('端口必须在1至65535之间')
        stop_verified_server(args.app_dir, args.port)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(f'停止失败：{exc}\n')
        return 1
    sys.stdout.write('指定WMS已停止，或指定端口无运行实例。\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
