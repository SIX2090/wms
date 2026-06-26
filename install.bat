@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "PKG_DIR=%~dp0"
set "PKG_DIR=%PKG_DIR:~0,-1%"
set "APP_SRC=%PKG_DIR%\app"
set "WHEELHOUSE=%PKG_DIR%\wheelhouse"
set "PY_INSTALLER=%PKG_DIR%\runtime\python-3.11.9-amd64.exe"
set "INSTALL_DIR=C:\wms"

echo ============================================================
echo WMS offline installer
echo Install dir: %INSTALL_DIR%
echo Default username: admin
echo Default password: admin123
echo ============================================================
echo.

if not exist "%APP_SRC%\app.py" (
  echo [ERROR] Package is incomplete: app\app.py not found.
  pause
  exit /b 1
)

if not exist "%WHEELHOUSE%" (
  echo [ERROR] Package is incomplete: wheelhouse not found.
  pause
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  if not exist "%PY_INSTALLER%" (
    echo [ERROR] Python not found and bundled installer is missing.
    echo Install Python 3.11 x64 first, then run this script again.
    pause
    exit /b 1
  )
  echo [1/8] Python not found. Installing Python 3.11...
  "%PY_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0
  if errorlevel 1 (
    echo [ERROR] Python installer failed.
    pause
    exit /b 1
  )
  set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
  if not exist "!PYTHON_EXE!" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
)

if defined PYTHON_EXE if exist "%PYTHON_EXE%" goto :python_found
for /f "delims=" %%p in ('where python') do (
  set "PYTHON_EXE=%%p"
  goto :python_found
)

:python_found
if not exist "%PYTHON_EXE%" (
  echo [ERROR] python.exe was not found.
  pause
  exit /b 1
)
echo [1/8] Python: %PYTHON_EXE%

echo [2/8] Stopping old WMS process...
if exist "%INSTALL_DIR%\stop_wms_offline.bat" (
  call "%INSTALL_DIR%\stop_wms_offline.bat" >nul 2>nul
) else if exist "%INSTALL_DIR%\stop_wms.bat" (
  call "%INSTALL_DIR%\stop_wms.bat" >nul 2>nul
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $ids = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess); foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } } catch {}" >nul 2>nul
)

echo [3/8] Copying WMS files...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\backups" mkdir "%INSTALL_DIR%\backups"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"
if exist "%INSTALL_DIR%\instance\inventory.db" (
  copy /Y "%INSTALL_DIR%\instance\inventory.db" "%INSTALL_DIR%\backups\before_offline_install_%STAMP%_inventory.db" >nul
)
if exist "%APP_SRC%\instance\inventory.db" (
  echo [ERROR] Package contains a business database and will not install.
  pause
  exit /b 1
)
robocopy "%APP_SRC%" "%INSTALL_DIR%" /E /XD __pycache__ /XF *.pyc >nul
if %ERRORLEVEL% GEQ 8 (
  echo [ERROR] File copy failed.
  pause
  exit /b 1
)

if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\backups" mkdir "%INSTALL_DIR%\backups"
if not exist "%INSTALL_DIR%\instance" mkdir "%INSTALL_DIR%\instance"

echo [4/8] Installing dependencies into system Python...
cd /d "%INSTALL_DIR%" || exit /b 1
echo [5/8] Installing dependencies from local wheelhouse...
"%PYTHON_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" --upgrade pip setuptools wheel
if errorlevel 1 (
  echo [ERROR] Offline pip bootstrap failed.
  pause
  exit /b 1
)
"%PYTHON_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" -r "%INSTALL_DIR%\requirements.txt"
if errorlevel 1 (
  echo [ERROR] Offline dependency installation failed.
  pause
  exit /b 1
)

echo [6/8] Creating empty database and default admin account...
"%PYTHON_EXE%" -c "from app import app, initialize_database; ctx=app.app_context(); ctx.push(); initialize_database(); ctx.pop()"
if errorlevel 1 (
  echo [ERROR] Empty database initialization failed.
  pause
  exit /b 1
)
"%PYTHON_EXE%" "%PKG_DIR%\tools\reset_admin_password.py" "%INSTALL_DIR%\instance\inventory.db" admin admin123
if errorlevel 1 (
  echo [ERROR] Admin account setup failed.
  pause
  exit /b 1
)

echo [7/8] Checking startup scripts...
if not exist "%INSTALL_DIR%\start_wms_offline.bat" (
  echo [ERROR] start_wms_offline.bat not found.
  pause
  exit /b 1
)

echo [8/8] Creating desktop shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop=[Environment]::GetFolderPath('Desktop');" ^
  "$ws=New-Object -ComObject WScript.Shell;" ^
  "$s=$ws.CreateShortcut((Join-Path $desktop 'WMS.lnk'));" ^
  "$s.TargetPath='C:\wms\start_wms_offline.bat';" ^
  "$s.WorkingDirectory='C:\wms';" ^
  "$s.Save();"

echo.
echo ============================================================
echo [OK] WMS installed
echo Start: C:\wms\start_wms_offline.bat
echo Login: http://127.0.0.1:8080/login
echo Username: admin
echo Password: admin123
echo ============================================================
echo.
pause
exit /b 0