@echo off
REM ============================================================
REM WMS 离线数据库恢复（F1.2 / P0-1）
REM
REM 用法:
REM   restore_offline.bat <备份文件路径>
REM
REM 流程: 确认 WMS 已停止 -> 校验备份 -> 留底当前库 -> 覆盖 -> 校验
REM 全部安全约束在 scripts\restore_backup.py 内实现，本脚本只做
REM Python 探测与停机提醒。
REM ============================================================
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"

set "ROOT_DIR=%~dp0"
set "ROOT_DIR=%ROOT_DIR:~0,-1%"

if "%~1"=="" (
  echo 用法: restore_offline.bat ^<备份文件路径^>
  echo 示例: restore_offline.bat C:\wms_backups\auto_daily_20261011_020000_inventory.db
  pause
  exit /b 1
)

echo ============================================================
echo  WMS 离线数据库恢复
echo ============================================================
echo.
echo [警告] 恢复前必须停止 WMS 服务（否则脚本会拒绝执行）：
echo   - 计划任务/命令行启动的: 关闭运行中的 python 窗口或结束 python 进程
echo   - 请勿在恢复完成前重新启动
echo.

REM Python 探测（与 update_from_github.bat 同一顺序）
set "PY="
if exist "%ROOT_DIR%\python\python.exe" set "PY=%ROOT_DIR%\python\python.exe"
if not defined PY if exist "%ROOT_DIR%\runtime\Python311\python.exe" set "PY=%ROOT_DIR%\runtime\Python311\python.exe"
if not defined PY if exist "%ROOT_DIR%\app\python\python.exe" set "PY=%ROOT_DIR%\app\python\python.exe"
if not defined PY (
  where python.exe >nul 2>nul
  if not errorlevel 1 set "PY=python.exe"
)
if not defined PY (
  where py.exe >nul 2>nul
  if not errorlevel 1 set "PY=py.exe -3"
)
if not defined PY if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PY (
  echo [ERROR] Python 未找到，无法执行恢复。
  pause
  exit /b 1
)

%PY% "%ROOT_DIR%\scripts\restore_backup.py" %*
if errorlevel 1 (
  echo.
  echo [ERROR] 恢复未完成，详见上方输出。
  pause
  exit /b 1
)
echo.
pause
