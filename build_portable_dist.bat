@echo off
setlocal EnableExtensions
set "PYTHONUTF8=1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_portable_dist.ps1" %*
exit /b %ERRORLEVEL%
