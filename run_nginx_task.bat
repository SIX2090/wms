@echo off
REM Auto-heal task 2026-10-19: start nginx if not already running.
REM Called by scheduled task "WMS-Nginx-Heal" (SYSTEM, boot + every 5 min).
REM Mirrors run_wms_task.bat: idempotent - exits immediately if nginx is up.
setlocal EnableExtensions
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"

set "NGINX_DIR=C:\nginx"
set "NGINX_EXE=%NGINX_DIR%\nginx.exe"

if not exist "%NGINX_EXE%" (
    echo [ERROR] nginx.exe not found: %NGINX_EXE%
    exit /b 1
)

REM Already running? Do nothing (idempotent heal).
tasklist /FI "IMAGENAME eq nginx.exe" 2>nul | find /I "nginx.exe" >nul
if not errorlevel 1 exit /b 0

REM Config precheck: never start a broken config silently.
pushd "%NGINX_DIR%"
"%NGINX_EXE%" -t >nul 2>&1
if errorlevel 1 (
    echo [ERROR] nginx config test failed; not starting.
    popd
    exit /b 1
)
start "" /B "%NGINX_EXE%"
popd
exit /b 0
