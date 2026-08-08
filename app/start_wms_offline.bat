@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Use PYTHONUTF8=1 for UTF-8 support.
cd /d "%~dp0" || exit /b 1

REM 生成日志文件名（带时间戳）
for /f "tokens=2 delims==" %%a in ('wmic os get localdatetime /value') do set "LDT=%%a"
set "LOG_FILE=%~dp0wms_start_%LDT:~0,8%_%LDT:~8,6%.log"
echo WMS start log: %LOG_FILE%
echo.

REM 所有输出重定向到日志文件，控制台仅显示日志路径和退出提示
call :run >> "%LOG_FILE%" 2>&1
echo.
echo WMS exited. See log: %LOG_FILE%
pause
exit /b 0

:run
for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
set "WMS_ALLOW_AUTO_SECRET_KEY=1"
set "WMS_NO_DB_TOUCH=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

echo Starting WMS...
echo URL: http://127.0.0.1:8080/login
echo Username: admin
echo Initial password: WMS_BOOTSTRAP_PASSWORD, or admin on first creation when unset
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
    exit /b 1
)

REM 自动修复数据库字段
echo [Auto-Fix] Checking database columns...
"%PYTHON_CMD%" "fix_db_columns.py"
echo.

"%PYTHON_CMD%" "run_server.py"
