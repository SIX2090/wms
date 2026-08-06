@echo off
chcp 65001 >nul
echo ============================================
echo   WMS 数据库修复：添加 picker 列
echo ============================================
echo.

set "DB_PATH=c:\wms\app\instance\inventory.db"

if not exist "%DB_PATH%" (
    echo [ERROR] 数据库文件不存在: %DB_PATH%
    pause
    exit /b 1
)

echo [INFO] 数据库: %DB_PATH%
echo.

python "%~dp0_fix_picker_helper.py" "%DB_PATH%"

echo.
echo ============================================
echo   修复完成！请重启 WMS 服务。
echo ============================================
pause
