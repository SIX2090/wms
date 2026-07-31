#!/usr/bin/env python3
"""检查 git core.hooksPath 是否指向仓库自带的 .githooks 目录。

设计目的：
  - 在 CI 上 clone 后立即跑一遍，验证 install-hooks.sh 的可重现性
  - CI 自身是 ephemeral 的，clone 出来没有 .git/config，所以本检查设为
    continue-on-error: true，仅作为"开发者本地指引"的可达性证明
  - 本地开发者手动跑：python3 scripts/check_hooks_installed.py

退出码：
  0 = 已正确设置 hooksPath
  1 = 未设置或设置错误（提示用户跑 install-hooks.sh）
  2 = 仓库根目录找不到（不在 git 仓库里）
"""
import subprocess
import sys
from pathlib import Path

EXPECTED_HOOKS_SUFFIX = ".githooks"
REPO_ROOT = Path(__file__).resolve().parent.parent


def get_current_hooks_path():
    """读取 git config core.hooksPath，未设置返回 None。"""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def in_git_repo():
    """当前目录是否在 git 仓库内。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return result.returncode == 0


def main():
    if not in_git_repo():
        print("✗ 不在 git 仓库内（找不到 .git）", file=sys.stderr)
        return 2

    githooks_dir = REPO_ROOT / ".githooks"
    if not githooks_dir.exists():
        print(f"✗ 仓库缺少 {githooks_dir}（本检查无意义）", file=sys.stderr)
        return 2

    current = get_current_hooks_path()
    if current is None:
        print("✗ core.hooksPath 未设置")
        print("  说明: 提交时不会跑 .githooks/pre-commit 的 7 条防 BUG 规则")
        print("  修复: bash .githooks/install-hooks.sh")
        return 1

    # current 可能是绝对路径或相对路径，统一结尾比较
    if current.endswith(EXPECTED_HOOKS_SUFFIX) or current == str(githooks_dir):
        print(f"✓ core.hooksPath 已正确指向 {EXPECTED_HOOKS_SUFFIX}")
        print(f"  当前值: {current}")
        return 0

    print(f"✗ core.hooksPath 指向非 .githooks 目录: {current}")
    print(f"  期望结尾: {EXPECTED_HOOKS_SUFFIX}")
    print("  修复: bash .githooks/install-hooks.sh")
    return 1


if __name__ == "__main__":
    sys.exit(main())
