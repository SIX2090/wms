from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
LOG_DIR = APP_DIR / "logs"


def main() -> int:
    os.chdir(APP_DIR)
    LOG_DIR.mkdir(exist_ok=True)

    print("Restarting WMS safely.")
    print("This script does not delete any database files.")

    stop_script = APP_DIR / "stop_wms.bat"
    if stop_script.exists():
        subprocess.run(["cmd", "/c", str(stop_script)], cwd=APP_DIR, check=False)

    env = os.environ.copy()
    env["FLASK_ENV"] = "production"
    env["PYTHONUTF8"] = "1"

    stdout = open(LOG_DIR / "service_stdout.log", "ab", buffering=0)
    stderr = open(LOG_DIR / "service_stderr.log", "ab", buffering=0)
    subprocess.Popen(
        [sys.executable, str(APP_DIR / "run_server.py")],
        cwd=APP_DIR,
        env=env,
        stdout=stdout,
        stderr=stderr,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    for _ in range(15):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/login", timeout=5) as response:
                if response.status == 200:
                    print("WMS is running: http://127.0.0.1:8080/login")
                    return 0
        except Exception:
            time.sleep(2)

    print("WMS did not respond on http://127.0.0.1:8080/login.")
    print(r"Check logs\service_stdout.log and logs\service_stderr.log.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
