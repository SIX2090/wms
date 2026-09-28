@echo off
REM ============================================================
REM  WMS nginx 重启脚本（先停后起 + 健康检查）
REM  用法：双击运行，或在命令行执行  restart_nginx.bat
REM  说明：nginx 位于 C:\nginx，配置见 app\nginx_wms_server_block.conf
REM        公网 HTTPS 443 -> 反代本机 WMS 127.0.0.1:8080
REM ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

REM ---- 修正 PATH：腾讯云 Windows Server 有时缺 System32 ----
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"

set "NGINX_DIR=C:\nginx"
set "NGINX_EXE=%NGINX_DIR%\nginx.exe"

echo.
echo ============================================================
echo   WMS nginx 重启
echo ============================================================

REM ---------- 0. 前置检查：nginx.exe 是否存在 ----------
if not exist "%NGINX_EXE%" (
    echo [错误] 找不到 nginx.exe：%NGINX_EXE%
    echo        请确认 nginx 装在 %NGINX_DIR%，或用记事本改本脚本的 NGINX_DIR。
    echo.
    pause
    exit /b 1
)

REM ============================================================
REM  第 1 步：先自检配置（必须在停旧进程之前！）
REM ============================================================
REM 顺序很重要：如果先停旧进程再发现配置有错，你的网站就断在那里了。
REM 先检查配置，不通过就直接退出，旧进程原封不动继续服务。
echo.
echo [1/4] 检查 nginx 配置 ...

pushd "%NGINX_DIR%"
"%NGINX_EXE%" -t >nul 2>&1
if errorlevel 1 (
    echo [错误] nginx 配置检查未通过，已中止（旧的 nginx 保持运行，网站不受影响）。
    echo        下面是具体错误信息：
    echo ------------------------------------------------------------
    "%NGINX_EXE%" -t
    echo ------------------------------------------------------------
    popd
    echo.
    pause
    exit /b 1
)
popd
echo       配置检查通过。

REM ============================================================
REM  第 2 步：停止 nginx
REM ============================================================
echo.
echo [2/4] 停止 nginx ...

REM 先看是否在运行
tasklist /FI "IMAGENAME eq nginx.exe" 2>nul | find /I "nginx.exe" >nul
if errorlevel 1 (
    echo       未发现正在运行的 nginx.exe，跳过停止。
    goto :START
)

REM --- 2a. 优先优雅停止（做完手头的请求、写完日志）---
pushd "%NGINX_DIR%"
"%NGINX_EXE%" -s quit >nul 2>&1
popd

REM --- 2b. 等待进程真正退出（最多 10 秒）---
REM 这一步是必须的：nginx 退出需要时间腾出 443/80 端口。
REM 不等就启动，会撞上「端口被占用」，表现为新进程起不来。
set /a _WAIT=0
:WAIT_QUIT
tasklist /FI "IMAGENAME eq nginx.exe" 2>nul | find /I "nginx.exe" >nul
if errorlevel 1 (
    echo       已优雅退出（等待 !_WAIT! 秒）。
    goto :START
)
set /a _WAIT+=1
if !_WAIT! GEQ 10 goto :FORCE_KILL
timeout /t 1 /nobreak >nul
goto :WAIT_QUIT

:FORCE_KILL
echo       优雅停止超时（10 秒），强制结束进程 ...
taskkill /F /IM nginx.exe >nul 2>&1

REM 强杀后再等一次，确认真的没了
set /a _WAIT2=0
:WAIT_KILL
tasklist /FI "IMAGENAME eq nginx.exe" 2>nul | find /I "nginx.exe" >nul
if errorlevel 1 (
    echo       已强制结束。
    goto :START
)
set /a _WAIT2+=1
if !_WAIT2! GEQ 10 (
    echo.
    echo [错误] nginx.exe 无法结束，可能被其他程序占用或权限不足。
    echo        请用「管理员身份运行」重试，或手动在任务管理器里结束 nginx.exe。
    echo.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :WAIT_KILL

REM ============================================================
REM  第 3 步：启动 nginx
REM ============================================================
REM 走到这里说明配置已检查通过（第 1 步），且旧进程已停干净（第 2 步）。
:START
echo.
echo [3/4] 启动 nginx ...

REM 启动（用 start 让 nginx 脱离本窗口独立运行，
REM 否则关掉本窗口 nginx 也会被带走）
pushd "%NGINX_DIR%"
start "" /B "%NGINX_EXE%"
popd

REM ============================================================
REM  第 4 步：健康检查
REM ============================================================
echo.
echo [4/4] 健康检查 ...

REM 等 2 秒给 nginx 起来的时间
timeout /t 2 /nobreak >nul

tasklist /FI "IMAGENAME eq nginx.exe" 2>nul | find /I "nginx.exe" >nul
if errorlevel 1 (
    echo.
    echo [失败] nginx 未能启动，进程不存在。
    echo        常见原因：
    echo          1. 443 端口被别的程序占用（IIS / 其他 web 服务）
    echo          2. 证书 server.pem / server.key 路径不对
    echo          3. 配置检查虽通过但运行时出错
    echo        排查：在 %NGINX_DIR% 下执行  nginx.exe -t  看报错，
    echo              并查看 logs\error.log 最后几行。
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   成功：nginx 已重启
echo ============================================================
echo   进程状态：
for /f "tokens=*" %%i in ('tasklist /FI "IMAGENAME eq nginx.exe" /FO TABLE /NH 2^>nul') do (
    echo     %%i
)
echo.
echo   监听端口（443 = 公网 HTTPS，8080 = 本机 WMS）：
netstat -ano | findstr ":443 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo     [!] 443 端口未见监听 —— nginx 可能刚起来还没绑定，或证书加载失败。
) else (
    netstat -ano | findstr ":443 " | findstr "LISTENING"
)
netstat -ano | findstr ":8080 " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo     [!] 8080 未见监听 —— 请确认 WMS 服务（start_wms_offline.bat）也在运行。
) else (
    netstat -ano | findstr ":8080 " | findstr "LISTENING"
)
echo.
echo   访问地址： https://gd2026.top
echo   日志目录： %NGINX_DIR%\logs\
echo ============================================================
echo.
pause
endlocal
exit /b 0
