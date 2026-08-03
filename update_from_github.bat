@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM 部分腾讯云控制台对 chcp 65001 会写设备失败，这里不强制切代码页
set "PYTHONUTF8=1"

REM === 腾讯云 RDP/控制台兼容：部分会话无法直接写入 CON 设备 ===
set "CONSOLE_OK=1"
echo. >con 2>nul
if errorlevel 1 set "CONSOLE_OK=0"

set "ROOT_DIR=%~dp0"
set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "APP_DIR=%ROOT_DIR%\app"
set "BACKUP_DIR=%ROOT_DIR%\backups"
set "NO_DB_TOUCH_FLAG=%APP_DIR%\WMS_NO_DB_TOUCH.flag"
set "BRANCH=main"
set "REMOTE=origin"

if "%CONSOLE_OK%"=="1" (
  echo ============================================================
  echo WMS GitHub one-click updater
  echo Repo: %ROOT_DIR%
  echo Remote: %REMOTE%
  echo Branch: %BRANCH%
  echo ============================================================
  echo.
)
if "%CONSOLE_OK%"=="1" echo.

cd /d "%ROOT_DIR%" || (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Cannot enter WMS directory.
  pause
  exit /b 1
)

where git.exe >nul 2>nul
if errorlevel 1 (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Git was not found. Install Git for Windows first.
  pause
  exit /b 1
)

if not exist "%ROOT_DIR%\.git" (
  if "%CONSOLE_OK%"=="1" echo [ERROR] This directory is not a Git repository: %ROOT_DIR%
  pause
  exit /b 1
)

if not exist "%APP_DIR%\requirements.txt" (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Missing app\requirements.txt. The WMS package looks incomplete.
  pause
  exit /b 1
)

for /f "delims=" %%b in ('git branch --show-current 2^>nul') do set "CURRENT_BRANCH=%%b"
if /i not "%CURRENT_BRANCH%"=="%BRANCH%" (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Current branch is "%CURRENT_BRANCH%", expected "%BRANCH%".
  if "%CONSOLE_OK%"=="1" echo Switch to %BRANCH% manually, then run this updater again.
  pause
  exit /b 1
)

for /f "delims=" %%s in ('git status --porcelain 2^>nul') do (
  set "STATUS_LINE=%%s"
  set "STATUS_PATH=!STATUS_LINE:~3!"
  REM 忽略以下"非业务代码"脏文件，避免它们阻塞一键更新（它们不影响 WMS 运行）：
  REM   - update_from_github.bat / WMS_NO_DB_TOUCH.flag：本脚本自身产物
  REM   - apk_source/：APK 反编译的第三方依赖库源码（androidx/retrofit2/okio 等），
  REM     每次反编译内容都会变，不应视为业务改动
  REM   - app/FETCH_HEAD：git fetch 自动生成的文件
  REM   - app/cd、app/git：cmd 误操作产生的异常文件
  REM   - app/.installed.flag：部署/安装标记文件
  set "SKIP=0"
  if /i "!STATUS_PATH!"=="update_from_github.bat" set "SKIP=1"
  if /i "!STATUS_PATH!"=="app/WMS_NO_DB_TOUCH.flag" set "SKIP=1"
  if /i "!STATUS_PATH!"=="WMS_NO_DB_TOUCH.flag" set "SKIP=1"
  if /i "!STATUS_PATH:~0,11!"=="apk_source/" set "SKIP=1"
  if /i "!STATUS_PATH!"=="app/FETCH_HEAD" set "SKIP=1"
  if /i "!STATUS_PATH!"=="app/cd" set "SKIP=1"
  if /i "!STATUS_PATH!"=="app/git" set "SKIP=1"
  if /i "!STATUS_PATH!"=="app/.installed.flag" set "SKIP=1"
  if "!SKIP!"=="0" set "GIT_DIRTY=1"
)
if defined GIT_DIRTY (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Local code has uncommitted changes.
  if "%CONSOLE_OK%"=="1" echo Commit or remove those changes before running automatic update.
  if "%CONSOLE_OK%"=="1" echo.
  git status --short
  pause
  exit /b 1
)

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"

