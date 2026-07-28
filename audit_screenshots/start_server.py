"""Start WMS server directly via app.app:app (the actual Flask app)."""
import os
import sys
import time
import subprocess
import urllib.request

ROOT = r'c:\Users\Administrator\Desktop\wms'
log_dir = os.path.dirname(os.path.abspath(__file__))
stdout_path = os.path.join(log_dir, 'server.out')
stderr_path = os.path.join(log_dir, 'server.err')

# Clear old logs
for p in (stdout_path, stderr_path):
    try:
        with open(p, 'wb') as f:
            f.write(b'')
    except Exception:
        pass

# Build env
env = os.environ.copy()
env['WMS_BOOTSTRAP_PASSWORD'] = 'AAAA1234'
env['PYTHONIOENCODING'] = 'utf-8'
env['PYTHONUTF8'] = '1'
# BUG-F02-FIX: 把项目根目录加到 PYTHONPATH，让 config / app.app 可被 import
# 必须是 wms 根目录，app 子目录不能放进 PYTHONPATH（否则 import app 会冲突）
env['PYTHONPATH'] = ROOT

python_exe = sys.executable
print(f"[*] Using python: {python_exe}")
print(f"[*] Starting WMS server on :8080, logs at {stdout_path}")

# Use start_simple.py logic but as detached subprocess via wrapper script
out = open(stdout_path, 'wb')
err = open(stderr_path, 'wb')

DETACHED_PROCESS = 0x00000008
wrapper_script = os.path.join(log_dir, '_wms_main.py')
proc = subprocess.Popen(
        [python_exe, wrapper_script],
        stdout=out, stderr=err, env=env,
        creationflags=DETACHED_PROCESS,
        cwd=ROOT
    )
print(f"[*] Started PID={proc.pid}")

# Wait for server to come up
for i in range(25):
    time.sleep(1)
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8080/login', timeout=2)
        print(f"[+] Server up: HTTP {r.status} (took {i+1}s)")
        sys.exit(0)
    except Exception as e:
        if i % 3 == 0:
            print(f"  waiting... {e}")

print("[!] Server failed to start in 25s, check server.err")
try:
    with open(stderr_path, 'r', errors='ignore') as f:
        print(f.read()[-2000:])
except Exception as e:
    print(f"[!] cannot read err: {e}")
sys.exit(1)
