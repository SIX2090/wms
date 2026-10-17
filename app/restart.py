from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from service_control import owns_port, stop_verified_server


APP_DIR = Path(__file__).resolve().parent
LOG_DIR = APP_DIR / "logs"

# 默认监听端口与登录页路径；可通过环境变量 WMS_PORT / WMS_LOGIN_PATH 覆盖。
DEFAULT_PORT = 8080
DEFAULT_LOGIN_PATH = os.environ.get("WMS_LOGIN_PATH", "/login") or "/login"


def build_server_env(base_env: dict) -> dict:
    """构造 run_server.py 的生产环境变量（本部署离线 HTTP 场景的必需放行项）。

    start_wms_offline.bat 是同一组变量的 .bat 版本；本函数是 Python 侧等价实现，
    供 restart.py 与 update_from_github.bat 第 [6/6] 步复用。缺项会让
    config.validate_production_security_config 在 import 阶段 RuntimeError，
    服务静默起不来（2026-10-11 更新脚本启动失败事故根因）。
    """
    env = dict(base_env)
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
    # BUG-2026-09-19-003：生产模式下 config.validate_production_security_config 要求
    # SESSION_COOKIE_SECURE=true 或显式 WMS_ALLOW_INSECURE_COOKIE=1，否则在 import
    # 阶段直接 RuntimeError——这正是 update_from_github.bat 第 [6/6] 步经本脚本启动时
    # 静默失败的原因（start_wms_offline.bat 设了该变量，本脚本漏了）。
    # 本部署为 127.0.0.1:8080 HTTP + nginx HTTPS，与 start_wms_offline.bat 保持一致
    # 默认放行；HTTPS 部署请设 SESSION_COOKIE_SECURE=true 覆盖本默认。
    _secure = env.get("SESSION_COOKIE_SECURE", "").strip().lower() in ("true", "1", "yes")
    if not _secure and "WMS_ALLOW_INSECURE_COOKIE" not in env:
        env["WMS_ALLOW_INSECURE_COOKIE"] = "1"
        print(
            "WARNING: SESSION_COOKIE_SECURE 未开启且未显式设置 WMS_ALLOW_INSECURE_COOKIE，"
            "已默认接受非 Secure Cookie 用于 127.0.0.1 HTTP 部署（与 start_wms_offline.bat 一致）。"
            " HTTPS 部署请设置 SESSION_COOKIE_SECURE=true 并移除该放行。"
        )
    return env


def main() -> int:
    os.chdir(APP_DIR)
    LOG_DIR.mkdir(exist_ok=True)

    print("Restarting WMS safely.")
    print("This script does not delete any database files.")

    # Repair task: AUDIT-FULL-20261016-001-F03
    try:
        port = int(os.environ.get("WMS_PORT") or DEFAULT_PORT)
        if not 1 <= port <= 65535:
            raise ValueError
        stop_verified_server(APP_DIR, port)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"无法安全停止旧实例，已拒绝重启：{exc}")
        return 1
    env = build_server_env(os.environ)
    env["WMS_PORT"] = str(port)
    login_path = os.environ.get("WMS_LOGIN_PATH", DEFAULT_LOGIN_PATH) or DEFAULT_LOGIN_PATH
    if not login_path.startswith("/"):
        login_path = "/" + login_path
    health_url = f"http://127.0.0.1:{port}{login_path}"

    child = None
    try:
        with open(LOG_DIR / "service_stdout.log", "ab", buffering=0) as stdout, open(
                LOG_DIR / "service_stderr.log", "ab", buffering=0) as stderr:
            child = subprocess.Popen(
                [sys.executable, str(APP_DIR / "run_server.py")], cwd=APP_DIR, env=env,
                stdout=stdout, stderr=stderr,
                creationflags=(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                               | getattr(subprocess, "CREATE_NO_WINDOW", 0)))
        for _ in range(15):
            if child.poll() is not None:
                print("新WMS进程已退出，启动失败；不会将其他进程的HTTP响应当作成功。")
                return 1
            if owns_port(child.pid, APP_DIR, port):
                try:
                    with urllib.request.urlopen(health_url, timeout=3) as response:
                        if response.status == 200 and child.poll() is None and owns_port(child.pid, APP_DIR, port):
                            print(f"WMS is running: {health_url} (PID {child.pid})")
                            return 0
                except OSError:
                    pass
            time.sleep(2)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"启动检查失败：{exc}")
    print(f"WMS did not respond on {health_url}.")
    print(r"Check logs\service_stdout.log and logs\service_stderr.log.")
    if child is not None and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            print("新子进程未及时退出，请人工确认；不扩大停止范围。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
