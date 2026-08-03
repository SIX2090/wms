@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Do not switch code page; some cloud consoles cannot write to CON.

REM ============================================================
REM WMS 绿色版 Python 3.11 部署脚本（离线优先）
REM 适用于 Windows Server 2012 R2 / 2016 / 2019 / 2022
REM 不污染系统 PATH，Python 装在 runtime\Python311
REM
REM 云上常见失败原因：
REM   PowerShell Invoke-WebRequest 进度条写控制台时报
REM   "The system cannot write to the specified device."
REM 本脚本优先使用本地 runtime 文件，避免在线下载。
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

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" 2>nul
if not exist "%RUNTIME_DIR%" (
    echo [ERROR] 无法创建目录: %RUNTIME_DIR%
    echo        请检查磁盘空间和写入权限。
    pause
    exit /b 1
)

REM 写盘自检
echo ok> "%RUNTIME_DIR%\.wms_write_test" 2>nul
if not exist "%RUNTIME_DIR%\.wms_write_test" (
    echo [ERROR] 无法写入 %RUNTIME_DIR%
    echo        请检查磁盘是否已满、是否只读、是否有权限。
    pause
    exit /b 1
)
del /q "%RUNTIME_DIR%\.wms_write_test" >nul 2>nul

REM ---- 步骤 0: 幂等检查 ----
if exist "%PY_EXE%" (
    echo [跳过] Python 已存在于 %PY_EXE%
    echo        如需重装，请先删除该目录。
    goto :check_pip
)

REM ---- 步骤 1: 获取 embeddable zip（离线优先）----
:get_embed
if exist "%EMBED_ZIP%" (
    echo [1/5] 使用本地 embeddable zip: %EMBED_ZIP%
    goto :extract
)

echo [1/5] 本地无 embeddable zip，尝试下载...
echo        目标: %EMBED_ZIP%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue';" ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
    "try { Invoke-WebRequest -Uri '%EMBED_URL%' -OutFile '%EMBED_ZIP%' -UseBasicParsing; exit 0 }" ^
    "catch { Write-Host ('[ERROR] ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo [ERROR] 无法获取 python embed 包。
    echo        请把下面文件放到本机后重跑:
    echo          %EMBED_ZIP%
    echo        下载地址:
    echo          %EMBED_URL%
    pause
    exit /b 1
)
echo       下载完成。

REM ---- 步骤 2: 解压（优先 tar，避免 Expand-Archive 控制台问题）----
:extract
echo [2/5] 解压到 %PY_DIR% ...
if exist "%PY_DIR%" rmdir /s /q "%PY_DIR%" 2>nul
mkdir "%PY_DIR%" 2>nul

where tar.exe >nul 2>nul
if not errorlevel 1 (
    tar -xf "%EMBED_ZIP%" -C "%PY_DIR%"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ProgressPreference='SilentlyContinue';" ^
        "Expand-Archive -LiteralPath '%EMBED_ZIP%' -DestinationPath '%PY_DIR%' -Force"
)
if not exist "%PY_EXE%" (
    echo [ERROR] 解压后找不到 python.exe
    echo        zip: %EMBED_ZIP%
    echo        dir: %PY_DIR%
    pause
    exit /b 1
)
echo       解压完成。

REM ---- 步骤 3: 启用 site 模块 ----
echo [3/5] 启用 site 模块 ...
set "PTH_FILE=%PY_DIR%\python311._pth"
if not exist "%PTH_FILE%" (
    echo [ERROR] 未找到 %PTH_FILE%
    pause
    exit /b 1
)
> "%PTH_FILE%" echo python311.zip
>> "%PTH_FILE%" echo .
>> "%PTH_FILE%" echo Lib\site-packages
>> "%PTH_FILE%" echo ..\..\app
>> "%PTH_FILE%" echo.
>> "%PTH_FILE%" echo # Uncomment to run site.main() automatically
>> "%PTH_FILE%" echo import site
echo       python311._pth 已修改（含 app 路径，embed 模式不读 PYTHONPATH）。

REM ---- 步骤 4: 安装 pip ----
:check_pip
if exist "%PY_DIR%\Scripts\pip.exe" (
    echo [4/5] pip 已安装，跳过。
    goto :install_deps
)

:get_pip
echo [4/5] 安装 pip ...
if not exist "%GET_PIP%" (
    echo        本地无 get-pip.py，尝试下载...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%GET_PIP%' -UseBasicParsing; exit 0 }" ^
        "catch { Write-Host ('[ERROR] ' + $_.Exception.Message); exit 1 }"
    if errorlevel 1 (
        echo [ERROR] 无法获取 get-pip.py
        echo        请把文件放到: %GET_PIP%
        echo        下载地址: %GETPIP_URL%
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
    pause
    exit /b 1
)
if exist "%WHEELHOUSE%" (
    echo        使用本地 wheelhouse 离线安装...
    "%PY_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" --upgrade pip setuptools wheel
    if errorlevel 1 (
        echo [ERROR] 升级 pip/setuptools/wheel 失败。
        pause
        exit /b 1
    )
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

echo.
echo ============================================================
echo [验证] Python 版本:
"%PY_EXE%" --version
echo [验证] 关键依赖:
"%PY_EXE%" -c "import flask, sqlalchemy, waitress; print('flask', flask.__version__); print('sqlalchemy', sqlalchemy.__version__); print('waitress OK')"
if errorlevel 1 (
    echo [ERROR] 依赖验证失败。
    pause
    exit /b 1
)
echo ============================================================
echo.
echo 绿色版 Python 部署完成:
echo   Python: %PY_EXE%
echo.
echo 下一步:
echo   cd app
echo   start_wms_offline.bat
echo.
pause
exit /b 0
