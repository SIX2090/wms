@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM 部分腾讯云控制台对 chcp 65001 会写设备失败，这里不强制切代码页
cd /d "%~dp0" || exit /b 1
for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
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
    echo [%date% %time%] [ERROR] Python 未找到，无法启动 WMS
    exit /b 1
)

echo [%date% %time%] 启动 WMS 服务（auto_update 由 run_server.py 触发）...
"%PYTHON_CMD%" "%~dp0run_server.py"
