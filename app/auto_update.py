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
- 已跟踪文件有未提交改动时默认先放入 Git stash，再继续 pull；可用 WMS_AUTO_UPDATE_DIRTY=skip 保守地跳过更新。
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
# BUG-2026-08-13-006：供应链加固——可选固定提交/标签。
# 设置 WMS_GIT_PIN=<完整 SHA 或 git tag> 后，fetch 完成但 pull 之前会校验
# {REMOTE}/{BRANCH} 的实际 tip 是否等于该 pin（tag 先 rev-parse 解析成 SHA），
# 不一致则拒绝 pull，防止远端被篡改后自动拉入任意代码。留空则维持原行为。
GIT_PIN = os.environ.get("WMS_GIT_PIN", "").strip()
# BUG-2026-08-13-006：可选强制 pip 哈希校验。置 1 时给 pip install 追加
# --require-hashes，要求 requirements.txt 内每条依赖均带 hash 行。
PIP_REQUIRE_HASHES = os.environ.get("WMS_PIP_REQUIRE_HASHES", "0").strip().lower() in (
    "1", "true", "yes", "on"
)

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
    if PIP_REQUIRE_HASHES:
        cmd.append("--require-hashes")
        log("更新 Python 依赖（已启用 --require-hashes 哈希校验）...")
    else:
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
        log_pip_versions(python_exe)
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


def resolve_sha(ref: str) -> str | None:  # no-test:reason=由 TestResolveSha.test_resolve_success/failure_returns_none 覆盖
    """把任意 ref（分支/tag/SHA）解析为完整 40 位 SHA，失败返回 None。"""
    code, out, err = run_git("rev-parse", ref)
    if code != 0 or not out:
        return None
    return out.strip().splitlines()[0]


def verify_pin(remote_sha: str) -> tuple[bool, str]:  # no-test:reason=由 TestVerifyPin 6 个用例覆盖（空/完整/短 SHA/tag/不匹配/未知 tag）
    """校验远端 tip 是否匹配 WMS_GIT_PIN。返回 (ok, detail)。"""
    if not GIT_PIN:
        return True, ""
    pin = GIT_PIN
    try:
        int(pin, 16)  # 纯十六进制 → 视作 SHA，直接前缀匹配
    except ValueError:
        resolved = resolve_sha(pin)
        if not resolved:
            return False, f"WMS_GIT_PIN={pin!r} 无法解析为提交或标签，拒绝更新"
        pin = resolved
    if remote_sha.startswith(pin):
        return True, f"远端 tip {remote_sha} 匹配固定 pin {GIT_PIN!r}"
    return False, (
        f"[安全拒绝] 远端 tip {remote_sha} 不匹配固定 pin {GIT_PIN!r}，"
        "已跳过 pull。请人工核对远端提交，或更新 WMS_GIT_PIN 后再启用自动更新。"
    )


def log_pulled_commits(pre_sha: str, post_sha: str) -> None:  # no-test:reason=审计日志辅助函数，由 main() 集成测试与源码静态校验覆盖
    """把本次 pull 引入的提交（subject + author）写入审计日志。"""
    if not pre_sha or not post_sha or pre_sha == post_sha:
        return
    code, out, err = run_git(
        "log", "--pretty=format:%h | %an | %ad | %s",
        "--date=short",
        f"{pre_sha}..{post_sha}",
    )
    if code == 0 and out.strip():
        log(f"本次更新引入的提交（{pre_sha[:10]}..{post_sha[:10]}）:\n{out}")
    else:
        log(f"[警告] 无法读取引入提交清单: {err or out}")


