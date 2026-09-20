# -*- coding: utf-8 -*-
"""A11 全量模式（--full-a11）黄金测试。

A11 默认是"新增代码生效"规则：仅检查 git staged 新增行，CI checkout 无 staged
文件时形同虚设。--full-a11（2026-09-20 新增，P0-1 遗留子项落地）切换为全量
扫描：不过滤 staged，存量代码同样强制，供 CI 硬门禁使用。

本测试在临时 git 仓库中验证两模式的行为差异与豁免口径不变。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_LINT = WORKSPACE_ROOT / "scripts" / "lint_wms_rules.py"

# 存量违规：material.stock 与比较运算符同现（校验语境）
VIOLATION_SRC = (
    "def check_enough(material, quantity):\n"
    "    if material.stock < quantity:\n"
    "        return False\n"
    "    return True\n"
)

# 存量违规 + 豁免注释（上一行）
ALLOWED_SRC = (
    "def check_enough(material, quantity):\n"
    "    # stock-truth:reason=测试豁免——单仓兜底口径\n"
    "    if material.stock < quantity:\n"
    "        return False\n"
    "    return True\n"
)

# 展示用途：序列化输出，无比较语境
DISPLAY_SRC = (
    "def serialize(material):\n"
    "    return {'stock': material.stock or 0}\n"
)


def _run_git(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def temp_repo():
    """临时 git 仓库：复制 lint 脚本 + app/ 目录播种业务文件（已提交，无 staged）。"""
    tmp = Path(tempfile.mkdtemp(prefix="wms_a11_full_"))
    try:
        _run_git(["init", "-q"], tmp)
        _run_git(["config", "user.email", "test@example.com"], tmp)
        _run_git(["config", "user.name", "Test"], tmp)
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()
        shutil.copy(SCRIPT_LINT, scripts_dir / "lint_wms_rules.py")
        (tmp / "app").mkdir()
        _run_git(["add", "-A"], tmp)
        _run_git(["commit", "-q", "-m", "init"], tmp)
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _seed_committed_file(repo: Path, name: str, content: str) -> None:
    """写入业务文件并提交——形成'存量代码'（无任何 staged 改动）。"""
    (repo / "app" / name).write_text(content, encoding="utf-8")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", f"add {name}"], repo)


def _run_lint(repo: Path, extra_args: list) -> tuple:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "scripts/lint_wms_rules.py", "--rule", "a11"] + extra_args,
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout


def test_full_mode_flags_existing_violation(temp_repo):
    """存量违规（已提交、无 staged）：--full-a11 必须抓到（CI 硬门禁的牙齿）。"""
    _seed_committed_file(temp_repo, "check_stock.py", VIOLATION_SRC)
    code, out = _run_lint(temp_repo, ["--full-a11"])
    assert code == 1
    assert "check_stock.py" in out


def test_default_mode_ignores_existing_violation(temp_repo):
    """同一存量文件在默认模式下不报（无 staged 新增行）——证明两模式确有差异。"""
    _seed_committed_file(temp_repo, "check_stock.py", VIOLATION_SRC)
    code, out = _run_lint(temp_repo, [])
    assert code == 0, out


def test_full_mode_respects_allow_hint(temp_repo):
    """--full-a11 下 # stock-truth:reason= 豁免注释仍有效（存量 17 处豁免的兼容保障）。"""
    _seed_committed_file(temp_repo, "check_stock.py", ALLOWED_SRC)
    code, out = _run_lint(temp_repo, ["--full-a11"])
    assert code == 0, out


def test_full_mode_ignores_display_usage(temp_repo):
    """--full-a11 下展示用途（序列化输出）仍不报——判定口径不因全量模式变宽。"""
    _seed_committed_file(temp_repo, "serialize.py", DISPLAY_SRC)
    code, out = _run_lint(temp_repo, ["--full-a11"])
    assert code == 0, out


def test_full_mode_scans_without_any_staged_files(temp_repo):
    """无任何 staged 改动的仓库（CI checkout 场景）：--full-a11 仍执行扫描。"""
    _seed_committed_file(temp_repo, "check_stock.py", VIOLATION_SRC)
    assert not _run_git(["diff", "--cached", "--name-only"], temp_repo).stdout.strip()
    code, out = _run_lint(temp_repo, ["--full-a11"])
    assert code == 1
