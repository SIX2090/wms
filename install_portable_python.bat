@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ============================================================
REM WMS 绿色版 Python 3.11 部署脚本
REM 适用于 Windows Server 2012 R2 / 2016 / 2019 / 2022
REM 不污染系统 PATH，Python 装在 runtime\Python311
REM ============================================================

set "ROOT_DIR=%~dp0"
set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "RUNTIME_DIR=%ROOT_DIR%\runtime"
set "PY_DIR=%RUNTIME_DIR%\Python311"
set "PY_EXE=%PY_DIR%\python.exe"
set "PY_VERSION=3.11.9"
set "EMBED_ZIP=%RUNTIME_DIR%\python-%PY_VERSION%-embed-amd64.zip"
set "GET_PIP=%RUNTIME_DIR%\get-pip.py"
set "EMBED_URL=https://www.python.org/ftp/python/%PY_VERSION%/python-%PY_VERSION%-embed-amd64.zip"
set "GETPIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "WHEELHOUSE=%ROOT_DIR%\wheelhouse"
set "REQ_FILE=%ROOT_DIR%\app\requirements.txt"

echo ============================================================
echo WMS 绿色版 Python %PY_VERSION% 部署
echo 目标目录: %PY_DIR%
echo ============================================================
echo.

REM ---- 步骤 0: 幂等检查 ----
if exist "%PY_EXE%" (
    echo [跳过] Python 已存在于 %PY_EXE%
    echo        如需重装，请先删除该目录。
    goto :check_pip
)

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%"

REM ---- 步骤 1: 获取 embeddable zip ----
:get_embed
if exist "%EMBED_ZIP%" (
    echo [1/5] 使用本地 embeddable zip: %EMBED_ZIP%
) else (
    echo [1/5] 本地无 embeddable zip，从 python.org 下载...
    powershell -NoProfile -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%EMBED_URL%' -OutFile '%EMBED_ZIP%' -UseBasicParsing }" ^
        "catch { Write-Host '[ERROR] 下载失败:' $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo [ERROR] 无法下载 embeddable zip。
        echo        请手动下载 %EMBED_URL%
        echo        放到 %EMBED_ZIP%
        echo        然后重新运行本脚本。
        pause
        exit /b 1
    )
    echo       下载完成。
)

REM ---- 步骤 2: 解压 ----
echo [2/5] 解压到 %PY_DIR% ...
if exist "%PY_DIR%" rmdir /s /q "%PY_DIR%"
mkdir "%PY_DIR%"
powershell -NoProfile -Command "Expand-Archive -LiteralPath '%EMBED_ZIP%' -DestinationPath '%PY_DIR%' -Force"
if not exist "%PY_EXE%" (
    echo [ERROR] 解压后找不到 python.exe
    pause
    exit /b 1
)
echo       解压完成。

REM ---- 步骤 3: 启用 site 模块（embeddable 默认禁用，否则 pip 无法工作）----
echo [3/5] 启用 site 模块 ...
set "PTH_FILE=%PY_DIR%\python311._pth"
if not exist "%PTH_FILE%" (
    echo [ERROR] 未找到 %PTH_FILE%
    pause
    exit /b 1
)
powershell -NoProfile -Command ^
    "$c = Get-Content -LiteralPath '%PTH_FILE%';" ^
    "$c = $c -replace '^#import site','import site';" ^
    "Set-Content -LiteralPath '%PTH_FILE%' -Value $c -Encoding ASCII"
echo       python311._pth 已修改（取消注释 import site）。

REM ---- 步骤 4: 安装 pip ----
:check_pip
if exist "%PY_DIR%\Scripts\pip.exe" (
    echo [4/5] pip 已安装，跳过。
    goto :install_deps
)

:get_pip
echo [4/5] 安装 pip ...
if not exist "%GET_PIP%" (
    echo        本地无 get-pip.py，从 bootstrap.pypa.io 下载...
    powershell -NoProfile -Command ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%GET_PIP%' -UseBasicParsing }" ^
        "catch { Write-Host '[ERROR] 下载失败:' $_.Exception.Message; exit 1 }"
    if errorlevel 1 (
        echo [ERROR] 无法下载 get-pip.py。
        echo        请手动下载 %GETPIP_URL%
        echo        放到 %GET_PIP%
        echo        然后重新运行本脚本。
        pause
        exit /b 1
    )
)
"%PY_EXE%" "%GET_PIP%" --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] pip 安装失败。
    pause
    exit /b 1
)
echo       pip 安装完成。

REM ---- 步骤 5: 安装项目依赖 ----
:install_deps
echo [5/5] 安装项目依赖 ...
if not exist "%REQ_FILE%" (
    echo [ERROR] 未找到 %REQ_FILE%
    echo        请确认在 WMS 根目录运行本脚本。
    pause
    exit /b 1
)
if exist "%WHEELHOUSE%" (
    echo        使用本地 wheelhouse 离线安装...
    "%PY_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" --upgrade pip setuptools wheel
    "%PY_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" -r "%REQ_FILE%"
) else (
    echo        无 wheelhouse，从 PyPI 在线安装...
    "%PY_EXE%" -m pip install --upgrade pip setuptools wheel
    "%PY_EXE%" -m pip install -r "%REQ_FILE%"
)
if errorlevel 1 (
    echo [ERROR] 依赖安装失败。
    pause
    exit /b 1
)
echo       依赖安装完成。

REM ---- 验证 ----
echo.
echo ============================================================
echo [验证] Python 版本:
"%PY_EXE%" --version
echo [验证] 关键依赖:
"%PY_EXE%" -c "import flask, sqlalchemy, waitress; print('flask', flask.__version__); print('sqlalchemy', sqlalchemy.__version__); print('waitress OK')"
echo ============================================================
echo.
echo 绿色版 Python 部署完成:
echo   Python: %PY_EXE%
echo   不在系统 PATH 中，WMS 启动脚本会自动找到它。
echo.
echo 下一步:
echo   1. 设置环境变量（见 deploy_cloud.bat 提示）
echo   2. 运行 start_wms_auto.bat 启动 WMS
echo   3. 用 nssm 注册为 Windows 服务实现开机自启
echo.
pause
exit /b 0
