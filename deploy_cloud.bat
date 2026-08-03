@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM 部分腾讯云控制台对 chcp 65001 会写设备失败，这里不强制切代码页
set "PYTHONUTF8=1"

REM ============================================================
REM WMS 腾讯云 Windows Server 一键部署脚本
REM 适用于 Server 2012 R2 / 2016 / 2019 / 2022
REM
REM 功能：
REM   1. 克隆/更新 WMS 仓库到 C:\wms
REM   2. 部署绿色版 Python 3.11（不污染系统 PATH）
REM   3. 用 nssm 注册 Windows 服务（开机自启 + 崩溃自恢复）
REM   4. 每次服务启动自动从 GitHub main 拉取最新代码
REM
REM 使用方式：管理员身份运行本脚本
REM ============================================================

set "INSTALL_DIR=C:\wms"
set "REPO_URL=https://github.com/SIX2090/wms.git"
set "BRANCH=main"
set "SERVICE_NAME=WMS"
set "NSSM_URL=https://nssm.cc/release/nssm-2.24.zip"
set "NSSM_DIR=%INSTALL_DIR%\runtime\nssm"

echo ============================================================
echo WMS 腾讯云一键部署
echo 安装目录: %INSTALL_DIR%
echo 仓库: %REPO_URL%
echo 分支: %BRANCH%
echo 服务名: %SERVICE_NAME%
echo ============================================================
echo.

REM ---- 权限检查 ----
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 需要管理员权限运行本脚本。
    echo        请右键 → 以管理员身份运行。
    pause
    exit /b 1
)

REM ---- 步骤 1: Git 检查 ----
echo [1/4] 检查 Git...
where git.exe >nul 2>nul
if not errorlevel 1 (
    echo       Git 可用。
    goto :git_ready
)

echo       Git 未安装，开始静默安装...
set "GIT_VER=2.47.1"
set "GIT_INSTALLER=%TEMP%\Git-%GIT_VER%-64-bit.exe"
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v%GIT_VER%.windows.1/Git-%GIT_VER%-64-bit.exe"

REM 下载 Git 安装包
if not exist "%GIT_INSTALLER%" (
    echo        下载 Git for Windows %GIT_VER% ...
    powershell -NoProfile -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%GIT_URL%' -OutFile '%GIT_INSTALLER%' -UseBasicParsing }" ^
        "catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo [ERROR] Git 下载失败。
        echo        请手动安装 Git for Windows 后重试。
        pause
        exit /b 1
    )
)

REM 静默安装（/VERYSILENT 不弹窗，/NORESTART 不重启，/NOCANCEL 不可取消）
echo        静默安装 Git...
"%GIT_INSTALLER%" /VERYSILENT /NORESTART /NOCANCEL /SP-
if errorlevel 1 (
    echo [ERROR] Git 安装失败。
    echo        请手动安装 Git for Windows 后重试。
    pause
    exit /b 1
)

REM 刷新当前会话 PATH，让 git.exe 立即可用（默认装到 C:\Program Files\Git）
set "PATH=%ProgramFiles%\Git\cmd;%ProgramFiles(x86)%\Git\cmd;%PATH%"
where git.exe >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git 安装后仍找不到 git.exe。
    echo        请重新打开 CMD 窗口再运行本脚本。
    pause
    exit /b 1
)
echo       Git 安装完成。

:git_ready

REM AI_TASK: AI-DEPLOY-F01-FIX-03
REM 禁止在脚本或 .git-credentials 中写入明文 PAT。
REM 私有仓库部署前，请由管理员为实际运行 WMS 服务的 Windows 账号
REM 配置 Git Credential Manager；凭据缺失时 clone/fetch 会明确失败。

REM ---- 步骤 2: 克隆或更新仓库 ----
echo [2/4] 克隆/更新仓库...
if exist "%INSTALL_DIR%\.git" (
    echo        仓库已存在，拉取最新代码...
    cd /d "%INSTALL_DIR%"
    git fetch origin %BRANCH%
    git pull --ff-only origin %BRANCH%
    if errorlevel 1 (
        echo [警告] git pull 失败，使用现有代码继续。
    )
) else (
    echo        克隆仓库到 %INSTALL_DIR% ...
    git clone -b %BRANCH% %REPO_URL% "%INSTALL_DIR%"
    if errorlevel 1 (
        echo [ERROR] git clone 失败。
        echo        检查网络或仓库地址: %REPO_URL%
        pause
        exit /b 1
    )
    cd /d "%INSTALL_DIR%"
)
echo       仓库就绪。

