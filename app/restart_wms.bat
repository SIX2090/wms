@echo off
setlocal EnableExtensions
call "%~dp0stop_wms.bat"
timeout /t 2 /nobreak >nul
call "%~dp0start.bat"
