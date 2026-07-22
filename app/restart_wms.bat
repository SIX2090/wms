@echo off
setlocal EnableExtensions
chcp 65001 >nul
echo Stopping WMS...
call "%~dp0stop_wms_offline.bat"
timeout /t 2 /nobreak >nul
echo Starting WMS...
call "%~dp0start_wms_offline.bat"
