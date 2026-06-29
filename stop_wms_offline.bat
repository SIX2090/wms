@echo off
call "%~dp0app\stop_wms_offline.bat" %*
exit /b %ERRORLEVEL%
