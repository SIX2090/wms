@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0" || exit /b 1
set "FLASK_ENV=production"
set "PYTHONUTF8=1"
set "WMS_ALLOW_AUTO_SECRET_KEY=1"
echo Starting WMS...
echo URL: http://127.0.0.1:8080/login
echo Username: admin
echo Password: admin123 (or check startup logs for the generated password)
echo.
set "PYTHON_CMD="
where python.exe >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python.exe"
) else (
    where py.exe >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=py.exe -3"
)
if not defined PYTHON_CMD (
    if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
        set "PYTHON_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
    )
)
if not defined PYTHON_CMD (
    echo Python was not found. Please install Python 3.11 and tick Add python.exe to PATH.
    pause
    exit /b 1
)
%PYTHON_CMD% "run_server.py"
pause
