@echo off
setlocal EnableExtensions
REM chcp 65001 removed: Tencent Cloud console cannot write to CON device.
REM Use PYTHONUTF8=1 instead for UTF-8 support.
set "PYTHONUTF8=1"

set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=(Resolve-Path -LiteralPath '%APP_DIR%').Path; $rootRx=[regex]::Escape($root); $listenIds=@(); try { $listenIds=@(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess) } catch {}; $procs=Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -and ($_.CommandLine -match $rootRx -or $listenIds -contains [int]$_.ProcessId) }; foreach ($p in $procs) { Write-Host ('Stopping WMS PID ' + $p.ProcessId); Stop-Process -Id $p.ProcessId -Force }; exit 0"
exit /b %ERRORLEVEL%
