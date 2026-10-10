# -*- coding: utf-8 -*-
"""BUG-2026-10-10-F3：规格边界匹配后缀中文误放行 + 候选词尾部助词污染。

HTTP 全链路测试（本地启动真实 Flask 服务）发现：
1. '铜排够不够用' 剥掉 '够不够' 剩 '铜排用'，'用' 未剥导致查不到铜排
2. '6*10的铜排库存' 返回 U型橡胶密封条（spec='6*10内卡2-3mm'）——
   _ai_spec_matches 后字符是中文'内'时误放行
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402


class TestSpecMatchSuffixBoundary:
    """后缀边界：中文紧邻不放行，ASCII 单位后缀放行。"""

    def test_chinese_suffix_rejected(self):
        # 修复前误放行（返回 True），导致密封条顶替铜排
        assert not app_module._ai_spec_matches('6*10内卡2-3mm', '6*10')
        assert not app_module._ai_spec_matches('6*10铜排', '6*10')

    def test_ascii_unit_suffix_allowed(self):
        # mm2 是电线单位，应放行
        assert app_module._ai_spec_matches('ZB-BV-450/750V 1*10mm2 红色', '1*10')
        assert app_module._ai_spec_matches('6*10mm', '6*10')

    def test_prefix_rules_unchanged(self):
        # 回归：此前已修的规则不得破坏
        assert not app_module._ai_spec_matches('SM76*10', '6*10')
        assert not app_module._ai_spec_matches('16*100', '6*10')
        assert not app_module._ai_spec_matches('M6*10', '6*10')
        assert app_module._ai_spec_matches('6*10', '6*10')
        assert app_module._ai_spec_matches('热缩管 6*10', '6*10')  # 前空格
        assert app_module._ai_spec_matches('(6*10)', '6*10')


class TestCandidateTailWords:
    """候选词剥离：'够不够用' 剥掉后应只剩 '铜排'。"""

    def test_yong_stripped(self):
        cands = app_module._ai_extract_material_candidates('铜排够不够用')
        assert '铜排' in cands, f"'铜排' 应在候选词中：{cands}"
        assert all('用' not in c for c in cands), f"候选不应含'用'：{cands}"

    def test_normal_candidates_unchanged(self):
        cands = app_module._ai_extract_material_candidates('查一下6*10的铜排的库存')
        assert any('铜排' == c or '铜排' in c for c in cands if '\u4e00' <= c[0] <= '\u9fff'), cands
        assert any('*' in c for c in cands), f"规格候选应保留：{cands}"
