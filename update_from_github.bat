@echo off
setlocal EnableExtensions
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
REM Repair task: AUDIT-FULL-20261016-001-F04 (2026-10-17).
REM No shell stop/pull/pip steps here; the controller preserves and checks every result.
set "ROOT_DIR=%~dp0"
set "PYTHON_CMD="
set "PYTHON_ARGS="
if exist "%ROOT_DIR%python\python.exe" set "PYTHON_CMD=%ROOT_DIR%python\python.exe"
if not defined PYTHON_CMD if exist "%ROOT_DIR%runtime\Python311\python.exe" set "PYTHON_CMD=%ROOT_DIR%runtime\Python311\python.exe"
if not defined PYTHON_CMD if exist "%ROOT_DIR%app\python\python.exe" set "PYTHON_CMD=%ROOT_DIR%app\python\python.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PYTHON_CMD (
  where python.exe >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python.exe"
)
if not defined PYTHON_CMD (
  where py.exe >nul 2>nul
  if not errorlevel 1 (
    set "PYTHON_CMD=py.exe"
    set "PYTHON_ARGS=-3"
  )
)
if not defined PYTHON_CMD (
  echo [ERROR] Python not found. WMS was not stopped.
  if /i not "%~1"=="--noninteractive" pause
  exit /b 1
)
"%PYTHON_CMD%" %PYTHON_ARGS% "%ROOT_DIR%scripts\update_from_github.py"
set "UPDATE_RESULT=%ERRORLEVEL%"
if /i not "%~1"=="--noninteractive" pause
exit /b %UPDATE_RESULT%
