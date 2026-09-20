@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Use PYTHONUTF8=1 for UTF-8 support.
cd /d "%~dp0" || exit /b 1

REM 确保 logs 目录存在（Python RotatingFileHandler 用）
if not exist "%~dp0logs" mkdir "%~dp0logs"

for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
set "WMS_ALLOW_AUTO_SECRET_KEY=1"
set "WMS_NO_DB_TOUCH=1"
REM BUG-2026-09-19-003：生产模式下若 SESSION_COOKIE_SECURE 未启用，
REM config.py 的 validate_production_security_config 会**直接拒绝启动**
REM （防 HTTP 明文会话 Cookie）。本脚本用于**本机/可信内网离线部署**
REM （http://127.0.0.1:8080），故显式 opt-in 放行；启动日志会打一条
REM CRITICAL 告警提示该风险，属预期输出。
REM ⚠️ 若部署到 HTTPS 环境：删掉下面这行，并改设 SESSION_COOKIE_SECURE=true。
set "WMS_ALLOW_INSECURE_COOKIE=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

echo Starting WMS...
echo URL: http://127.0.0.1:8080/login
echo Username: admin
echo Initial password: WMS_BOOTSTRAP_PASSWORD, or admin on first creation when unset
echo Log file: %~dp0logs\app.log
echo.

REM 查找 Python：优先便携版，其次系统安装版
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

REM 自动修复数据库字段
echo [Auto-Fix] Checking database columns...
"%PYTHON_CMD%" "fix_db_columns.py"
echo.

"%PYTHON_CMD%" "run_server.py"
pause
