@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"

REM === Tencent Cloud RDP/console compatibility: some sessions cannot write to CON device ===
set "CONSOLE_OK=1"
echo. >con 2>nul
if errorlevel 1 set "CONSOLE_OK=0"

REM === administrator privilege check (AI-SEC-F01) ===
net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Please run this script as administrator (right-click ^> Run as administrator).
  echo         Installing portable Python and creating directories require admin rights.
  pause
  exit /b 1
)

set "PKG_DIR=%~dp0"
set "PKG_DIR=%PKG_DIR:~0,-1%"
set "APP_SRC=%PKG_DIR%\app"
set "WHEELHOUSE=%PKG_DIR%\wheelhouse"
set "PY_INSTALLER=%PKG_DIR%\runtime\python-3.11.9-amd64.exe"
set "INSTALL_DIR=E:\wms"
set "RUN_DIR=%INSTALL_DIR%"
set "PYTHON_DIR=%INSTALL_DIR%\python"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "IN_PLACE_INSTALL="

for %%I in ("%PKG_DIR%") do set "PKG_DIR_FULL=%%~fI"
for %%I in ("%INSTALL_DIR%") do set "INSTALL_DIR_FULL=%%~fI"
if /i "%PKG_DIR_FULL%"=="%INSTALL_DIR_FULL%" (
  set "IN_PLACE_INSTALL=1"
  set "RUN_DIR=%APP_SRC%"
)

goto :main

REM ==================== log functions (AI-SEC-F01) ====================
:log
if "%CONSOLE_OK%"=="1" echo [%date% %time%] %~1
echo [%date% %time%] %~1>>"%INSTALL_LOG%"
goto :eof

:logerr
if "%CONSOLE_OK%"=="1" echo [%date% %time%] [ERROR] %~1 1>&2
echo [%date% %time%] [ERROR] %~1>>"%INSTALL_LOG%"
goto :eof

REM ==================== rollback functions (AI-SEC-F01) ====================
:do_rollback
call :log "===== start rollback ====="
if defined COPIED_FILES (
  if not defined IN_PLACE_INSTALL (
    if exist "%INSTALL_DIR%\app.py" (
      rd /s /q "%INSTALL_DIR%" >nul 2>nul
      call :log "cleaned install directory: %INSTALL_DIR%"
    )
  )
)
if exist "%USERPROFILE%\Desktop\WMS.lnk" (
  del /q "%USERPROFILE%\Desktop\WMS.lnk" >nul 2>nul
  call :log "deleted desktop shortcut"
)
call :log "===== rollback completed ====="
call :logerr "deployment failed, rolled back. log: %INSTALL_LOG%"
pause
goto :eof

:main
REM banner shown only when console is writable (Tencent Cloud RDP "cannot write to device")
if "%CONSOLE_OK%"=="1" (
  echo ============================================================
  echo WMS offline installer (E:\wms)
  if defined IN_PLACE_INSTALL (
    echo Install mode: in-place
    echo App dir: %RUN_DIR%
  ) else (
    echo Install dir: %INSTALL_DIR%
  )
  echo Default username: admin
  echo Initial password: WMS_BOOTSTRAP_PASSWORD, or admin on first creation when unset
  echo ============================================================
  echo.
)

if not exist "%APP_SRC%\app.py" (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Package is incomplete: app\app.py not found.
  pause
  exit /b 1
)

if not exist "%WHEELHOUSE%" (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Package is incomplete: wheelhouse not found.
  pause
  exit /b 1
)

REM === create log directory (AI-SEC-F01, BUG-2026-07-31-002: some RDP sessions fail PowerShell stdout) ===
if not exist "%RUN_DIR%\logs" mkdir "%RUN_DIR%\logs"
set "STAMP="
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "DATETIME=%%I"
if defined DATETIME set "STAMP=%DATETIME:~0,8%_%DATETIME:~8,6%"
if not defined STAMP (
  set "STAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
  set "STAMP=%STAMP: =0%"
)
if not defined STAMP set "STAMP=manual_%RANDOM%"
set "INSTALL_LOG=%RUN_DIR%\logs\install_%STAMP%.log"
call :log "WMS offline installer (E:\wms) started"
call :log "INSTALL_DIR=%INSTALL_DIR%  RUN_DIR=%RUN_DIR%"

