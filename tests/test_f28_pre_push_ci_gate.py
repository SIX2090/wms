# -*- coding: utf-8 -*-
"""F2.8-PARALLEL-001: independent pushes retain branch and release checks."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".githooks" / "pre-push"


def bash_binary():
    found=shutil.which('bash')
    if found:
        return found
    git=shutil.which('git')
    if git:
        bundled=Path(git).resolve().parent.parent/'bin/bash.exe'
        if bundled.is_file():
            return str(bundled)
    pytest.skip('Bash unavailable')


def test_pre_push_keeps_local_checks_without_global_ci_gate():
    body = HOOK.read_text(encoding="utf-8")
    assert "check_ci_green.py" not in body
    assert '${WMS_SKIP_CI_GATE' not in body
    assert 'ALLOWED_LOCAL_BRANCH="main"' in body
    assert 'ALLOWED_REMOTE_BRANCH="main"' in body
    assert 'app/version.py 未递增' in body


@pytest.mark.parametrize('local_branch,remote_branch,allowed', [
    ('main', 'main', True),
    ('feature/another-task', 'main', False),
    ('main', 'feature/another-task', False),
])
def test_pre_push_needs_no_python_but_still_enforces_main(tmp_path,local_branch,remote_branch,allowed):
    bash = bash_binary()
    marker=tmp_path/'python-called.txt'
    env = dict(os.environ)
    env['WMS_TEST_PYTHON_MARKER']=str(marker)
    script='''
python3() { printf called > "$WMS_TEST_PYTHON_MARKER"; return 99; }
python() { printf called > "$WMS_TEST_PYTHON_MARKER"; return 99; }
py() { printf called > "$WMS_TEST_PYTHON_MARKER"; return 99; }
source "$1"
'''
    proc = subprocess.run(
        [bash,'-c',script,'hook-test',str(HOOK)],
        input=f'refs/heads/{local_branch} {"a"*40} refs/heads/{remote_branch} {"b"*40}\n',
        capture_output=True,text=True,encoding='utf-8',cwd=ROOT,env=env,timeout=30,
    )
    assert (proc.returncode==0)==allowed,proc.stderr
    assert not marker.exists()
    assert ('PRE-PUSH BLOCKED' in proc.stderr)==(not allowed)


def test_pre_push_syntax_ok():
    bash = bash_binary()
    proc = subprocess.run([bash, "-n", str(HOOK)], capture_output=True, text=True)
    assert proc.returncode == 0, f"pre-push 存在语法错误: {proc.stderr}"
