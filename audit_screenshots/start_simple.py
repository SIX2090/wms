"""Start WMS server directly via app.app:app"""
import os
import sys

ROOT = r'c:\Users\Administrator\Desktop\wms'
os.chdir(ROOT)
# wms 根目录必须能 import config 和 ai
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'app'))
os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'AAAA1234'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

from waitress import serve
import app as wms_app  # noqa: E402

print('[*] starting WMS on :8080', flush=True)
serve(wms_app.app, host='0.0.0.0', port=8080, threads=8, ident='WMS-BUGFIX')
