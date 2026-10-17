# -*- coding: utf-8 -*-
"""BUG-2026-10-17-015-F06（审计 B8）：客户端错误响应不得回传异常原文。

原 63 处 return api_error(f'...{str(e)}') / jsonify(msg=f'...{str(e)}') /
flash(...{str(e)}) 会把 SQLAlchemy/SQLite 英文细节暴露给登录用户。
修复：统一为中文通用提示（细节留在 logger），ValueError 业务校验仍可回传。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'

LEAK = re.compile(
    r"(return\s+api_error\(f'[^']*\{str\(e\)\}"
    r"|return\s+jsonify\([^\n]*\{str\(e\)\}"
    r"|flash\(f'[^']*\{str\(e\)\})"
)


def test_no_exception_text_in_client_responses():
    offenders = []
    for path in APP.rglob('*.py'):
        if '__pycache__' in str(path):
            continue
        for lineno, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if LEAK.search(line):
                offenders.append(f'{path.relative_to(ROOT)}:{lineno}: {line.strip()[:120]}')
    assert offenders == [], '客户端仍回传异常原文：' + '; '.join(offenders[:5])
