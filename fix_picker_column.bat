@echo off
chcp 65001 >nul
echo ============================================
echo   WMS 数据库修复：添加 picker 列
echo ============================================
echo.

set "DB_PATH=c:\wms\app\instance\inventory.db"

if not exist "%DB_PATH%" (
    echo [ERROR] 数据库文件不存在: %DB_PATH%
    echo 请确认 WMS 安装目录为 c:\wms
    pause
    exit /b 1
)

echo [INFO] 数据库: %DB_PATH%
echo.

python -c "import sqlite3; conn=sqlite3.connect(r'%DB_PATH%'); cols=[r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]; print('[INFO] out_order 现有列:', cols); conn.close()"
echo.

python -c "import sqlite3; conn=sqlite3.connect(r'%DB_PATH%'); cols=[r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]; (conn.execute('ALTER TABLE out_order ADD COLUMN picker VARCHAR(50)') or True) and conn.commit() and print('[OK] 已添加 out_order.picker') if 'picker' not in cols else print('[OK] out_order.picker 已存在'); conn.close()"

python -c "import sqlite3; conn=sqlite3.connect(r'%DB_PATH%'); cols=[r[1] for r in conn.execute('PRAGMA table_info(production_requisition)').fetchall()]; (conn.execute('ALTER TABLE production_requisition ADD COLUMN picker VARCHAR(50)') or True) and conn.commit() and print('[OK] 已添加 production_requisition.picker') if 'picker' not in cols else print('[OK] production_requisition.picker 已存在'); conn.close()"

echo.
echo ============================================
echo   修复完成！请重启 WMS 服务。
echo ============================================
pause
