# -*- coding: utf-8 -*-
"""A13 规则黄金测试：台账新增 BUG 条目必须含「生效确认」字段（R3 机械化）。

A13 是"新增代码生效"规则：仅检查 git staged 新增行中出现的条目头
（### BUG-… 等），要求条目块内含「生效确认」字样；编辑存量条目、
计数行等非条目头改动不触发。本测试用临时 git 仓库模拟三种场景。
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

BASELINE_SEED = (
    "# WMS BUG 基线\n\n"
    "更新时间：2026-09-19（累计 407 条）\n\n"
    "### BUG-2026-09-19-001（旧条目）\n\n"
    "- **生效条件**：重启生效。\n"
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
    """临时 git 仓库：复制 lint 脚本 + 播种既有台账。"""
    tmp = Path(tempfile.mkdtemp(prefix="wms_a13_"))
    try:
        _run_git(["init", "-q"], tmp)
        _run_git(["config", "user.email", "test@example.com"], tmp)
        _run_git(["config", "user.name", "Test"], tmp)
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()
        shutil.copy(SCRIPT_LINT, scripts_dir / "lint_wms_rules.py")
        (tmp / "WMS_BUG_BASELINE.md").write_text(BASELINE_SEED, encoding="utf-8")
        _run_git(["add", "-A"], tmp)
        _run_git(["commit", "-q", "-m", "init"], tmp)
        yield tmp
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _stage_baseline(repo: Path, content: str) -> None:
    (repo / "WMS_BUG_BASELINE.md").write_text(content, encoding="utf-8")
    _run_git(["add", "WMS_BUG_BASELINE.md"], repo)


def _run_lint_staged(repo: Path) -> tuple:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "scripts/lint_wms_rules.py", "--staged", "--rule", "a13"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    return proc.returncode, proc.stdout


def test_a13_flags_new_entry_without_effect_confirmation(temp_repo):
    """新增条目缺「生效确认」→ 违规。"""
    content = BASELINE_SEED + (
        "\n### BUG-2026-09-20-009（新条目）\n\n"
        "- **根因**：xxx。\n"
        "- **生效条件**：重启 WMS 服务生效。\n"
    )
    _stage_baseline(temp_repo, content)
    code, out = _run_lint_staged(temp_repo)
    assert code == 1
    assert "BUG-2026-09-20-009" in out
    assert "生效确认" in out


def test_a13_passes_new_entry_with_effect_confirmation(temp_repo):
    """新增条目含「生效确认」→ 通过（允许「待确认」占位）。"""
    content = BASELINE_SEED + (
        "\n### BUG-2026-09-20-010（新条目）\n\n"
        "- **根因**：xxx。\n"
        "- **生效条件**：重启 WMS 服务生效。\n"
        "- **生效确认**：待确认（重启后核对启动 banner 的 config-check 行）。\n"
    )
    _stage_baseline(temp_repo, content)
    code, out = _run_lint_staged(temp_repo)
    assert code == 0, out


def test_a13_ignores_non_entry_edits(temp_repo):
    """编辑存量条目 / 更新计数行（无新条目头）→ 不触发。"""
    content = BASELINE_SEED.replace("累计 407 条", "累计 408 条").replace(
        "- **生效条件**：重启生效。", "- **生效条件**：重启生效（已核对）。\n- 补充一行。")
    _stage_baseline(temp_repo, content)
    code, out = _run_lint_staged(temp_repo)
    assert code == 0, out
