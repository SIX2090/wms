@echo off
setlocal EnableExtensions
set "PYTHONUTF8=1"
REM Repair task: AUDIT-FULL-20261016-001-F03. Never kill by port or directory substring.
for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "PYTHON_CMD="
if exist "%APP_ROOT%\python\python.exe" set "PYTHON_CMD=%APP_ROOT%\python\python.exe"
if not defined PYTHON_CMD if exist "%~dp0python\python.exe" set "PYTHON_CMD=%~dp0python\python.exe"
if not defined PYTHON_CMD if exist "%APP_ROOT%\runtime\Python311\python.exe" set "PYTHON_CMD=%APP_ROOT%\runtime\Python311\python.exe"
if not defined PYTHON_CMD if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_CMD (
  where python.exe >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=python.exe"
)
if not defined PYTHON_CMD (
  echo [ERROR] Python not found. Stop the verified WMS instance manually.
  exit /b 1
)
"%PYTHON_CMD%" "%~dp0service_control.py" stop %*
exit /b %ERRORLEVEL%