def log_pip_versions(python_exe: str) -> None:  # no-test:reason=审计日志辅助函数，由 TestPipRequireHashes 间接覆盖（pip_install 成功分支调用）
    """更新依赖后把已安装包版本写入审计日志，便于追溯供应链。"""
    try:
        result = subprocess.run(
            [python_exe, "-m", "pip", "freeze"],
            cwd=str(APP_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            installed = result.stdout.strip().splitlines()
            log(f"依赖更新后已安装包版本（共 {len(installed)} 个）:\n" + "\n".join(installed))
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass


def stash_tracked_changes() -> tuple[bool, str]:
    """将已跟踪本地改动安全保存到 stash，避免启动更新覆盖现场修改。"""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    code, out, err = run_git(
        "stash", "push", "-m", f"WMS auto-update backup {stamp}"
    )
    if code != 0:
        return False, err or out or f"git stash failed ({code})"
    return True, out or "(no changes stashed)"


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
    remote_ref = f"{REMOTE}/{BRANCH}"
    # BUG-2026-08-13-006：供应链加固——固定提交/标签校验。
    remote_sha = resolve_sha(remote_ref)
    if remote_sha:
        log(f"远端 tip SHA: {remote_sha}")
    if GIT_PIN:
        if not remote_sha:
            log("[警告] 无法解析远端 tip SHA，无法校验 WMS_GIT_PIN，跳过更新")
            return 0
        ok_pin, pin_detail = verify_pin(remote_sha)
        log(pin_detail)
        if not ok_pin:
            return 0

    # AI-DEPLOY-F01-FIX-02: 真正的 behind / ahead，不是两 tip 并集
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
    stashed_local_changes = False
    if status.strip():
        log(f"检测到已跟踪文件有未提交改动:\n{status}")
        if os.environ.get("WMS_AUTO_UPDATE_DIRTY", "stash").strip().lower() in (
            "skip", "false", "0", "no"
        ):
            log(
                "[警告] WMS_AUTO_UPDATE_DIRTY=skip，跳过 pull 以保留本地改动。"
            )
            return 0
        ok_stash, stash_result = stash_tracked_changes()
        if not ok_stash:
            log(f"[警告] 无法 stash 本地改动，跳过 pull: {stash_result}")
            return 0
        stashed_local_changes = True
        log(f"本地已跟踪改动已保存到 Git stash，继续更新: {stash_result}")
        code_u, untracked, _ = run_git("status", "--porcelain", "--untracked-files=normal")
        if code_u == 0 and untracked.strip():
            log("（另有未跟踪文件，已忽略，不单独拦截 pull）")

    backup_database()
    pre_sha = resolve_sha("HEAD") or ""
    code, out, err = run_git("pull", "--ff-only", REMOTE, BRANCH)
    if code != 0:
        log(f"[警告] git pull --ff-only 失败（不阻断启动）: {err or out}")
        if stashed_local_changes:
            restore_code, restore_out, restore_err = run_git("stash", "pop")
            if restore_code == 0:
                log(f"更新失败，已恢复本地 stash 改动: {restore_out or '(restored)'}")
            else:
                log(
                    "[严重警告] 更新失败且无法恢复本地 stash，请立即执行 git stash list/pop: "
                    f"{restore_err or restore_out}"
                )
        if ahead > 0:
            log("提示: 本地超前远端时快进合并可能失败，需在服务器对齐历史后再更新。")
        return 0
    if stashed_local_changes:
        log(
            "代码已更新；本地旧改动保留在 Git stash，未自动重新应用。"
            "如需取回请先确认与远程代码的差异后执行 git stash list / git stash pop。"
        )
    else:
        log(f"代码已更新:\n{out or '(fast-forward)'}")

    post_sha = resolve_sha("HEAD") or ""
    if post_sha:
        log(f"更新后 HEAD SHA: {post_sha}")
    log_pulled_commits(pre_sha, post_sha)

    python_exe = find_python()
    if python_exe:
        pip_install(python_exe)
    else:
        log("[警告] 未找到 Python，跳过依赖更新")

    log("自动更新完成。若本次启动前已 import 旧模块，再重启一次 WMS 可确保全量新代码生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
