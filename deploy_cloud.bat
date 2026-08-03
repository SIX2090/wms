@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "PYTHONUTF8=1"

REM ============================================================
REM WMS Tencent Cloud Windows Server deployment script
REM for Server 2012 R2 / 2016 / 2019 / 2022
REM
REM What it does:
REM   1. Clone/update WMS code to C:\wms
REM   2. Install portable Python 3.11 (does not modify system PATH)
REM   3. Use nssm to install a Windows service with auto-start and log rotation
REM   4. start_wms_auto.bat pulls latest GitHub main on run_server.py trigger
REM
REM Run this batch file as administrator.
REM ============================================================

set "INSTALL_DIR=C:\wms"
set "REPO_URL=https://github.com/SIX2090/wms.git"
set "BRANCH=main"
set "SERVICE_NAME=WMS"
set "NSSM_URL=https://nssm.cc/release/nssm-2.24.zip"
set "NSSM_DIR=%INSTALL_DIR%\runtime\nssm"

echo ============================================================
echo WMS Tencent Cloud deployment
echo Install directory: %INSTALL_DIR%
echo Repository: %REPO_URL%
echo Branch: %BRANCH%
echo Service name: %SERVICE_NAME%
echo ============================================================
echo.

REM ---- administrator privilege check ----
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Administrator privileges are required.
    echo        Please right-click and choose "Run as administrator".
    pause
    exit /b 1
)

REM ---- Step 1: Git check ----
echo [1/4] Checking Git...
where git.exe >nul 2>nul
if not errorlevel 1 (
    echo       Git is already installed.
    goto :git_ready
)

echo       Git not found, downloading installer...
set "GIT_VER=2.47.1"
set "GIT_INSTALLER=%TEMP%\Git-%GIT_VER%-64-bit.exe"
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v%GIT_VER%.windows.1/Git-%GIT_VER%-64-bit.exe"

REM Download Git installer
if not exist "%GIT_INSTALLER%" (
    echo        Downloading Git for Windows %GIT_VER% ...
    powershell -NoProfile -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%GIT_URL%' -OutFile '%GIT_INSTALLER%' -UseBasicParsing }" ^
        "catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo [ERROR] Git download failed.
        echo        Please download Git for Windows manually.
        pause
        exit /b 1
    )
)

REM /VERYSILENT silent install /NORESTART no reboot /NOCANCEL no cancel
echo        Installing Git...
"%GIT_INSTALLER%" /VERYSILENT /NORESTART /NOCANCEL /SP-
if errorlevel 1 (
    echo [ERROR] Git installation failed.
    echo        Please download Git for Windows manually.
    pause
    exit /b 1
)

REM Update PATH to include git.exe (default install path C:\Program Files\Git)
set "PATH=%ProgramFiles%\Git\cmd;%ProgramFiles(x86)%\Git\cmd;%PATH%"
where git.exe >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git installed but git.exe not found.
    echo        Please restart CMD and run again.
    pause
    exit /b 1
)
echo       Git installation completed.

:git_ready

REM AI_TASK: AI-DEPLOY-F01-FIX-03
REM If .git-credentials is not configured, clone/fetch may fail due to missing PAT.
REM Configure git credential helper or place a PAT in .git-credentials before running.
REM Without credentials, WMS service auto-update against GitHub will fail.

REM ---- Step 2: clone / update code ----
echo [2/4] Cloning/updating code...
if exist "%INSTALL_DIR%\.git" (
    echo        Existing installation found, pulling updates...
    cd /d "%INSTALL_DIR%"
    git fetch origin %BRANCH%
    git pull --ff-only origin %BRANCH%
    if errorlevel 1 (
        echo [WARN] git pull failed, continuing with local code.
    )
) else (
    echo        Cloning repository into %INSTALL_DIR% ...
    git clone -b %BRANCH% %REPO_URL% "%INSTALL_DIR%"
    if errorlevel 1 (
        echo [ERROR] git clone failed.
        echo        Repository URL: %REPO_URL%
        pause
        exit /b 1
    )
    cd /d "%INSTALL_DIR%"
)
echo       Code update completed.

