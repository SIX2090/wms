# -*- coding: utf-8 -*-
"""F2.8 回归：pre-push 接入 CI 全绿门禁。

静态契约（防止门禁调用被误删）+ shell 语法检查（bash -n，不执行）。
行为验证（CI 红时阻断）由实际 push / CI 承担，此处不做执行型测试以免依赖本机 bash。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-push"


def test_pre_push_invokes_ci_gate():
    body = HOOK.read_text(encoding="utf-8")
    assert "check_ci_green.py" in body, "pre-push 必须调用 CI 全绿门禁脚本"
    assert "WMS_SKIP_CI_GATE" in body, "pre-push 应提供显式逃生舱"
    assert "PRE-PUSH BLOCKED" in body, "CI 非绿时应阻断并给出提示"


def test_pre_push_validates_interpreter_before_use():
    """BUG-2026-10-17-007：解释器必须先真实执行验证，不能只看 command -v。

    Windows 的 python3 常是 Microsoft Store 0 字节别名：command -v 能找到，
    执行却返回 9009。原逻辑据此判定门禁未通过，把所有 push 都误拦。
    """
    body = HOOK.read_text(encoding="utf-8")
    assert '-c "import sys"' in body, "pre-push 必须真实执行验证解释器，避免 Store 别名阻断所有 push"


@pytest.mark.skipif(os.name == "nt", reason="Windows 的 chmod 不产生 MSYS 可执行位，行为验证交给 Linux CI")
def test_pre_push_skips_broken_python3_alias(tmp_path):
    """行为验证：PATH 里先放坏的 python3，钩子应跳过并改用可用的 python。"""
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash 不可用，跳过行为验证")

    broken_dir = tmp_path / "broken"
    broken_dir.mkdir()
    broken = broken_dir / "python3"
    broken.write_text("#!/bin/sh\nexit 9009\n", encoding="utf-8")

    good_dir = tmp_path / "good"
    good_dir.mkdir()
    good = good_dir / "python"
    good.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for path in (broken, good):
        path.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(broken_dir), str(good_dir), env.get("PATH", "")])
    env.pop("WMS_SKIP_CI_GATE", None)

    proc = subprocess.run(
        [bash, str(HOOK)], input="", capture_output=True, text=True,
        cwd=str(ROOT), env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert "PRE-PUSH BLOCKED" not in proc.stderr


def test_pre_push_syntax_ok():
    bash = shutil.which("bash")
    if not bash:
        import pytest
        pytest.skip("bash 不可用，跳过语法检查")
    proc = subprocess.run([bash, "-n", str(HOOK)], capture_output=True, text=True)
    assert proc.returncode == 0, f"pre-push 存在语法错误: {proc.stderr}"
