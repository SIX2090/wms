"""Native Windows acceptance against uniquely named synthetic tasks only."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows task registration and execution')
def test_configure_scheduled_operations_preview_apply_and_real_retry(tmp_path):
    task_name = 'WMS-Remediation-20261105-' + uuid.uuid4().hex[:12]
    source = tmp_path / 'synthetic source #1.db'
    connection = sqlite3.connect(source)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE sample(value TEXT)')
    connection.execute("INSERT INTO sample VALUES ('committed WAL')")
    connection.commit()
    connection.execute("INSERT INTO sample VALUES ('uncommitted')")
    worker = tmp_path / 'synthetic worker.py'
    count = tmp_path / 'attempts.txt'
    pid = tmp_path / 'worker-pid.txt'
    worker.write_text('from pathlib import Path\nimport os,sys,time\n'
        'p=Path(%r)\nn=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\n'
        'Path(%r).write_text(str(os.getpid()))\ntime.sleep(15 if n==1 else 0)\n'
        'sys.exit(17 if n<3 else 0)\n' % (str(count), str(pid)), encoding='utf-8')
    launch = tmp_path / 'synthetic launch.cmd'
    launch.write_text('@echo off\r\nsetlocal\r\n'
        'if not "%~1"=="current" exit /b 64\r\n'
        'if not "%~2"=="--serve" exit /b 64\r\n'
        '"' + sys.executable + '" "%~dp0synthetic worker.py"\r\nexit /b %errorlevel%\r\n',
        encoding='utf-8')
    script = tmp_path / 'native-test.ps1'
    script.write_text(r'''
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$root=$env:OPS_TEST_ROOT
$temp=$env:OPS_TEST_TEMP
$name=$env:OPS_TEST_TASK
$python=$env:OPS_TEST_PYTHON
$worker=Join-Path $temp 'synthetic worker.py'
$pidFile=Join-Path $temp 'worker-pid.txt'
$config=Join-Path $root 'tools\configure_scheduled_operations.ps1'
$state=Join-Path $temp 'operations'
$directory=Join-Path $temp 'daily'
$parameters=@{ServiceTaskName=$name;PythonExe=$python;BackupSource=(Join-Path $temp 'synthetic source #1.db');BackupDirectory=$directory;StateDirectory=$state;SourceRoot=$root;BackupTime='23:59';RetentionDays=7}
if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'Unexpected existing task'}
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$action=New-ScheduledTaskAction -Execute $env:ComSpec -Argument ('/d /s /c ""'+(Join-Path $temp 'synthetic launch.cmd')+'" current --serve"') -WorkingDirectory $temp
$trigger=New-ScheduledTaskTrigger -Once -At ((Get-Date).AddDays(1))
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
$registered=$false
try {
 Register-ScheduledTask -TaskName $name -Principal $principal -Action $action -Trigger $trigger -Settings $settings|Out-Null
 $registered=$true
 $original=Export-ScheduledTask -TaskName $name
 $originalPrincipal=(Get-ScheduledTask -TaskName $name).Principal|ConvertTo-Json -Depth 8 -Compress
 $originalTriggers=(Get-ScheduledTask -TaskName $name).Triggers|ConvertTo-Json -Depth 8 -Compress
 $preview=(& $config @parameters)|ConvertFrom-Json
 if($preview.applied -or (Test-Path -LiteralPath $state) -or (Test-Path -LiteralPath $directory)){throw 'Preview wrote files'}
 if((Export-ScheduledTask -TaskName $name) -cne $original){throw 'Preview changed task'}
 $rejected=$false
 try { & $config @parameters -Apply -ExpectedDefinitionHash 'wrong-hash'|Out-Null } catch { $rejected=$true }
 if(-not $rejected -or (Test-Path -LiteralPath $state)){throw 'Changed definition was not refused'}
 Start-ScheduledTask -TaskName $name
 $deadline=(Get-Date).AddSeconds(25)
 while(-not (Test-Path -LiteralPath $pidFile)){if((Get-Date) -gt $deadline){throw 'Worker did not start'};Start-Sleep -Milliseconds 100}
 $firstPid=[int](Get-Content -LiteralPath $pidFile)
 $applied=(& $config @parameters -Apply -ExpectedDefinitionHash $preview.definitionHash)|ConvertFrom-Json
 if(-not $applied.applied -or -not (Get-Process -Id $firstPid -ErrorAction SilentlyContinue)){throw 'Apply stopped the original worker'}
 $task=Get-ScheduledTask -TaskName $name
 if($task.Settings.ExecutionTimeLimit -ne 'PT0S' -or $task.Settings.MultipleInstances -ne 'IgnoreNew'){throw 'Wrong service limits'}
 if(($task.Principal|ConvertTo-Json -Depth 8 -Compress) -cne $originalPrincipal){throw 'Principal changed'}
 if(($task.Triggers|ConvertTo-Json -Depth 8 -Compress) -cne $originalTriggers){throw 'Triggers changed'}
 $deadline=(Get-Date).AddSeconds(25)
 while((Get-ScheduledTask -TaskName $name).State -eq 'Running'){if((Get-Date) -gt $deadline){throw 'Original worker did not exit'};Start-Sleep -Milliseconds 100}
 Start-ScheduledTask -TaskName $name
 $deadline=(Get-Date).AddSeconds(110)
 do {
  $count=[int](Get-Content -LiteralPath (Join-Path $temp 'attempts.txt'))
  if($count -ge 3 -and (Get-ScheduledTask -TaskName $name).State -ne 'Running'){break}
  if((Get-Date) -gt $deadline){throw 'Supervised failure was not retried successfully'}
  Start-Sleep -Milliseconds 300
 } while($true)
 if($count -ne 3 -or (Get-ScheduledTaskInfo -TaskName $name).LastTaskResult -ne 0){throw 'Wrong retry result'}
 $monitor=Get-Content -LiteralPath (Join-Path $state 'monitor\supervisor-status.json') -Encoding UTF8|ConvertFrom-Json
 if($monitor.phase -ne 'stopped' -or $monitor.last_exit_code -ne 0){throw 'Wrong monitor status'}
 Start-ScheduledTask -TaskName ($name+'-DailyBackup')
 $deadline=(Get-Date).AddSeconds(35)
 do {
  if((Test-Path -LiteralPath (Join-Path $directory '.daily-backup-status.json')) -and (Get-ScheduledTask -TaskName ($name+'-DailyBackup')).State -ne 'Running'){break}
  if((Get-Date) -gt $deadline){throw 'Independent scheduled backup did not finish'}
  Start-Sleep -Milliseconds 100
 } while($true)
 if((Get-ScheduledTaskInfo -TaskName ($name+'-DailyBackup')).LastTaskResult -ne 0){throw 'Backup task failed'}
 if(-not (Test-Path -LiteralPath (Join-Path $state 'service-task.before.xml'))){throw 'Missing rollback definition'}
 @{success=$true;productionModified=$false;previewReadOnly=$true;changedDefinitionRefused=$true;runningPidPreserved=$true;attempts=$count;nativeRetryDelaySeconds=60;backupTaskSucceeded=$true}|ConvertTo-Json -Compress
} finally {
 if($registered){
  foreach($taskName in @(($name+'-DailyBackup'),$name)){
   $owned=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
   if($owned -and $owned.Actions[0].Execute -in @($python,$env:ComSpec) -and ($owned.Actions[0].Arguments.Contains($temp))){
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
   }
  }
 }
}
''', encoding='utf-8-sig')
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(script)], env=dict(os.environ,
            OPS_TEST_ROOT=str(ROOT), OPS_TEST_TEMP=str(tmp_path), OPS_TEST_TASK=task_name,
            OPS_TEST_PYTHON=sys.executable), capture_output=True, text=True, encoding='utf-8-sig',
            errors='replace', timeout=200, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert result.returncode == 0, result.stdout + result.stderr
        proof = json.loads(result.stdout.strip())
        assert proof['success'] is True and proof['productionModified'] is False
        status = json.loads((tmp_path / 'daily/.daily-backup-status.json').read_text(encoding='utf-8'))
        assert status['retention_days'] == 7
        files = list((tmp_path / 'daily').glob('auto_daily_*.db'))
        assert len(files) == 1
        with sqlite3.connect(files[0]) as copy:
            assert copy.execute('SELECT value FROM sample').fetchall() == [('committed WAL',)]
        assert connection.execute('SELECT COUNT(*) FROM sample').fetchone() == (2,)
    finally:
        connection.rollback()
        connection.close()
