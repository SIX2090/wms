@echo off
call "%~dp0stop_wms_offline.bat" %*
exit /b %ERRORLEVEL%