REM === PowerShell version check (AI-SEC-F01) ===
for /f "delims=" %%v in ('powershell -NoProfile -Command "$PSVersionTable.PSVersion.Major" 2^>nul') do set "PS_MAJOR=%%v"
if not defined PS_MAJOR (
  call :logerr "PowerShell not found. Please install WMF 5.1."
  echo         URL: https://www.microsoft.com/download/details.aspx?id=54616
  pause
  exit /b 1
)
if !PS_MAJOR! LSS 5 (
  call :logerr "PowerShell version !PS_MAJOR! is too old; need 5.0+."
  echo         Please install WMF 5.1: https://www.microsoft.com/download/details.aspx?id=54616
  pause
  exit /b 1
)
call :log "PowerShell !PS_MAJOR! OK"

REM === port 8080 check (AI-SEC-F01) ===
powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue; if($c){exit 1} else {exit 0}"
if errorlevel 1 (
  call :logerr "Port 8080 is already in use. Please stop the occupying process first."
  pause
  exit /b 1
)
call :log "Port 8080 is available."

REM === already installed check (AI-SEC-F01) ===
if exist "%RUN_DIR%\.installed.flag" (
  call :log "Already installed. To reinstall, delete .installed.flag and run again."
  pause
  exit /b 0
)

if exist "%PYTHON_EXE%" goto :python_found

set "PYTHON_EXE="
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
)
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python311\python.exe" (
  set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
)
if not defined PYTHON_EXE (
  where python >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%p in ('where python') do (
      set "PYTHON_EXE=%%p"
      goto :python_found
    )
  )
)

if not defined PYTHON_EXE (
  if not exist "%PY_INSTALLER%" (
    call :logerr "Python not found and bundled installer is missing."
    if "%CONSOLE_OK%"=="1" echo Install Python 3.11 x64 first, then run this script again.
    pause
    exit /b 1
  )
  call :log "[1/8] Installing portable Python to %PYTHON_DIR%..."
  if "%CONSOLE_OK%"=="1" echo          Python will NOT be added to system PATH.
  if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"
  "%PY_INSTALLER%" /quiet InstallAllUsers=0 TargetDir="%PYTHON_DIR%" PrependPath=0 Include_pip=1 Include_test=0
  if errorlevel 1 (
    call :logerr "Python installer failed."
    if "%CONSOLE_OK%"=="1" echo Try right-clicking install_e_wms.bat and choose "Run as administrator".
    set "ROLLBACK_NEEDED=1"
    call :do_rollback
    exit /b 1
  )
  set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
)

if defined PYTHON_EXE if exist "%PYTHON_EXE%" goto :python_found

:python_found
if not exist "%PYTHON_EXE%" (
  call :logerr "python.exe was not found."
  pause
  exit /b 1
)
call :log "[1/8] Python resolved: %PYTHON_EXE%"

call :log "[2/8] Stopping old WMS process..."
if exist "%INSTALL_DIR%\stop_wms_offline.bat" (
  call "%INSTALL_DIR%\stop_wms_offline.bat" >nul 2>nul
) else if exist "%INSTALL_DIR%\stop_wms.bat" (
  call "%INSTALL_DIR%\stop_wms.bat" >nul 2>nul
) else (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $ids = @(Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess); foreach ($id in $ids) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } } catch {}" >nul 2>nul
)

call :log "[3/8] Copying WMS files..."
if defined IN_PLACE_INSTALL (
  call :log "In-place install, skipping file copy."
) else (
  if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
  if not exist "%INSTALL_DIR%\backups" mkdir "%INSTALL_DIR%\backups"
)
if not exist "%RUN_DIR%\backups" mkdir "%RUN_DIR%\backups"
if exist "%RUN_DIR%\instance\inventory.db" (
  copy /Y "%RUN_DIR%\instance\inventory.db" "%RUN_DIR%\backups\before_offline_install_%STAMP%_inventory.db" >nul
  call :log "Backed up existing inventory.db"
)
if not defined IN_PLACE_INSTALL if exist "%APP_SRC%\instance\inventory.db" (
  call :logerr "Package contains a business database and will not install."
  pause
  exit /b 1
)
if not defined IN_PLACE_INSTALL (
  robocopy "%APP_SRC%" "%INSTALL_DIR%" /E /XD __pycache__ /XF *.pyc >nul
  if !ERRORLEVEL! GEQ 8 (
    call :logerr "File copy failed."
    set "ROLLBACK_NEEDED=1"
    set "COPIED_FILES=1"
    call :do_rollback
    exit /b 1
  )
  set "COPIED_FILES=1"
  call :log "File copy completed."
)

