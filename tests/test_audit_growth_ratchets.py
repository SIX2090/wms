# -*- coding: utf-8 -*-
"""BUG-2026-10-17-013-F05：两处历史欠账只许减不许增（棘轮）。

1. 模板内联原生写 fetch：审计 F1，现存 157 处；迁移完成前禁止新增。
2. pydantic 书面豁免（# pydantic:reason=）：审计 §9.2，现存 279 处。
任一数字上涨即失败；下降后请同步下调本文件基线。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
APP = ROOT / 'app'

RAW_FETCH_BASELINE = 157
PYDANTIC_EXEMPTION_BASELINE = 279


def _raw_write_fetch_count():
    import re
    pattern = re.compile(r"fetch\s*\([^)]{0,300}?method\s*:\s*['\"](POST|PUT|DELETE|PATCH)", re.S)
    total = 0
    for path in TEMPLATES.glob('*.html'):
        total += len(pattern.findall(path.read_text(encoding='utf-8', errors='replace')))
    return total


def _pydantic_exemption_count():
    total = 0
    for path in APP.rglob('*.py'):
        if '__pycache__' in str(path):
            continue
        total += path.read_text(encoding='utf-8', errors='replace').count('pydantic:reason=')
    return total


def test_template_raw_write_fetch_does_not_grow():
    current = _raw_write_fetch_count()
    assert current <= RAW_FETCH_BASELINE, (
        f'模板内联原生写 fetch 由 {RAW_FETCH_BASELINE} 增至 {current}；'
        '新代码请走 WMS.api.post/put/delete，迁移后同步下调基线。')


def test_pydantic_exemptions_do_not_grow():
    current = _pydantic_exemption_count()
    assert current <= PYDANTIC_EXEMPTION_BASELINE, (
        f'pydantic 豁免由 {PYDANTIC_EXEMPTION_BASELINE} 增至 {current}；'
        '新写接口请用 BaseModel，迁移后同步下调基线。')
