@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
set "PYTHON_EXE="

if defined WMS_PYTHON if exist "%WMS_PYTHON%" set "PYTHON_EXE=%WMS_PYTHON%"
if not defined PYTHON_EXE if exist "%ROOT_DIR%\.venv\python.exe" set "PYTHON_EXE=%ROOT_DIR%\.venv\python.exe"
if not defined PYTHON_EXE if exist "%ROOT_DIR%\.venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT_DIR%\.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT_DIR%\venv\Scripts\python.exe" set "PYTHON_EXE=%ROOT_DIR%\venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%ROOT_DIR%\python\python.exe" set "PYTHON_EXE=%ROOT_DIR%\python\python.exe"
if not defined PYTHON_EXE if exist "%ROOT_DIR%\dist\WMS\python\python.exe" set "PYTHON_EXE=%ROOT_DIR%\dist\WMS\python\python.exe"
if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python311\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"

if not defined PYTHON_EXE (
    echo [ERROR] Python 3.11 runtime was not found.
    echo [HINT] Install Python 3.11, build the portable package, or set WMS_PYTHON.
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%ROOT_DIR%\app;%PYTHONPATH%"

"%PYTHON_EXE%" "%SCRIPT_DIR%verify_python_runtime.py" --quiet
if errorlevel 1 exit /b 1

if /I "%~1"=="--check" (
    "%PYTHON_EXE%" "%SCRIPT_DIR%verify_python_runtime.py"
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="--print" (
    echo %PYTHON_EXE%
    exit /b 0
)

"%PYTHON_EXE%" %*
exit /b %ERRORLEVEL%
