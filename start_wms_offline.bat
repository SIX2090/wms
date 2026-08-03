@echo off
REM Fix PATH for Tencent Cloud Windows Server where System32 is sometimes missing.
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0;%PATH%"
call "%~dp0app\start_wms_offline.bat" %*
exit /b %ERRORLEVEL%
