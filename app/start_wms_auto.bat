@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0" || exit /b 1
for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "WMS_NO_DB_TOUCH=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

set "PYTHON_CMD="
if exist "%APP_ROOT%\python\python.exe" set "PYTHON_CMD=%APP_ROOT%\python\python.exe"
if not defined PYTHON_CMD if exist "%~dp0python\python.exe" set "PYTHON_CMD=%~dp0python\python.exe"
if not defined PYTHON_CMD if exist "%APP_ROOT%\runtime\Python311\python.exe" set "PYTHON_CMD=%APP_ROOT%\runtime\Python311\python.exe"
if not defined PYTHON_CMD if exist "%APP_ROOT%\python\Scripts\python.exe" set "PYTHON_CMD=%APP_ROOT%\python\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0python\Scripts\python.exe" set "PYTHON_CMD=%~dp0python\Scripts\python.exe"
if not defined PYTHON_CMD (
    where python.exe >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%p in ('where python.exe') do (
            set "PYTHON_CMD=%%p"
            goto :pyfound
        )
    )
)
:pyfound
if not defined PYTHON_CMD (
    echo [%date% %time%] [ERROR] Python not found; failed to start WMS
    exit /b 1
)

REM Repair task: AUDIT-FULL-20261016-001-F07A. Keep direct run_server launch after preflight.
set "WMS_START_MODE="
set "WMS_START_SECURE="
set "WMS_START_INSECURE="
set "WMS_START_PORT="
for /f "tokens=1-4 delims=|" %%A in ('""%PYTHON_CMD%" "%~dp0service_launcher.py" --batch-config"') do (
    set "WMS_START_MODE=%%A"
    set "WMS_START_SECURE=%%B"
    set "WMS_START_INSECURE=%%C"
    set "WMS_START_PORT=%%D"
)
if not defined WMS_START_PORT goto :config_failed
if /I not "%WMS_START_MODE%"=="https" if /I not "%WMS_START_MODE%"=="trusted-http" goto :config_failed
if not "%WMS_START_SECURE%"=="true" if not "%WMS_START_SECURE%"=="false" if not "%WMS_START_SECURE%"=="unset" goto :config_failed
if not "%WMS_START_INSECURE%"=="1" if not "%WMS_START_INSECURE%"=="0" if not "%WMS_START_INSECURE%"=="unset" goto :config_failed
set "WMS_DEPLOYMENT_MODE=%WMS_START_MODE%"
set "WMS_PORT=%WMS_START_PORT%"
if "%WMS_START_SECURE%"=="unset" (set "SESSION_COOKIE_SECURE=") else (set "SESSION_COOKIE_SECURE=%WMS_START_SECURE%")
if "%WMS_START_INSECURE%"=="unset" (set "WMS_ALLOW_INSECURE_COOKIE=") else (set "WMS_ALLOW_INSECURE_COOKIE=%WMS_START_INSECURE%")
if not defined WMS_HOST set "WMS_HOST=127.0.0.1"
set "WMS_SKIP_AUTO_UPDATE=1"
echo [%date% %time%] Starting configured WMS service...
"%PYTHON_CMD%" "%~dp0run_server.py"
exit /b %ERRORLEVEL%

:config_failed
echo [ERROR] Service configuration preflight failed. No server was started.
exit /b 2
