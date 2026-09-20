@echo off
chcp 65001 >nul
echo ============================================
echo   WMS 数据库修复：盘点域缺列补齐
echo   BUG-2026-09-05-001 物料编辑 500
echo   no such column: inventory_check_item.counted_by
echo ============================================
echo.

set "DB_PATH=c:\wms\app\instance\inventory.db"
set "PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe"

if not exist "%PYTHON%" (
    echo [ERROR] Python 不存在: %PYTHON%
    echo         请修改本脚本中的 PYTHON 变量为你的 python.exe 路径
    pause
    exit /b 1
)

if exist "%DB_PATH%" (
    echo [INFO] 数据库: %DB_PATH%
    "%PYTHON%" "%~dp0app\fix_inventory_check_columns.py" "%DB_PATH%"
) else (
    echo [WARN] 默认数据库不存在: %DB_PATH%
    echo        尝试自动定位...
    "%PYTHON%" "%~dp0app\fix_inventory_check_columns.py"
)

echo.
echo ============================================
echo   完成！请重启 WMS 服务后再试编辑物料。
echo ============================================
pause
