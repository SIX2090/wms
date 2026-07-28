"""Start WMS server for browser bug-hunting session."""
import os
import sys
import time
import subprocess
import urllib.request

ROOT = '/workspace'
APP = os.path.join(ROOT, 'app')
os.chdir(ROOT)
sys.path.insert(0, APP)
sys.path.insert(0, ROOT)
os.environ['WMS_BOOTSTRAP_PASSWORD'] = os.environ.get('WMS_BOOTSTRAP_PASSWORD', 'admin')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'
os.environ['WMS_SKIP_AUTO_UPDATE'] = '1'

from waitress import serve
import app as _app_module
serve(_app_module.app, host='0.0.0.0', port=8080, threads=8, ident='WMS-BUGHUNT')
