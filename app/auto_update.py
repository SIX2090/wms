"""WMS 启动前可选地从 GitHub main 分支更新代码和依赖。

AI-DEPLOY-F01 / AI-DEPLOY-F01-FIX-01 / AI-DEPLOY-F01-FIX-02:
本模块由 run_server.py 在系统设置「启动时自动从 GitHub 更新」开启时调用。
该设置默认关闭；开启后每次重启才会从 GitHub main 拉取代码和依赖。
环境变量 WMS_SKIP_AUTO_UPDATE=1 可强制跳过（测试、安装、特殊运维）。
历史入口 start_wms_auto.bat 由 run_server.py 统一触发，避免重复执行。

设计原则：
- 任何步骤失败都不阻断 WMS 启动，用现有代码启动保证可用性。
- 仅做 git fetch + pull --ff-only，不做 force、不切分支。
- 数据库迁移由 app.py 启动逻辑 + WMS_NO_DB_TOUCH.flag 控制，本脚本不干预。
- 已跟踪文件有未提交改动时跳过 pull，避免冲突；仅有未跟踪本地文件（如 runtime）不拦截。
- 落后提交数使用 HEAD..remote/branch（真正 behind），不是两 tip 并集计数。
- 拉取的新代码在同一次启动、import 业务模块之前生效；若进程已加载旧模块，
  需再重启一次才能用全新代码（标准 in-process 行为）。
"""
# AI_TASK: AI-DEPLOY-F01
# AI_TASK: AI-DEPLOY-F01-FIX-01
# AI_TASK: AI-DEPLOY-F01-FIX-02
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

_GIT_EXE: str | None = None


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