REM ---- 步骤 3: 部署绿色版 Python ----
echo [3/4] 部署绿色版 Python 3.11...
call "%INSTALL_DIR%\install_portable_python.bat"
if errorlevel 1 (
    echo [ERROR] 绿色版 Python 部署失败。
    pause
    exit /b 1
)

REM ---- 步骤 4: 注册 Windows 服务 ----
echo [4/4] 注册 Windows 服务...

set "NSSM_EXE=%NSSM_DIR%\win64\nssm.exe"
if not exist "%NSSM_EXE%" (
    echo        nssm 未找到，下载中...
    set "NSSM_ZIP=%INSTALL_DIR%\runtime\nssm-2.24.zip"
    powershell -NoProfile -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%NSSM_URL%' -OutFile '!NSSM_ZIP!' -UseBasicParsing }" ^
        "catch { Write-Host '[ERROR]' $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo [ERROR] nssm 下载失败。
        echo        请手动下载 %NSSM_URL%
        echo        解压到 %NSSM_DIR%
        pause
        exit /b 1
    )
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '!NSSM_ZIP!' -DestinationPath '%NSSM_DIR%' -Force"
)

if not exist "%NSSM_EXE%" (
    echo [ERROR] nssm.exe 未找到: %NSSM_EXE%
    echo        请手动下载 nssm 并解压到该目录。
    pause
    exit /b 1
)

REM 先移除旧服务（如果存在）
"%NSSM_EXE%" status %SERVICE_NAME% >nul 2>&1
if not errorlevel 1 (
    echo        旧服务存在，先停止并移除...
    "%NSSM_EXE%" stop %SERVICE_NAME% >nul 2>&1
    "%NSSM_EXE%" remove %SERVICE_NAME% confirm >nul 2>&1
    timeout /t 2 /nobreak >nul
)

REM 注册新服务
"%NSSM_EXE%" install %SERVICE_NAME% "%INSTALL_DIR%\app\start_wms_auto.bat"
"%NSSM_EXE%" set %SERVICE_NAME% AppDirectory "%INSTALL_DIR%\app"
"%NSSM_EXE%" set %SERVICE_NAME% AppStdout "%INSTALL_DIR%\app\logs\service_stdout.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStderr "%INSTALL_DIR%\app\logs\service_stderr.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateBytes 10485760
"%NSSM_EXE%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM_EXE%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM_EXE%" set %SERVICE_NAME% AppRestartDelay 5000

echo        启动服务...
"%NSSM_EXE%" start %SERVICE_NAME%
timeout /t 5 /nobreak >nul

echo.
echo ============================================================
echo [验证] 服务状态:
"%NSSM_EXE%" status %SERVICE_NAME%
echo.
echo [验证] 本机访问:
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8080/login' -TimeoutSec 10 -UseBasicParsing; Write-Host ('HTTP ' + $r.StatusCode) } catch { Write-Host $_.Exception.Message }"
echo.
echo ============================================================
echo.
echo 部署完成!
echo.
echo 服务管理:
echo   启动: nssm start %SERVICE_NAME%
echo   停止: nssm stop %SERVICE_NAME%
echo   重启: nssm restart %SERVICE_NAME%
echo   状态: nssm status %SERVICE_NAME%
echo.
echo 日志位置:
echo   服务日志: %INSTALL_DIR%\app\logs\service_stdout.log
echo   服务错误: %INSTALL_DIR%\app\logs\service_stderr.log
echo   自动更新: %INSTALL_DIR%\app\logs\auto_update.log
echo.
echo 访问地址:
echo   本机: http://127.0.0.1:8080/login
echo   公网: 配置 Nginx 反代后 https://gd2026.top/login
echo.
echo 自动更新机制（AI-DEPLOY-F01-FIX-02）:
echo   默认关闭。在系统设置 → 运维更新 中打开「启动时自动从 GitHub 更新」后，
echo   再 nssm restart WMS（或重启服务器）才会从 GitHub main 拉取代码。
echo   需要已安装 Git、目录为 git 仓库、已跟踪文件无本地改动、能访问 GitHub。
echo   日志: %INSTALL_DIR%\app\logs\auto_update.log
echo   手动更新: %INSTALL_DIR%\update_from_github.bat
echo.
echo 下一步:
echo   1. 安装 Nginx，配置 HTTPS 反代到 127.0.0.1:8080
echo      模板: %INSTALL_DIR%\app\nginx_wms_server_block.conf
echo   2. 腾讯云安全组放行 443 端口
echo   3. 首次登录后立即修改 admin 密码
echo ============================================================
echo.
pause
exit /b 0
