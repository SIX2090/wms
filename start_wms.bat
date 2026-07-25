@echo off
setlocal EnableExtensions
cd /d "%~dp0app" || exit /b 1
call "%~dp0app\start_wms_offline.bat" %*
exit /b %ERRORLEVEL%