if "%CONSOLE_OK%"=="1" echo [1/6] Backing up business data...
set "BACKED_UP="
if exist "%APP_DIR%\instance\inventory.db" (
  copy /Y "%APP_DIR%\instance\inventory.db" "%BACKUP_DIR%\before_github_update_%STAMP%_app_inventory.db" >nul
  if errorlevel 1 (
    if "%CONSOLE_OK%"=="1" echo [ERROR] Failed to back up app\instance\inventory.db.
    pause
    exit /b 1
  )
  set "BACKED_UP=1"
  if "%CONSOLE_OK%"=="1" echo Backup: %BACKUP_DIR%\before_github_update_%STAMP%_app_inventory.db
)
if exist "%ROOT_DIR%\instance\inventory.db" (
  copy /Y "%ROOT_DIR%\instance\inventory.db" "%BACKUP_DIR%\before_github_update_%STAMP%_root_inventory.db" >nul
  if errorlevel 1 (
    if "%CONSOLE_OK%"=="1" echo [ERROR] Failed to back up instance\inventory.db.
    pause
    exit /b 1
  )
  set "BACKED_UP=1"
  if "%CONSOLE_OK%"=="1" echo Backup: %BACKUP_DIR%\before_github_update_%STAMP%_root_inventory.db
)
if not defined BACKED_UP (
  if "%CONSOLE_OK%"=="1" echo No inventory.db found yet. Continuing without database backup.
)

if "%CONSOLE_OK%"=="1" echo.
if "%CONSOLE_OK%"=="1" echo Creating production safety flag: %NO_DB_TOUCH_FLAG%
echo WMS update safety flag. Remove this file only when database schema upgrade is allowed.>"%NO_DB_TOUCH_FLAG%"
if errorlevel 1 (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Failed to create WMS_NO_DB_TOUCH.flag.
  pause
  exit /b 1
)

if "%CONSOLE_OK%"=="1" echo.
if "%CONSOLE_OK%"=="1" echo [2/6] Stopping WMS...
if exist "%ROOT_DIR%\stop_wms_offline.bat" (
  call "%ROOT_DIR%\stop_wms_offline.bat"
) else if exist "%APP_DIR%\stop_wms_offline.bat" (
  call "%APP_DIR%\stop_wms_offline.bat"
) else (
  if "%CONSOLE_OK%"=="1" echo [WARN] Stop script not found. Continuing.
)
if errorlevel 1 (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Failed to stop WMS.
  pause
  exit /b 1
)

if "%CONSOLE_OK%"=="1" echo.
if "%CONSOLE_OK%"=="1" echo [3/6] Fetching latest code from GitHub...
git fetch "%REMOTE%" "%BRANCH%"
if errorlevel 1 (
  if "%CONSOLE_OK%"=="1" echo [ERROR] git fetch failed.
  pause
  exit /b 1
)

if "%CONSOLE_OK%"=="1" echo.
if "%CONSOLE_OK%"=="1" echo [4/6] Updating local code...
git pull --ff-only "%REMOTE%" "%BRANCH%"
if errorlevel 1 (
  if "%CONSOLE_OK%"=="1" echo [ERROR] git pull failed. Manual intervention is required.
  pause
  exit /b 1
)

if "%CONSOLE_OK%"=="1" echo.
if "%CONSOLE_OK%"=="1" echo [5/6] Updating Python dependencies...
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
  if "%CONSOLE_OK%"=="1" echo [ERROR] Python was not found.
  pause
  exit /b 1
)

if exist "%ROOT_DIR%\wheelhouse" (
  %PYTHON_CMD% -m pip install --no-index --find-links "%ROOT_DIR%\wheelhouse" -r "%APP_DIR%\requirements.txt"
) else (
  %PYTHON_CMD% -m pip install -r "%APP_DIR%\requirements.txt"
)
if errorlevel 1 (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Dependency update failed.
  pause
  exit /b 1
)

if "%CONSOLE_OK%"=="1" echo.
if "%CONSOLE_OK%"=="1" echo [6/6] Starting WMS...
if exist "%APP_DIR%\restart.py" (
  cd /d "%APP_DIR%" || exit /b 1
  set "WMS_NO_DB_TOUCH=1"
  %PYTHON_CMD% "%APP_DIR%\restart.py"
  cd /d "%ROOT_DIR%" || exit /b 1
) else if exist "%APP_DIR%\start_wms_offline.bat" (
  call "%APP_DIR%\start_wms_offline.bat"
) else if exist "%ROOT_DIR%\start_wms_offline.bat" (
  call "%ROOT_DIR%\start_wms_offline.bat"
) else (
  if "%CONSOLE_OK%"=="1" echo [ERROR] Start script not found.
  pause
  exit /b 1
)

if "%CONSOLE_OK%"=="1" (
  echo.
  echo ============================================================
  echo [OK] WMS update finished.
  echo Login: http://127.0.0.1:8080/login
  echo ============================================================
  echo.
)
pause
exit /b 0
