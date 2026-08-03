@echo off
setlocal EnableExtensions EnableDelayedExpansion
REM Do not switch code page; some cloud consoles cannot write to CON.

REM ============================================================
REM WMS portable Python 3.11 installer (offline-first)
REM for Windows Server 2012 R2 / 2016 / 2019 / 2022
REM does not pollute system PATH; Python is installed in runtime\Python311
REM
REM common cloud failure cause:
REM   PowerShell Invoke-WebRequest progress bar writing to console reports
REM   "The system cannot write to the specified device."
REM this script prefers local runtime files to avoid online download.
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
echo WMS portable Python %PY_VERSION% installer
echo target directory: %PY_DIR%
echo ============================================================
echo.

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%" 2>nul
if not exist "%RUNTIME_DIR%" (
    echo [ERROR] failed to create directory: %RUNTIME_DIR%
    echo        please check disk space and write permissions.
    pause
    exit /b 1
)

REM write permission test
echo ok> "%RUNTIME_DIR%\.wms_write_test" 2>nul
if not exist "%RUNTIME_DIR%\.wms_write_test" (
    echo [ERROR] failed to write to %RUNTIME_DIR%
    echo        please check directory permissions and disk space.
    pause
    exit /b 1
)
del /q "%RUNTIME_DIR%\.wms_write_test" >nul 2>nul

REM ---- Step 0: already installed ----
if exist "%PY_EXE%" (
    echo [INFO] Python already installed: %PY_EXE%
    echo        To reinstall, delete the directory above and run again.
    goto :check_pip
)

REM ---- Step 1: get embeddable zip (offline-first) ----
:get_embed
if exist "%EMBED_ZIP%" (
    echo [1/5] Found local embeddable zip: %EMBED_ZIP%
    goto :extract
)

echo [1/5] Embeddable zip not found, downloading...
echo        target: %EMBED_ZIP%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue';" ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
    "try { Invoke-WebRequest -Uri '%EMBED_URL%' -OutFile '%EMBED_ZIP%' -UseBasicParsing; exit 0 }" ^
    "catch { Write-Host ('[ERROR] ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo [ERROR] failed to download Python embed zip.
    echo        please download manually and place it at:
    echo          %EMBED_ZIP%
    echo        download URL:
    echo          %EMBED_URL%
    pause
    exit /b 1
)
echo       download completed.

REM ---- Step 2: extract; prefer tar.exe, fallback to Expand-Archive ----
:extract
echo [2/5] Extracting to %PY_DIR% ...
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
    echo [ERROR] extraction failed: python.exe not found.
    echo        zip: %EMBED_ZIP%
    echo        dir: %PY_DIR%
    pause
    exit /b 1
)
echo       extraction completed.

REM ---- Step 3: configure site paths ----
echo [3/5] Configuring site paths ...
set "PTH_FILE=%PY_DIR%\python311._pth"
if not exist "%PTH_FILE%" (
    echo [ERROR] not found %PTH_FILE%
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
echo       python311._pth updated: app and embed directory added to PYTHONPATH.

REM ---- Step 4: install pip ----
:check_pip
if exist "%PY_DIR%\Scripts\pip.exe" (
    echo [4/5] pip already installed.
    goto :install_deps
)

:get_pip
echo [4/5] Installing pip ...
if not exist "%GET_PIP%" (
    echo        get-pip.py not found, downloading...
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ProgressPreference='SilentlyContinue';" ^
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" ^
        "try { Invoke-WebRequest -Uri '%GETPIP_URL%' -OutFile '%GET_PIP%' -UseBasicParsing; exit 0 }" ^
        "catch { Write-Host ('[ERROR] ' + $_.Exception.Message); exit 1 }"
    if errorlevel 1 (
        echo [ERROR] failed to download get-pip.py
        echo        please place it manually: %GET_PIP%
        echo        download URL: %GETPIP_URL%
        pause
        exit /b 1
    )
)
"%PY_EXE%" "%GET_PIP%" --no-warn-script-location
if errorlevel 1 (
    echo [ERROR] pip installation failed.
    pause
    exit /b 1
)
echo       pip installation completed.

REM ---- Step 5: install dependencies ----
:install_deps
echo [5/5] Installing dependencies ...
if not exist "%REQ_FILE%" (
    echo [ERROR] not found %REQ_FILE%
    pause
    exit /b 1
)
if exist "%WHEELHOUSE%" (
    echo        local wheelhouse found, installing offline...
    "%PY_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" --upgrade pip setuptools wheel
    if errorlevel 1 (
        echo [ERROR] offline pip/setuptools/wheel upgrade failed.
        pause
        exit /b 1
    )
    "%PY_EXE%" -m pip install --no-index --find-links "%WHEELHOUSE%" -r "%REQ_FILE%"
) else (
    echo        no wheelhouse found, installing from PyPI...
    "%PY_EXE%" -m pip install --upgrade pip setuptools wheel
    "%PY_EXE%" -m pip install -r "%REQ_FILE%"
)
if errorlevel 1 (
    echo [ERROR] dependency installation failed.
    pause
    exit /b 1
)
echo       dependency installation completed.

echo.
echo ============================================================
echo [INFO] Python version:
"%PY_EXE%" --version
echo [INFO] Core packages:
"%PY_EXE%" -c "import flask, sqlalchemy, waitress; print('flask', flask.__version__); print('sqlalchemy', sqlalchemy.__version__); print('waitress OK')"
if errorlevel 1 (
    echo [ERROR] package check failed.
    pause
    exit /b 1
)
echo ============================================================
echo.
echo Portable Python installation completed:
echo   Python: %PY_EXE%
echo.
echo Next steps:
echo   cd app
echo   start_wms_offline.bat
echo.
pause
exit /b 0
