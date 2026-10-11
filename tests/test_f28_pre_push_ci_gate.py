# -*- coding: utf-8 -*-
"""F2.8 回归：pre-push 接入 CI 全绿门禁。

静态契约（防止门禁调用被误删）+ shell 语法检查（bash -n，不执行）。
行为验证（CI 红时阻断）由实际 push / CI 承担，此处不做执行型测试以免依赖本机 bash。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-push"


def test_pre_push_invokes_ci_gate():
    body = HOOK.read_text(encoding="utf-8")
    assert "check_ci_green.py" in body, "pre-push 必须调用 CI 全绿门禁脚本"
    assert "WMS_SKIP_CI_GATE" in body, "pre-push 应提供显式逃生舱"
    assert "PRE-PUSH BLOCKED" in body, "CI 非绿时应阻断并给出提示"


def test_pre_push_syntax_ok():
    bash = shutil.which("bash")
    if not bash:
        import pytest
        pytest.skip("bash 不可用，跳过语法检查")
    proc = subprocess.run([bash, "-n", str(HOOK)], capture_output=True, text=True)
    assert proc.returncode == 0, f"pre-push 存在语法错误: {proc.stderr}"
