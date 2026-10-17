# -*- coding: utf-8 -*-
"""A17 回归锁：README 的库存口径必须按库位开关分档，不能无条件写三账全等。

AUDIT-FULL-20261016-001-F09-F07（原 A17）：README 原文写"总账 = Σ库位账 = Σ流水账"，
而关闭库位管理时库位账不落账、允许历史残留；照 README 排查会把正常残留当坏账。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _readme():
    return (ROOT / 'README.md').read_text(encoding='utf-8')


def test_readme_states_switch_dependent_identity():
    text = _readme()
    assert '开启库位管理时' in text
    assert '关闭库位管理时' in text
    assert '总账 = Σ流水账' in text
    assert 'INVENTORY_TRUTH.md' in text


def test_authority_doc_keeps_both_branches():
    truth = (ROOT / 'INVENTORY_TRUTH.md').read_text(encoding='utf-8')
    assert '开启库位管理' in truth
    assert '关闭库位管理' in truth
    assert '① = Σ③' in truth
