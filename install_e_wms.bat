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

REM ==================== fatal installation endpoint (AI-SEC-F01) ====================
:do_rollback
REM Repair task: AUDIT-FULL-20261016-001-F05. Preserve the entire failure scene.
call :log "===== installation stopped; existing data retained ====="
call :log "No automatic directory or desktop shortcut cleanup."
call :logerr "Deployment incomplete. Program files or dependencies may have changed; no complete rollback was performed."
call :logerr "Keep the install directory and shortcuts. Review log before repair: %INSTALL_LOG%"
pause
exit /b 1

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
REM Culture-independent and unique backup/log names; WMIC is absent on newer Windows.
for /f "delims=" %%I in ('powershell -NoProfile -Command "(Get-Date -Format yyyyMMdd_HHmmss_fffffff) + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)" 2^>nul') do set "STAMP=%%I"
if not defined STAMP set "STAMP=manual_%RANDOM%_%RANDOM%"
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
    goto :do_rollback
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
REM Use packaged identity verifier, never an old target stop script or port-only kill.
if not exist "%APP_SRC%\service_control.py" (
  call :logerr "Missing safe process verifier. Installation stopped before file copy."
  pause
  exit /b 1
)
"%PYTHON_EXE%" "%APP_SRC%\service_control.py" stop --app-dir "%RUN_DIR%"
if errorlevel 1 (
  call :logerr "Cannot confirm old WMS identity. Stop the verified instance manually, then retry."
  pause
  exit /b 1
)

call :log "[3/8] Copying WMS files..."
if defined IN_PLACE_INSTALL (
  call :log "In-place install, skipping file copy."
) else (
  if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
  if not exist "%INSTALL_DIR%\backups" mkdir "%INSTALL_DIR%\backups"
)
if not exist "%RUN_DIR%\backups" mkdir "%RUN_DIR%\backups"
REM Preserve customized program configuration before overwriting program files.
if exist "%RUN_DIR%\config.py" (
  copy /Y "%RUN_DIR%\config.py" "%RUN_DIR%\backups\before_offline_install_%STAMP%_config.py" >nul
  if errorlevel 1 (
    call :logerr "Could not preserve existing config.py. Installation stopped before copy."
    goto :do_rollback
  )
)
if exist "%RUN_DIR%\instance\inventory.db" (
  if not exist "%PKG_DIR%\scripts\restore_backup.py" (
    call :logerr "Missing read-only database validator. Use a complete source installation package."
    goto :do_rollback
  )
  if not exist "%PKG_DIR%\scripts\online_backup.py" (
    call :logerr "Missing consistent backup tool. Existing database was not changed."
    goto :do_rollback
  )
  "%PYTHON_EXE%" "%PKG_DIR%\scripts\restore_backup.py" "%RUN_DIR%\instance\inventory.db" --validate-only
  if errorlevel 1 (
    call :logerr "Existing database validation failed. It is preserved; manual maintenance is required."
    goto :do_rollback
  )
  "%PYTHON_EXE%" "%PKG_DIR%\scripts\online_backup.py" "%RUN_DIR%\instance\inventory.db" "%RUN_DIR%\backups\before_offline_install_%STAMP%_inventory.db"
  if errorlevel 1 (
    call :logerr "Consistent database backup failed. Installation stopped before file copy."
    goto :do_rollback
  )
  call :log "Consistent existing database backup completed."
)
if not defined IN_PLACE_INSTALL if exist "%APP_SRC%\instance\inventory.db" (
  call :logerr "Package contains a business database and will not install."
  pause
  exit /b 1
)
if not defined IN_PLACE_INSTALL (
  robocopy "%APP_SRC%" "%INSTALL_DIR%" /E /XD __pycache__ instance backups logs uploads .git /XF *.pyc *.flag .env .env.* *.db *.db-* *.sqlite *.sqlite-* *.sqlite3 *.sqlite3-* *.pem *.key *.pfx *.p12 *.jks *.keystore >nul
  if !ERRORLEVEL! GEQ 8 (
    call :logerr "File copy failed."
    set "ROLLBACK_NEEDED=1"
    set "COPIED_FILES=1"
    goto :do_rollback
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
  goto :do_rollback
)
call :log "[5/8] Installing dependencies from local wheelhouse..."
"%PYTHON_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" --upgrade pip setuptools wheel
if errorlevel 1 (
  call :logerr "Offline pip bootstrap failed."
  set "ROLLBACK_NEEDED=1"
  goto :do_rollback
)
"%PYTHON_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" -r "%RUN_DIR%\requirements.txt"
if errorlevel 1 (
  call :logerr "Offline dependency installation failed."
  set "ROLLBACK_NEEDED=1"
  set "DEPS_INSTALLED=1"
  goto :do_rollback
)
set "DEPS_INSTALLED=1"
call :log "Dependencies installed."

call :log "[6/8] Checking existing database or initializing a fresh installation..."
if exist "%RUN_DIR%\instance\inventory.db" (
  if not exist "%PKG_DIR%\scripts\restore_backup.py" (
    call :logerr "Existing database needs the read-only validator. No initialization was attempted."
    goto :do_rollback
  )
  "%PYTHON_EXE%" "%PKG_DIR%\scripts\restore_backup.py" "%RUN_DIR%\instance\inventory.db" --validate-only
  if errorlevel 1 (
    call :logerr "Existing database is invalid or incomplete. Kept unchanged; no initialization was attempted."
    goto :do_rollback
  )
  call :log "Existing business database retained. Initialization skipped."
) else (
  set "WMS_ALLOW_AUTO_SECRET_KEY=1"
  set "WMS_INIT_SAMPLE_DATA=0"
  REM Offline installer explicitly targets trusted HTTP; respect an explicit opt-out/HTTPS.
  if not defined WMS_ALLOW_INSECURE_COOKIE if /I not "%SESSION_COOKIE_SECURE%"=="true" if /I not "%SESSION_COOKIE_SECURE%"=="1" if /I not "%SESSION_COOKIE_SECURE%"=="yes" set "WMS_ALLOW_INSECURE_COOKIE=1"
  "%PYTHON_EXE%" -c "from app import app, initialize_database; ctx=app.app_context(); ctx.push(); initialize_database(); ctx.pop()"
  if errorlevel 1 (
    call :logerr "Empty database initialization failed."
    set "ROLLBACK_NEEDED=1"
    set "DB_INITIALIZED=1"
    goto :do_rollback
  )
  set "DB_INITIALIZED=1"
  call :log "Database initialized."
)
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
set "WMS_INSTALL_MARKER=%RUN_DIR%\.installed.flag"
"%PYTHON_EXE%" -c "import os; from pathlib import Path; Path(os.environ['WMS_INSTALL_MARKER']).write_text('installed\n', encoding='ascii')"
if errorlevel 1 (
  call :logerr "Installation marker could not be written. Installation is incomplete."
  goto :do_rollback
)
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
