@echo off
setlocal EnableExtensions
REM 部分腾讯云控制台对 chcp 65001 会写设备失败，这里不强制切代码页
set "PYTHONUTF8=1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_portable_dist.ps1" %*
exit /b %ERRORLEVEL%