if not exist "%RUN_DIR%\logs" mkdir "%RUN_DIR%\logs"
if not exist "%RUN_DIR%\backups" mkdir "%RUN_DIR%\backups"
if not exist "%RUN_DIR%\instance" mkdir "%RUN_DIR%\instance"

call :log "[4/8] Installing dependencies into portable Python..."
cd /d "%RUN_DIR%" || (
  call :logerr "Cannot enter RUN_DIR."
  set "ROLLBACK_NEEDED=1"
  call :do_rollback
  exit /b 1
)
call :log "[5/8] Installing dependencies from local wheelhouse..."
"%PYTHON_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" --upgrade pip setuptools wheel
if errorlevel 1 (
  call :logerr "Offline pip bootstrap failed."
  set "ROLLBACK_NEEDED=1"
  call :do_rollback
  exit /b 1
)
"%PYTHON_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" -r "%RUN_DIR%\requirements.txt"
if errorlevel 1 (
  call :logerr "Offline dependency installation failed."
  set "ROLLBACK_NEEDED=1"
  set "DEPS_INSTALLED=1"
  call :do_rollback
  exit /b 1
)
set "DEPS_INSTALLED=1"
call :log "Dependencies installed."

call :log "[6/8] Creating empty database and default admin account..."
set "WMS_ALLOW_AUTO_SECRET_KEY=1"
set "WMS_INIT_SAMPLE_DATA=0"
"%PYTHON_EXE%" -c "from app import app, initialize_database; ctx=app.app_context(); ctx.push(); initialize_database(); ctx.pop()"
if errorlevel 1 (
  call :logerr "Empty database initialization failed."
  set "ROLLBACK_NEEDED=1"
  set "DB_INITIALIZED=1"
  call :do_rollback
  exit /b 1
)
set "DB_INITIALIZED=1"
call :log "Database initialized."
call :log "[7/8] Checking startup scripts..."
if defined IN_PLACE_INSTALL (
  set "START_SCRIPT=%PKG_DIR%\start_wms_offline.bat"
  set "START_WORKDIR=%PKG_DIR%"
) else (
  set "START_SCRIPT=%INSTALL_DIR%\start_wms_offline.bat"
  set "START_WORKDIR=%INSTALL_DIR%"
)
if not exist "%START_SCRIPT%" (
  call :logerr "start_wms_offline.bat not found."
  pause
  exit /b 1
)

call :log "[8/8] Creating desktop shortcuts..."
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop=[Environment]::GetFolderPath('Desktop');" ^
  "$ws=New-Object -ComObject WScript.Shell;" ^
  "$s=$ws.CreateShortcut((Join-Path $desktop 'WMS.lnk'));" ^
  "$s.TargetPath='%START_SCRIPT%';" ^
  "$s.WorkingDirectory='%START_WORKDIR%';" ^
  "$s.Save();"
if errorlevel 1 (
  call :logerr "Desktop shortcut creation failed (non-fatal)."
) else (
  set "SHORTCUT_CREATED=1"
  call :log "Desktop shortcut created."
)

REM === write installation marker flag (AI-SEC-F01) ===
echo installed > "%RUN_DIR%\.installed.flag"
call :log "Installation flag written."

if "%CONSOLE_OK%"=="1" (
  echo.
  echo ============================================================
  echo [OK] WMS installed to E:\wms
  echo Python: %PYTHON_DIR% (portable, not in system PATH)
  echo Start: %START_SCRIPT%
  echo Login: http://127.0.0.1:8080/login
  echo Username: admin
  echo Initial password: admin
  echo ============================================================
  echo.
)
call :log "WMS installation completed successfully."
pause
exit /b 0
