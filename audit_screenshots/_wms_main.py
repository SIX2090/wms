"""Start WMS server - main entry, using direct sys.path injection."""
import os
import sys
import time

ROOT = r'c:\Users\Administrator\Desktop\wms'
APP = os.path.join(ROOT, 'app')
os.chdir(ROOT)
# BUG-F02-FIX: 配置 sys.path 让 config / app 都能 import
sys.path.insert(0, APP)  # for `import config`
sys.path.insert(0, ROOT)  # for `import app` (treats app as a module)
os.environ['WMS_BOOTSTRAP_PASSWORD'] = os.environ.get('WMS_BOOTSTRAP_PASSWORD', 'AAAA1234')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

print('[*] starting WMS on :8080', flush=True)
from waitress import serve
import app as _app_module  # 这个 app 是 ROOT/app/ 目录，被当作 module
serve(_app_module.app, host='0.0.0.0', port=8080, threads=8, ident='WMS-BUGFIX')
