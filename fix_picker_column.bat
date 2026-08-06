@echo off
chcp 65001 >nul
echo ===== 修复 out_order / production_requisition 缺 picker 列 =====
echo.

cd /d "%~dp0"

python -c "
import sqlite3, os, sys

# 自动查找数据库
candidates = [
    os.path.join(os.path.dirname(__file__) if '__file__' in dir() else '.', 'app', 'instance', 'inventory.db'),
    os.path.join(os.environ.get('USERPROFILE',''), 'AppData', 'Local', 'Programs', 'Python', 'Python311', 'Scripts', 'instance', 'inventory.db'),
    r'C:\workspace\app\instance\inventory.db',
]

db_path = None
for c in candidates:
    if os.path.exists(c):
        db_path = c
        break

if not db_path:
    # 尝试从 Flask config 读取
    try:
        sys.path.insert(0, os.path.join(os.getcwd(), 'app'))
        from config import config_dict
        uri = config_dict.get('default').SQLALCHEMY_DATABASE_URI
        if uri and uri.startswith('sqlite:///'):
            p = uri.replace('sqlite:///', '')
            if not os.path.isabs(p):
                p = os.path.join(os.getcwd(), 'app', 'instance', p)
            if os.path.exists(p):
                db_path = p
    except:
        pass

if not db_path:
    print('[ERROR] 找不到 inventory.db，请手动指定路径')
    input('按回车退出...')
    sys.exit(1)

print('[OK] 数据库:', db_path)
conn = sqlite3.connect(db_path)

for tbl in ['out_order', 'production_requisition']:
    cols = [r[1] for r in conn.execute('PRAGMA table_info(%s)' % tbl).fetchall()]
    if 'picker' not in cols:
        conn.execute('ALTER TABLE %s ADD COLUMN picker VARCHAR(50)' % tbl)
        conn.commit()
        print('[OK] 已添加 %s.picker' % tbl)
    else:
        print('[OK] %s.picker 已存在，跳过' % tbl)

conn.close()
print()
print('===== 修复完成，请重启 WMS 服务 =====')
input('按回车退出...')
"