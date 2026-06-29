@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0" || exit /b 1
for %%I in ("%~dp0..") do set "APP_ROOT=%%~fI"
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
set "WMS_ALLOW_AUTO_SECRET_KEY=1"
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
echo Starting WMS...
echo URL: http://127.0.0.1:8080/login
echo Username: admin
echo Password: admin123
echo.
set "PYTHON_CMD="
if exist "%APP_ROOT%\python\python.exe" (
    set "PYTHON_CMD=%APP_ROOT%\python\python.exe"
)
if not defined PYTHON_CMD if exist "%APP_ROOT%\python\Scripts\python.exe" (
    set "PYTHON_CMD=%APP_ROOT%\python\Scripts\python.exe"
)
if not defined PYTHON_CMD if exist "%~dp0python\python.exe" (
    set "PYTHON_CMD=%~dp0python\python.exe"
)
if not defined PYTHON_CMD if exist "%~dp0python\Scripts\python.exe" (
    set "PYTHON_CMD=%~dp0python\Scripts\python.exe"
)
if not defined PYTHON_CMD (
    where python.exe >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python.exe"
    ) else (
        where py.exe >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py.exe -3"
    )
)
if not defined PYTHON_CMD (
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    )
)
if not defined PYTHON_CMD (
    echo Python runtime was not found.
    echo For user computers, run dist\WMS\??WMS.bat from the portable package.
    echo For development computers, run tools\build_portable_dist.ps1 first or install Python 3.11.
    pause
    exit /b 1
)
%PYTHON_CMD% "run_server.py"
pause
