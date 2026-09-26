@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Use PYTHONUTF8=1 for UTF-8 support.
cd /d "%~dp0" || exit /b 1

REM Ensure logs directory exists (used by Python RotatingFileHandler).
if not exist "%~dp0logs" mkdir "%~dp0logs"

for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
set "WMS_ALLOW_AUTO_SECRET_KEY=1"
set "WMS_NO_DB_TOUCH=1"
REM BUG-2026-09-19-003: in production mode, if SESSION_COOKIE_SECURE is not
REM enabled, config.py validate_production_security_config will REFUSE to start
REM (prevents plaintext session cookies over HTTP). This script targets
REM offline deployment on localhost / trusted intranet (http://127.0.0.1:8080),
REM so we explicitly opt in below; startup logs one CRITICAL warning about the
REM risk, which is expected output.
REM WARNING: for HTTPS deployments, delete the next line and set
REM SESSION_COOKIE_SECURE=true instead.
set "WMS_ALLOW_INSECURE_COOKIE=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

echo Starting WMS...
echo URL: http://127.0.0.1:8080/login
echo Username: admin
echo Initial password: WMS_BOOTSTRAP_PASSWORD, or admin on first creation when unset
echo Log file: %~dp0logs\app.log
echo.

REM Locate Python: prefer the portable runtime, fall back to system installs.
set "PYTHON_CMD="
if exist "%APP_ROOT%\python\python.exe" set "PYTHON_CMD=%APP_ROOT%\python\python.exe"
if not defined PYTHON_CMD if exist "%APP_ROOT%\python\Scripts\python.exe" set "PYTHON_CMD=%APP_ROOT%\python\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%~dp0python\python.exe" set "PYTHON_CMD=%~dp0python\python.exe"
if not defined PYTHON_CMD if exist "%~dp0python\Scripts\python.exe" set "PYTHON_CMD=%~dp0python\Scripts\python.exe"
if not defined PYTHON_CMD if exist "%APP_ROOT%\runtime\Python311\python.exe" set "PYTHON_CMD=%APP_ROOT%\runtime\Python311\python.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python313\python.exe"

if not defined PYTHON_CMD (
    echo Python runtime was not found.
    pause
    exit /b 1
)

REM Auto-fix database columns.
echo [Auto-Fix] Checking database columns...
"%PYTHON_CMD%" "fix_db_columns.py"
echo.

"%PYTHON_CMD%" "run_server.py"
pause
