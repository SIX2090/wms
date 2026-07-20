from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent
LOG_DIR = APP_DIR / "logs"

# 默认监听端口与登录页路径；可通过环境变量 WMS_PORT / WMS_LOGIN_PATH 覆盖。
DEFAULT_PORT = int(os.environ.get("WMS_PORT", "8080") or "8080")
DEFAULT_LOGIN_PATH = os.environ.get("WMS_LOGIN_PATH", "/login") or "/login"


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
    # 仅在操作员未显式设置时，才为本地离线启动场景允许自动 SECRET_KEY；
    # 生产部署必须显式设置 SECRET_KEY（或显式设 WMS_ALLOW_AUTO_SECRET_KEY=0 关闭）。
    if "WMS_ALLOW_AUTO_SECRET_KEY" not in env:
        env["WMS_ALLOW_AUTO_SECRET_KEY"] = "1"
        print(
            "WARNING: WMS_ALLOW_AUTO_SECRET_KEY 未显式配置，已默认开启自动 SECRET_KEY 用于本地离线启动。"
            " 生产部署请显式设置 SECRET_KEY 或将 WMS_ALLOW_AUTO_SECRET_KEY=0 关闭。"
        )

    port = int(os.environ.get("WMS_PORT", str(DEFAULT_PORT)) or DEFAULT_PORT)
    login_path = os.environ.get("WMS_LOGIN_PATH", DEFAULT_LOGIN_PATH) or DEFAULT_LOGIN_PATH
    if not login_path.startswith("/"):
        login_path = "/" + login_path
    health_url = f"http://127.0.0.1:{port}{login_path}"

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
            with urllib.request.urlopen(health_url, timeout=5) as response:
                if response.status == 200:
                    print(f"WMS is running: {health_url}")
                    return 0
        except Exception:
            time.sleep(2)

    print(f"WMS did not respond on {health_url}.")
    print(r"Check logs\service_stdout.log and logs\service_stderr.log.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
