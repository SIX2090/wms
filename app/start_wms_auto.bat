@echo off
REM AI-DEPLOY-F01: 服务自启入口（nssm 注册目标）
REM
REM 本脚本是 deploy_cloud.bat 注册的 Windows 服务入口，专为无交互终端的服务模式设计：
REM - 不含 pause（pause 会卡死 nssm 服务进程）
REM - 不直接执行 auto_update.py（由 run_server.py 内置 _run_startup_auto_update 统一触发，避免重复）
REM - Python 查找逻辑与 start_wms_offline.bat 一致（优先绿色版，回退系统 Python）
REM
REM 交互式启动请用 start_wms_offline.bat（含错误提示 pause）；
REM 服务自启用本脚本（无 pause，适配 nssm）。
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0" || exit /b 1
for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

REM 查找 Python（优先绿色版，回退系统 Python）
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

REM AI-DEPLOY-F01: auto_update 由 run_server.py 内置 _run_startup_auto_update 统一触发，
REM 此处不再单独执行 auto_update.py，避免重复触发。
echo [%date% %time%] 启动 WMS 服务（auto_update 由 run_server.py 触发）...
"%PYTHON_CMD%" "%~dp0run_server.py"
