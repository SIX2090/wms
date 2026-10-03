# -*- coding: utf-8 -*-
"""WMS-AI-HINT-001 回归测试：供应商评估数据稀疏置信度提示（2026-10-03）。

背景（AI 功能实用性审计 P2-2）：供应商智能评估基于近 90 天采购订单，
单人小仓数据稀疏时评分置信度低，页面此前无任何提示，易被当作决策依据。

测试用例：
  T1. ai_supplier_evaluation.html 页头下方必须含数据稀疏置信度提示
"""
from __future__ import annotations

import re
from pathlib import Path

TPL = Path(__file__).resolve().parent.parent / "app" / "templates" / "ai_supplier_evaluation.html"


def test_supplier_eval_data_sparsity_hint():
    html = TPL.read_text(encoding="utf-8")
    m = re.search(r'alert alert-info.*?置信度较低，仅供参考', html, re.S)
    assert m, "供应商评估页缺少数据稀疏置信度提示（WMS-AI-HINT-001）"
    assert "近 90 天" in m.group(0), "提示未说明数据口径（近 90 天）"
