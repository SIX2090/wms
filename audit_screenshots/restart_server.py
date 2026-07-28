#!/usr/bin/env python
"""Restart the WMS server to pick up CSS/JS/Python changes - pure Python approach."""
import os
import sys
import time
import subprocess
import ctypes
import signal

# Kill existing python processes by name (the WMS server processes, not us)
print("[*] Killing any existing WMS python processes...")
try:
    output = subprocess.check_output(
        ['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE ne python*'],
        stderr=subprocess.STDOUT, timeout=20
    ).decode('utf-8', errors='ignore')
    print(output)
except subprocess.CalledProcessError as e:
    print(f"[!] taskkill rc={e.returncode}: {e.output.decode('utf-8', errors='ignore')[:500]}")
except Exception as e:
    print(f"[!] PowerShell kill failed: {e}")

time.sleep(2)

# Start new server using app.app:app (the actual Flask app in this repo)
env = os.environ.copy()
env['WMS_BOOTSTRAP_PASSWORD'] = 'AAAA1234'
env['PYTHONIOENCODING'] = 'utf-8'
env['PYTHONUTF8'] = '1'
# BUG-F02-FIX: 把项目根目录加到 PYTHONPATH
env['PYTHONPATH'] = ROOT

log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
stdout_path = os.path.join(log_dir, 'server.out')
stderr_path = os.path.join(log_dir, 'server.err')

print(f"[*] Starting new WMS server on :8080, logs at {stdout_path}")
with open(stdout_path, 'wb') as out, open(stderr_path, 'wb') as err:
    proc = subprocess.Popen(
        [sys.executable, os.path.join(log_dir, '_wms_main.py')],
        stdout=out, stderr=err, env=env,
        creationflags=0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    )
    print(f"[*] Started PID={proc.pid}")

time.sleep(5)
# Verify it's running
try:
    out2 = subprocess.check_output(
        ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
        stderr=subprocess.STDOUT, timeout=10
    ).decode('utf-8', errors='ignore')
    print("[*] tasklist output:")
    print(out2)
except Exception as e:
    print(f"[!] verify failed: {e}")

# Quick health check
try:
    import urllib.request
    time.sleep(2)
    r = urllib.request.urlopen('http://127.0.0.1:8080/login', timeout=5)
    print(f"[*] Health: HTTP {r.status}")
except Exception as e:
    print(f"[!] Health failed: {e}")

print("[*] Done.")
