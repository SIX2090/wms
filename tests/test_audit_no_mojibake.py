# -*- coding: utf-8 -*-
"""BUG-2026-10-17-013-F06：用户可见文案不得出现 4 连问号乱码（审计 §5.5）。

历史转码事故把中文替换成 '?'，库里 16 处，本轮已全部修复；本用例防止回归。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
PATTERN = re.compile(r'\?{4,}')


def test_no_four_question_marks_in_app_python():
    offenders = []
    for path in APP.rglob('*.py'):
        if '__pycache__' in str(path):
            continue
        for lineno, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if PATTERN.search(line):
                offenders.append(f'{path.relative_to(ROOT)}:{lineno}: {line.strip()[:100]}')
    assert offenders == [], '发现乱码文案：' + '; '.join(offenders[:5])
