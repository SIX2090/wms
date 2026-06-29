@echo off
setlocal EnableExtensions
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build_portable_dist.ps1" %*
exit /b %ERRORLEVEL%
