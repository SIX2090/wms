# -*- coding: utf-8 -*-
"""BUG-2026-10-17-010 回归锁：lint 脚本在 cp936/GBK 控制台下不得崩溃。

根因：脚本直接 print ✓/✗/⚠，GBK 无法编码这些符号 -> UnicodeEncodeError。
pre-commit 只看退出码，脚本崩溃被当成"发现违规"，于是任何提交都被拒。
修法：stdout/stderr errors=replace 兜底 + 按编码能力降级 ASCII 标记。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def _run(args, encoding):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = encoding
    env['PYTHONUTF8'] = '0' if encoding.lower().startswith('gbk') else '1'
    return subprocess.run([sys.executable, *args], cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding=encoding,
                          errors='replace', timeout=180)


@pytest.mark.parametrize('encoding', ['gbk', 'utf-8'])
def test_fetch_lint_survives_console_encoding(encoding):
    result = _run(['scripts/lint_no_raw_post_fetch.py', '--repo-root', str(ROOT)], encoding)
    combined = (result.stdout or '') + (result.stderr or '')
    assert 'UnicodeEncodeError' not in combined
    assert 'Traceback' not in combined
    assert result.returncode == 0, combined[-800:]


@pytest.mark.parametrize('encoding', ['gbk', 'utf-8'])
def test_rule_lint_staged_survives_console_encoding(encoding):
    result = _run(['scripts/lint_wms_rules.py', '--staged'], encoding)
    combined = (result.stdout or '') + (result.stderr or '')
    assert 'UnicodeEncodeError' not in combined
    assert 'Traceback' not in combined
    assert result.returncode == 0, combined[-800:]


def test_glyph_degrades_on_gbk_and_keeps_emoji_on_utf8():
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "import lint_no_raw_post_fetch as m;"
        "print(m._glyph(chr(0x26a0), '[WARN]'))" % str(SCRIPTS)
    )
    gbk = subprocess.run([sys.executable, '-c', code], cwd=str(ROOT),
                         env={**os.environ, 'PYTHONIOENCODING': 'gbk'},
                         capture_output=True, text=True, encoding='gbk', errors='replace', timeout=60)
    assert gbk.returncode == 0, gbk.stderr
    assert '[WARN]' in gbk.stdout

    utf8 = subprocess.run([sys.executable, '-c', code], cwd=str(ROOT),
                          env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert utf8.returncode == 0, utf8.stderr
    assert chr(0x26a0) in utf8.stdout
