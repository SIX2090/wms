# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011-F06：低置信度阈值必须单一来源（0.80）。

审计 Q6：同一概念曾出现 0.80/0.85/0.85 三个值，指标与门禁不同源，
0.80~0.85 区间的行在两处判定相反。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ai.documents import constants  # noqa: E402
from ai.documents import document_confirmation  # noqa: E402
from ai.ops import acceptance_evidence  # noqa: E402


def test_constant_value_and_reexports():
    assert constants.LOW_CONFIDENCE_THRESHOLD == 0.80
    assert document_confirmation.LOW_CONFIDENCE_THRESHOLD == 0.80
    assert acceptance_evidence.LOW_CONFIDENCE_THRESHOLD == 0.80


def test_no_duplicate_definitions():
    hits = []
    for path in list(APP.rglob('*.py')):
        text = path.read_text(encoding='utf-8', errors='replace')
        hits += [(path, m.start()) for m in re.finditer(r'^LOW_CONFIDENCE_THRESHOLD\s*=', text, re.M)]
    assert len(hits) == 1, hits


def test_no_hardcoded_low_confidence_comparison():
    """只锁"低置信度判定"这一语义；0.85 作为默认中等置信度/相似度阈值是别的语义。"""
    offenders = []
    pattern = re.compile(r'confidence\s*<\s*0\.85', re.I)
    for path in list(APP.rglob('*.py')):
        text = path.read_text(encoding='utf-8', errors='replace')
        for line in text.splitlines():
            if pattern.search(line):
                offenders.append(f'{path}:{line.strip()}')
    assert offenders == [], offenders
