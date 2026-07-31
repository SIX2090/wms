#!/usr/bin/env python3
"""WMS CI 冒烟测试包装：启动 WMS 服务 → 等就绪 → 跑全量冒烟 → 关闭服务。

退出码约定：
  0 = 冒烟测试全部通过
  1 = 冒烟测试存在失败项
  2 = 服务启动失败 / 端口被占用 / 未在超时时间内就绪
  3 = 冒烟测试脚本本身异常（非 0/1 退出码）

设计要点：
  - 与 full_smoke_test.py 解耦：仅负责"启服务 + 跑 + 收尾"
  - 服务进程日志落到 /tmp/wms_server.log，便于 CI 抓取
  - 健康检查：HTTP GET /login 期待 200
  - 端口默认 18080，避开本机 8080 的 WMS 服务
  - 仅依赖 Python 标准库 + requests（已在 requirements.txt）
"""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 仓库根目录：scripts/ 的父目录
REPO_ROOT = Path(__file__).resolve().parent.parent

# 启动参数
HOST = "127.0.0.1"
PORT = 18080
BASE_URL = f"http://{HOST}:{PORT}"
HEALTH_PATH = "/login"
WAIT_TIMEOUT_SEC = 30  # 服务就绪最长等待时间
POLL_INTERVAL_SEC = 0.5
LOG_PATH = Path("/tmp/wms_server.log")


def start_server():
    """在子进程中启动 WMS 服务，返回 (proc, log_file)。

    环境变量：
      FLASK_ENV=production          使用生产配置
      WMS_ALLOW_AUTO_SECRET_KEY=1   CI 无 SECRET_KEY 时允许自动生成
      WMS_SKIP_AUTO_UPDATE=1        跳过启动前 GitHub 更新
      WMS_BOOTSTRAP_PASSWORD=admin  admin 初始密码
      WMS_PORT=18080                监听端口（run_server.py 已支持）
      WMS_HOST=127.0.0.1            监听 host
    """
    env = os.environ.copy()
    env["FLASK_ENV"] = "production"
    env["WMS_ALLOW_AUTO_SECRET_KEY"] = "1"
    env["WMS_SKIP_AUTO_UPDATE"] = "1"
    env["WMS_BOOTSTRAP_PASSWORD"] = "admin"
    env["WMS_PORT"] = str(PORT)
    env["WMS_HOST"] = HOST
    # 确保 PYTHONPATH 包含 app 目录（与 start_wms_offline.bat 一致）
    env["PYTHONPATH"] = str(REPO_ROOT / "app") + os.pathsep + env.get("PYTHONPATH", "")

    log_file = open(LOG_PATH, "w", encoding="utf-8")
    proc = subprocess.Popen(
        ["python3", "app/run_server.py"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return proc, log_file


def wait_ready(timeout=WAIT_TIMEOUT_SEC):
    """轮询 health check，直到 /login 返回 200 或超时。返回 bool。"""
    url = f"{BASE_URL}{HEALTH_PATH}"
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except urllib.error.HTTPError as e:
            # 200 之外视为未就绪（401/403 等说明服务起来了但权限未就绪）
            if e.code in (200, 302):
                return True
            last_error = f"HTTP {e.code}"
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_error = str(e)
        except Exception as e:  # noqa: BLE001
            last_error = str(e)
        time.sleep(POLL_INTERVAL_SEC)
    print(f"  last_error={last_error}", flush=True)
    return False


def stop_server(proc, grace_sec=5):
    """优雅关闭 WMS 服务：先 SIGTERM，超时再 SIGKILL。"""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=grace_sec)
    except subprocess.TimeoutExpired:
        print("  [warn] SIGTERM 未响应，强制 SIGKILL", flush=True)
        try:
            proc.kill()
            proc.wait(timeout=grace_sec)
        except Exception:
            pass


def print_log_tail(n=30):
    """打印日志末尾 n 行，便于排错。"""
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        print(f"  --- 日志末 {min(n, len(lines))} 行 ({LOG_PATH}) ---")
        for line in lines[-n:]:
            print(f"    {line.rstrip()}")
        print(f"  --- 日志结束 ---")
    except Exception as e:
        print(f"  读取日志失败: {e}")


def main():
    print("=" * 60, flush=True)
    print("WMS CI 冒烟测试包装", flush=True)
    print(f"  仓库: {REPO_ROOT}", flush=True)
    print(f"  监听: {BASE_URL}", flush=True)
    print("=" * 60, flush=True)

    proc = None
    log_file = None
    try:
        # 1. 启动服务
        print("\n[1/4] 启动 WMS 服务...", flush=True)
        proc, log_file = start_server()
        print(f"  PID: {proc.pid}", flush=True)
        print(f"  日志: {LOG_PATH}", flush=True)

        # 2. 等就绪
        print(f"\n[2/4] 等待服务就绪 (≤{WAIT_TIMEOUT_SEC}s)...", flush=True)
        if not wait_ready():
            print(f"  ✗ 超时未就绪", flush=True)
            print_log_tail(40)
            return 2
        print(f"  ✓ 服务已就绪", flush=True)

        # 3. 跑冒烟测试
        print(f"\n[3/4] 跑全量冒烟测试 (BASE={BASE_URL})...", flush=True)
        smoke_proc = subprocess.run(
            ["python3", "scripts/full_smoke_test.py", "--base-url", BASE_URL],
            cwd=str(REPO_ROOT),
        )
        smoke_exit = smoke_proc.returncode
        print(f"\n  冒烟测试 exit code: {smoke_exit}", flush=True)
        if smoke_exit not in (0, 1):
            print(f"  异常 exit code（非 0/1），视为基础设施问题", flush=True)
            print_log_tail(20)
            return 3

        # 4. 关闭服务
        print(f"\n[4/4] 关闭服务...", flush=True)
        stop_server(proc)
        log_file.close()
        log_file = None
        print(f"  ✓ 服务已关闭", flush=True)

        # 退出码语义
        print("\n" + "=" * 60, flush=True)
        if smoke_exit == 0:
            print("✅ CI 冒烟测试 全部通过", flush=True)
            return 0
        print(f"❌ CI 冒烟测试 有失败项 (exit={smoke_exit})", flush=True)
        return 1
    finally:
        # 异常路径保底
        if proc is not None and proc.poll() is None:
            stop_server(proc)
        if log_file is not None:
            try:
                log_file.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
