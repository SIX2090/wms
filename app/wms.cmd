@echo off
REM A12: app\install.bat never existed; the only supported installer is the repo-root install.bat.
if not exist "%~dp0..\install.bat" (
    echo [ERROR] install.bat not found: "%~dp0..\install.bat"
    exit /b 1
)
call "%~dp0..\install.bat" %*
exit /b %ERRORLEVEL%
