"""Start WMS server in background with proper PYTHONPATH."""
import os
import sys
import subprocess

ROOT = r"C:\Users\Administrator\Desktop\wms"
APP = r"C:\Users\Administrator\Desktop\wms\app"

os.chdir(APP)
os.environ["WMS_SKIP_AUTO_UPDATE"] = "1"
os.environ["PYTHONPATH"] = APP + os.pathsep + ROOT

LOG = r"C:\Users\Administrator\Desktop\wms\audit_screenshots\server.log"
ERR = r"C:\Users\Administrator\Desktop\wms\audit_screenshots\server.err"

with open(LOG, "ab") as out, open(ERR, "ab") as err:
    p = subprocess.Popen(
        [sys.executable, "-m", "waitress", "--host=0.0.0.0", "--port=8080", "--threads=8", "app:app"],
        stdout=out, stderr=err, cwd=APP,
        env={**os.environ}
    )
print("Started PID", p.pid)
