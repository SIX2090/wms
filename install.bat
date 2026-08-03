@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"

REM === 腾讯云 RDP/控制台兼容：部分会话无法直接写入 CON 设备 ===
set "CONSOLE_OK=1"
echo. >con 2>nul
if errorlevel 1 set "CONSOLE_OK=0"

REM === 管理员权限校验（AI-SEC-F01）===
net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 请以管理员身份运行此脚本（右键 → 以管理员身份运行）。
  echo         安装 Python、写入系统路径需要管理员权限。
  pause
  exit /b 1
)

set "PKG_DIR=%~dp0"
set "PKG_DIR=%PKG_DIR:~0,-1%"
set "APP_SRC=%PKG_DIR%\app"
set "WHEELHOUSE=%PKG_DIR%\wheelhouse"
set "PY_INSTALLER=%PKG_DIR%\runtime\python-3.11.9-amd64.exe"
set "INSTALL_DIR=C:\WMS"
set "RUN_DIR=%INSTALL_DIR%"
set "IN_PLACE_INSTALL="

for %%I in ("%PKG_DIR%") do set "PKG_DIR_FULL=%%~fI"
for %%I in ("%INSTALL_DIR%") do set "INSTALL_DIR_FULL=%%~fI"
if /i "%PKG_DIR_FULL%"=="%INSTALL_DIR_FULL%" (
  set "IN_PLACE_INSTALL=1"
  set "RUN_DIR=%APP_SRC%"
)

goto :main

REM ==================== 日志函数（AI-SEC-F01）====================
:log
if "%CONSOLE_OK%"=="1" echo [%date% %time%] %~1
echo [%date% %time%] %~1>>"%INSTALL_LOG%"
goto :eof

:logerr
if "%CONSOLE_OK%"=="1" echo [%date% %time%] [ERROR] %~1 1>&2
echo [%date% %time%] [ERROR] %~1>>"%INSTALL_LOG%"
goto :eof

REM ==================== 回滚函数（AI-SEC-F01）====================
:do_rollback
call :log "===== 开始回滚 ====="
if defined COPIED_FILES (
  if not defined IN_PLACE_INSTALL (
    if exist "%INSTALL_DIR%\app.py" (
      rd /s /q "%INSTALL_DIR%" >nul 2>nul
      call :log "已清理安装目录: %INSTALL_DIR%"
    )
  )
)
if exist "%USERPROFILE%\Desktop\WMS.lnk" (
  del /q "%USERPROFILE%\Desktop\WMS.lnk" >nul 2>nul
  call :log "已删除桌面快捷方式"
)
call :log "===== 回滚完成 ====="
call :logerr "部署失败，已回滚。详见日志: %INSTALL_LOG%"
pause
goto :eof

:main
REM banner 只在控制台可写时输出，避免腾讯云 RDP 会话报 "cannot write to device"
if "%CONSOLE_OK%"=="1" (
  echo ============================================================
  echo WMS offline installer
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

REM === 文件日志初始化（AI-SEC-F01；BUG-2026-07-31-002 修复：避免 RDP 会话下 PowerShell stdout 失败）===
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
call :log "WMS offline installer started"
call :log "INSTALL_DIR=%INSTALL_DIR%  RUN_DIR=%RUN_DIR%"

REM === PowerShell 版本预检（AI-SEC-F01）===
for /f "delims=" %%v in ('powershell -NoProfile -Command "$PSVersionTable.PSVersion.Major" 2^>nul') do set "PS_MAJOR=%%v"
if not defined PS_MAJOR (
  call :logerr "PowerShell 未找到。请安装 WMF 5.1。"
  echo         下载: https://www.microsoft.com/download/details.aspx?id=54616
  pause
  exit /b 1
)
if !PS_MAJOR! LSS 5 (
  call :logerr "PowerShell 版本 !PS_MAJOR! 过低，需要 5.0+。"
  echo         请安装 WMF 5.1: https://www.microsoft.com/download/details.aspx?id=54616
  pause
  exit /b 1
)
call :log "PowerShell !PS_MAJOR! OK"

REM === 端口预检（AI-SEC-F01）===
powershell -NoProfile -Command "$c=Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue; if($c){exit 1} else {exit 0}"
if errorlevel 1 (
  call :logerr "端口 8080 已被占用，部署中止。请先停止占用该端口的进程。"
  pause
  exit /b 1
)
call :log "端口 8080 空闲"

REM === 幂等性检查（AI-SEC-F01）===
if exist "%RUN_DIR%\.installed.flag" (
  call :log "检测到已安装标记，跳过重复安装。如需重新安装，请先删除 .installed.flag 并卸载旧版本。"
  pause
  exit /b 0
)

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
  call :log "[1/8] Installing Python 3.11..."
  "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
  if errorlevel 1 (
    call :logerr "Python installer failed."
    if "%CONSOLE_OK%"=="1" echo Try right-clicking install.bat and choose "Run as administrator", or install Python 3.11 x64 manually.
    set "ROLLBACK_NEEDED=1"
    call :do_rollback
    exit /b 1
  )
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
  if not exist "!PYTHON_EXE!" set "PYTHON_EXE=%ProgramFiles%\Python311\python.exe"
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

call :log "[4/8] Installing dependencies into system Python..."
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

REM === 写入安装标记（AI-SEC-F01 幂等性）===
echo installed > "%RUN_DIR%\.installed.flag"
call :log "Installation flag written."

if "%CONSOLE_OK%"=="1" (
  echo.
  echo ============================================================
  echo [OK] WMS installed
  echo Start: %START_SCRIPT%
  echo Login: http://127.0.0.1:8080/login
  echo Username: admin
  echo Initial password: WMS_BOOTSTRAP_PASSWORD, or admin on first creation when unset
  echo ============================================================
  echo.
)
call :log "WMS installation completed successfully."
pause
exit /b 0