REM ---- Step 3: install portable Python ----
echo [3/4] Installing portable Python 3.11...
call "%INSTALL_DIR%\install_portable_python.bat"
if errorlevel 1 (
    echo [ERROR] Portable Python installation failed.
    pause
    exit /b 1
)

REM ---- Step 4: install Windows service ----
echo [4/4] Installing Windows service...

set "NSSM_EXE=%NSSM_DIR%\win64\nssm.exe"
if not exist "%NSSM_EXE%" (
    echo        nssm not found, downloading...
    set "NSSM_ZIP=%INSTALL_DIR%\runtime\nssm-2.24.zip"
    powershell -NoProfile -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%NSSM_URL%' -OutFile '!NSSM_ZIP!' -UseBasicParsing }" ^
        "catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo [ERROR] nssm download failed.
        echo        Please download manually: %NSSM_URL%
        echo        Extract to: %NSSM_DIR%
        pause
        exit /b 1
    )
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '!NSSM_ZIP!' -DestinationPath '%NSSM_DIR%' -Force"
)

if not exist "%NSSM_EXE%" (
    echo [ERROR] nssm.exe not found: %NSSM_EXE%
    echo        Please check nssm extraction path.
    pause
    exit /b 1
)

REM Remove existing service if present
"%NSSM_EXE%" status %SERVICE_NAME% >nul 2>&1
if not errorlevel 1 (
    echo        Existing service found, stopping and removing...
    "%NSSM_EXE%" stop %SERVICE_NAME% >nul 2>&1
    "%NSSM_EXE%" remove %SERVICE_NAME% confirm >nul 2>&1
    timeout /t 2 /nobreak >nul
)

REM Install service
"%NSSM_EXE%" install %SERVICE_NAME% "%INSTALL_DIR%\app\start_wms_auto.bat"
"%NSSM_EXE%" set %SERVICE_NAME% AppDirectory "%INSTALL_DIR%\app"
"%NSSM_EXE%" set %SERVICE_NAME% AppStdout "%INSTALL_DIR%\app\logs\service_stdout.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStderr "%INSTALL_DIR%\app\logs\service_stderr.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateBytes 10485760
"%NSSM_EXE%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM_EXE%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM_EXE%" set %SERVICE_NAME% AppRestartDelay 5000

echo        Starting service...
"%NSSM_EXE%" start %SERVICE_NAME%
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo [INFO] Service status:
"%NSSM_EXE%" status %SERVICE_NAME%
echo.
echo [INFO] Health check:
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/login' -TimeoutSec 10 -UseBasicParsing; Write-Host ('HTTP ' + $r.StatusCode) } catch { Write-Host $_.Exception.Message }"
echo.
echo ============================================================
echo.
echo Deployment completed!
echo.
echo Service commands:
echo   start: nssm start %SERVICE_NAME%
echo   stop: nssm stop %SERVICE_NAME%
echo   restart: nssm restart %SERVICE_NAME%
echo   status: nssm status %SERVICE_NAME%
echo.
echo Log files:
echo   service stdout: %INSTALL_DIR%\app\logs\service_stdout.log
echo   service stderr: %INSTALL_DIR%\app\logs\service_stderr.log
echo   auto-update log: %INSTALL_DIR%\app\logs\auto_update.log
echo.
echo Access URLs:
echo   local: http://127.0.0.1:8080/login
echo   public: configure Nginx for https://gd2026.top/login
echo.
echo Auto-update notes (AI-DEPLOY-F01-FIX-02):
echo   start_wms_auto.bat sets WMS_NO_DB_TOUCH=1; run_server.py trigger start pulls latest GitHub code.
echo   Use nssm restart WMS to force the service to fetch GitHub main branch updates.
echo   If Git credential issues occur, configure git credential helper or use PAT in .git-credentials.
echo   log: %INSTALL_DIR%\app\logs\auto_update.log
echo   manual update: %INSTALL_DIR%\update_from_github.bat
echo.
echo Next steps:
echo   1. Configure Nginx reverse proxy HTTPS to 127.0.0.1:8080
echo      sample: %INSTALL_DIR%\app\nginx_wms_server_block.conf
echo   2. Open TCP 443 in Tencent Cloud security group.
echo   3. Log in and change the default admin password.
echo ============================================================
echo.
pause
exit /b 0