def find_git() -> str | None:
    """查找 git 可执行文件：PATH 优先，再尝试常见安装路径（nssm 服务 PATH 常不完整）。"""
    global _GIT_EXE
    if _GIT_EXE:
        return _GIT_EXE

    try:
        probe = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if probe.returncode == 0:
            _GIT_EXE = "git"
            return _GIT_EXE
    except (FileNotFoundError, OSError):
        pass

    candidates: list[Path] = []
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates.extend(
            [
                Path(pf) / "Git" / "cmd" / "git.exe",
                Path(pf) / "Git" / "bin" / "git.exe",
                Path(pf86) / "Git" / "cmd" / "git.exe",
                Path(pf86) / "Git" / "bin" / "git.exe",
                ROOT_DIR / "runtime" / "Git" / "cmd" / "git.exe",
                ROOT_DIR / "runtime" / "PortableGit" / "cmd" / "git.exe",
            ]
        )
        if local:
            candidates.append(Path(local) / "Programs" / "Git" / "cmd" / "git.exe")
    else:
        candidates.extend([Path("/usr/bin/git"), Path("/usr/local/bin/git")])

    for path in candidates:
        try:
            if path.is_file():
                probe = subprocess.run(
                    [str(path), "--version"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if probe.returncode == 0:
                    _GIT_EXE = str(path)
                    log(f"使用 Git: {_GIT_EXE}")
                    return _GIT_EXE
        except (FileNotFoundError, OSError):
            continue
    return None


def run_git(*args: str) -> tuple[int, str, str]:
    """执行 git 命令，返回 (returncode, stdout, stderr)。"""
    git = find_git()
    if not git:
        return 127, "", "git not found"
    try:
        result = subprocess.run(
            [git, *args],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (FileNotFoundError, OSError) as exc:
        return 127, "", str(exc)


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
        cmd = [
            python_exe,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "-r",
            str(req),
        ]
    else:
        cmd = [python_exe, "-m", "pip", "install", "-r", str(req)]
    log("更新 Python 依赖...")
    result = subprocess.run(
        cmd,
        cwd=str(APP_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        log("依赖更新完成")
    else:
        log(f"[警告] 依赖更新失败（不阻断启动）: {result.stderr.strip()[:500]}")


def count_commits(rev_range: str) -> tuple[bool, int, str]:
    """返回 (ok, count, raw_or_error)。"""
    code, out, err = run_git("rev-list", "--count", rev_range)
    if code != 0:
        return False, 0, err or out or f"rev-list failed ({code})"
    text = (out or "0").strip().splitlines()[-1] if out else "0"
    try:
        return True, int(text), text
    except ValueError:
        return False, 0, f"无法解析提交数: {out!r}"


def main() -> int:
    log("=" * 60)
    log("WMS 启动前自动更新检查（AI-DEPLOY-F01-FIX-02）")
    log("说明: 仅当系统设置开启「启动时自动从 GitHub 更新」时才会进入本流程；"
        "默认关闭。需重启 WMS 才会再次检查。")

    git_dir = ROOT_DIR / ".git"
    if not git_dir.exists():
        log(f"非 Git 仓库（{git_dir} 不存在），跳过自动更新，直接启动。"
            "云上请用 git clone 部署，或运行 deploy_cloud.bat。")
        return 0

    if not find_git():
        log("[警告] git 不可用（未安装或不在服务 PATH 中），跳过自动更新。"
            "请安装 Git for Windows，并确保 nssm 服务能找到 git.exe 后重启 WMS。")
        return 0

    code, current, err = run_git("branch", "--show-current")
    if code != 0:
        log(f"[警告] 无法读取当前分支，跳过更新: {err or current}")
        return 0
    if current != BRANCH:
        log(f"[警告] 当前分支 {current!r} 不是 {BRANCH}，跳过自动更新（避免切分支）")
        return 0

    code, _, err = run_git("fetch", REMOTE, BRANCH)
    if code != 0:
        log(f"[警告] git fetch 失败（不阻断启动）: {err}")
        log("提示: 检查服务器出网、GitHub 连通性，以及私有仓凭据"
            "（如 C:\\wms\\runtime\\.git-credentials）。")
        return 0
    log(f"已从 {REMOTE}/{BRANCH} 拉取远端信息")

    # AI-DEPLOY-F01-FIX-02: 真正的 behind / ahead，不是两 tip 并集
    remote_ref = f"{REMOTE}/{BRANCH}"
    ok_b, behind, raw_b = count_commits(f"HEAD..{remote_ref}")
    if not ok_b:
        log(f"[警告] 无法比较落后提交数，跳过更新: {raw_b}")
        return 0
    ok_a, ahead, raw_a = count_commits(f"{remote_ref}..HEAD")
    if ok_a and ahead > 0:
        log(f"本地相对 {remote_ref} 超前 {ahead} 个提交（仅本地有、远端没有）")

    if behind == 0:
        log(f"已与 {remote_ref} 同步（落后 0），无需 pull")
        return 0

    log(f"落后远端 {behind} 个提交（rev-list HEAD..{remote_ref}），准备更新")

    # 仅检查已跟踪文件改动；未跟踪的 runtime/日志等不拦截 pull
    code, status, err = run_git("status", "--porcelain", "--untracked-files=no")
    if code != 0:
        log(f"[警告] 无法检查工作区: {err or status}")
        return 0
    if status.strip():
        log(
            "[警告] 已跟踪文件有未提交改动，跳过 pull 以避免冲突。\n"
            f"{status}\n"
            "处理: 在服务器提交/还原这些文件后重启；"
            "或临时关闭自动更新、用 update_from_github.bat 手动处理。"
        )
        code_u, untracked, _ = run_git("status", "--porcelain", "--untracked-files=normal")
        if code_u == 0 and untracked.strip() and untracked.strip() != status.strip():
            log("（另有未跟踪文件，已忽略，不单独拦截 pull）")
        return 0

    backup_database()

    code, out, err = run_git("pull", "--ff-only", REMOTE, BRANCH)
    if code != 0:
        log(f"[警告] git pull --ff-only 失败（不阻断启动）: {err or out}")
        if ahead > 0:
            log("提示: 本地超前远端时快进合并可能失败，需在服务器对齐历史后再更新。")
        return 0
    log(f"代码已更新:\n{out or '(fast-forward)'}")

    python_exe = find_python()
    if python_exe:
        pip_install(python_exe)
    else:
        log("[警告] 未找到 Python，跳过依赖更新")

    log("自动更新完成。若本次启动前已 import 旧模块，再重启一次 WMS 可确保全量新代码生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
