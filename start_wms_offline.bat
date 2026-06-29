@echo off
call "%~dp0app\start_wms_offline.bat" %*
exit /b %ERRORLEVEL%
