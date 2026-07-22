@echo off
REM AI-DEPLOY-F01: 自启动更新已内置到 run_server.py，本脚本保留向后兼容
REM （用户可能已建立指向 start_wms_auto.bat 的桌面快捷方式）。
REM 直接委托给 start_wms_offline.bat，由 run_server.py 在启动时执行一次 auto_update.py。
call "%~dp0start_wms_offline.bat" %*
exit /b %ERRORLEVEL%
