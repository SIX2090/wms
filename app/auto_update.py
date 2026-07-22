"""WMS 启动前自动从 GitHub main 分支更新代码和依赖。

AI-DEPLOY-F01: 本模块由 run_server.py 在每次 WMS 启动时调用一次，
确保 WMS 每次启动都自动从 GitHub main 分支拉取最新代码和依赖。
通过环境变量 WMS_SKIP_AUTO_UPDATE=1 可跳过（用于测试、安装、特殊运维场景）。
历史调用入口 start_wms_auto.bat 现已委托给 start_wms_offline.bat，
由 run_server.py 统一触发，避免重复执行。

设计原则：
- 任何步骤失败都不阻断 WMS 启动，用现有代码启动保证可用性。
- 仅做 git fetch + pull --ff-only，不做 force、不切分支。
- 数据库迁移由 app.py 启动逻辑 + WMS_NO_DB_TOUCH.flag 控制，本脚本不干预。
- 工作区不干净时跳过 pull，避免冲突，记录警告。
- 拉取的新代码在下一次 Python 进程启动时生效（Python 模块已加载到内存，
  当前进程仍运行旧代码）。这是 in-process 自动更新的标准行为，
  保证每次 WMS 重启后都运行 GitHub main 上的最新代码。
"""
# AI_TASK: AI-DEPLOY-F01
from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
LOG_DIR = APP_DIR / "logs"
LOG_FILE = LOG_DIR / "auto_update.log"
REMOTE = os.environ.get("WMS_GIT_REMOTE", "origin")
BRANCH = os.environ.get("WMS_GIT_BRANCH", "main")


def log(msg: str) -> None:
    """输出到 stdout 并追加到 logs/auto_update.log。"""
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run_git(*args: str) -> tuple[int, str, str]:
    """执行 git 命令，返回 (returncode, stdout, stderr)。"""
    result = subprocess.run(
        ["git", *args],
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def find_python() -> str | None:
    """查找 Python 解释器，优先绿色版，兼容 Linux/Windows。"""
    candidates = [
        ROOT_DIR / "python" / "python.exe",
        ROOT_DIR / "runtime" / "Python311" / "python.exe",
        APP_DIR / "python" / "python.exe",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    # 系统 PATH（跨平台）
    try:
        if os.name == "nt":
            where = subprocess.run(["where", "python.exe"], capture_output=True, text=True)
        else:
            where = subprocess.run(["which", "python3"], capture_output=True, text=True)
        if where.returncode == 0 and where.stdout.strip():
            return where.stdout.strip().splitlines()[0]
    except (FileNotFoundError, OSError):
        pass
    return sys.executable


def backup_database() -> None:
    """更新前备份 instance/inventory.db 到 backups/。"""
    db = APP_DIR / "instance" / "inventory.db"
    if not db.exists():
        return
    backup_dir = ROOT_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"before_auto_update_{stamp}_inventory.db"
    try:
        shutil.copy2(db, dest)
        log(f"数据库已备份: {dest}")
    except OSError as e:
        log(f"[警告] 数据库备份失败: {e}")


def pip_install(python_exe: str) -> None:
    """更新 Python 依赖，优先离线 wheelhouse，失败不阻断。"""
    req = APP_DIR / "requirements.txt"
    if not req.exists():
        return
    wheelhouse = ROOT_DIR / "wheelhouse"
    if wheelhouse.exists():
        cmd = [python_exe, "-m", "pip", "install", "--no-index",
               "--find-links", str(wheelhouse), "-r", str(req)]
    else:
        cmd = [python_exe, "-m", "pip", "install", "-r", str(req)]
    log("更新 Python 依赖...")
    result = subprocess.run(cmd, cwd=str(APP_DIR), capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode == 0:
        log("依赖更新完成")
    else:
        log(f"[警告] 依赖更新失败（不阻断启动）: {result.stderr.strip()[:500]}")


def main() -> int:
    log("=" * 60)
    log("WMS 启动前自动更新检查")

    git_dir = ROOT_DIR / ".git"
    if not git_dir.exists():
        log(f"非 Git 仓库（{git_dir} 不存在），跳过自动更新，直接启动")
        return 0

    # 检查 git 可用
    check = subprocess.run(["git", "--version"], capture_output=True, text=True)
    if check.returncode != 0:
        log("[警告] git 不可用，跳过自动更新")
        return 0

    # 检查分支
    code, current, _ = run_git("branch", "--show-current")
    if code != 0:
        log(f"[警告] 无法读取当前分支，跳过更新: {current}")
        return 0
    if current != BRANCH:
        log(f"[警告] 当前分支 {current} 不是 {BRANCH}，跳过自动更新（避免切分支）")
        return 0

    # fetch
    code, _, err = run_git("fetch", REMOTE, BRANCH)
    if code != 0:
        log(f"[警告] git fetch 失败（不阻断启动）: {err}")
        return 0
    log(f"已从 {REMOTE}/{BRANCH} 拉取远端信息")

    # 比较本地与远端
    code, behind, _ = run_git("rev-list", "--count", "HEAD", f"{REMOTE}/{BRANCH}")
    if code != 0:
        log(f"[警告] 无法比较版本，跳过更新: {behind}")
        return 0
    behind = behind.strip()
    if behind == "0":
        log("已是最新，无需更新")
        return 0

    log(f"落后远端 {behind} 个提交，开始更新")

    # 检查工作区干净
    code, status, _ = run_git("status", "--porcelain")
    if code != 0 or status.strip():
        log(f"[警告] 工作区不干净，跳过 pull 以避免冲突。未提交改动:\n{status}")
        return 0

    # 备份数据库
    backup_database()

    # pull --ff-only
    code, out, err = run_git("pull", "--ff-only", REMOTE, BRANCH)
    if code != 0:
        log(f"[警告] git pull 失败（不阻断启动）: {err}")
        return 0
    log(f"代码已更新:\n{out}")

    # 更新依赖
    python_exe = find_python()
    if python_exe:
        pip_install(python_exe)
    else:
        log("[警告] 未找到 Python，跳过依赖更新")

    log("自动更新完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
