@echo off
setlocal EnableExtensions EnableDelayedExpansion
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
    echo [%date% %time%] [ERROR] Python not found; failed to start WMS
    exit /b 1
)

echo [%date% %time%] Starting WMS service (auto-update via run_server.py trigger)...
"%PYTHON_CMD%" "%~dp0run_server.py"
