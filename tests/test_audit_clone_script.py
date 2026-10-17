# -*- coding: utf-8 -*-
"""A13 回归锁：clone_wms_main.ps1 必须逐步检查 git 退出码，失败即停。

AUDIT-FULL-20261016-001-F09-F03（原 A13）：旧脚本对 git 原生命令不检查 $LASTEXITCODE，
拉取/克隆失败后仍会打印"已准备 main 工作区"。PowerShell 的 ErrorActionPreference=Stop
只对 cmdlet 生效，原生 exe 非零退出不会抛异常。
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools' / 'clone_wms_main.ps1'


def _text():
    return SCRIPT.read_text(encoding='utf-8-sig')


def test_every_git_call_is_wrapped_and_checked():
    text = _text()
    assert 'function Invoke-Git' in text
    assert '$LASTEXITCODE -ne 0' in text
    assert '& git @Arguments' in text
    # 不允许再出现裸的 git 调用行（全部经 Invoke-Git）
    bare = [line.strip() for line in text.splitlines()
            if line.strip().startswith('git ') or line.strip().startswith('& git ') and 'dot-source' in line]
    assert bare == [], bare


def test_verifies_local_and_remote_head():
    text = _text()
    assert 'rev-parse HEAD' in text
    assert 'rev-parse "origin/main"' in text
    assert '本地 HEAD 与远端 main 不一致' in text


def test_has_utf8_bom_for_powershell_51():
    assert SCRIPT.read_bytes().startswith(b'\xef\xbb\xbf')


@pytest.mark.skipif(sys.platform != 'win32' or shutil.which('powershell') is None,
                    reason='需要 Windows PowerShell 做行为验证')
def test_fails_before_printing_success_on_non_git_dir(tmp_path):
    (tmp_path / 'keep.txt').write_text('x', encoding='utf-8')
    result = subprocess.run(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPT),
         '-Destination', str(tmp_path)],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode != 0
    assert '已准备 main 工作区' not in result.stdout
