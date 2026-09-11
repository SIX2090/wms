# -*- coding: utf-8 -*-
"""AI 名实对齐（P0-1 / AI-NAMING-TRUTH-001）回归。

背景：诊断报告（WMS_BUSINESS_AI_DIAGNOSIS.md §4.1）证实 319 个 _ai_* 函数中
仅 18 个真调 LLM；补货/库存健康等页面为纯规则实现，但标题带"AI/智能"，
违反"结论是否模型生成"的命名原则（AGENTS.md R5 的信任前提）。

修复原则（非一刀切）：
- 纯规则页面/列 → 去掉 AI/智能 字样，标注"规则判断，非模型生成"；
- 真 LLM 链路（供应商评估、单据 OCR、单据异常 AI 建议）→ 保留 AI 字样。

本文件断言三层一致：模板文案、后端 CSV 导出表头、导航入口。
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")


def _tpl(name: str) -> str:
    return (APP_DIR / "templates" / name).read_text(encoding="utf-8", errors="ignore")


def _app_py() -> str:
    return (APP_DIR / "app.py").read_text(encoding="utf-8", errors="ignore")


def _base_html() -> str:
    return _tpl("base.html")


def test_t1_smart_page_table_header_not_ai():
    """T1: 规则补货页表头不得再叫『AI建议』。"""
    html = _tpl("ai_replenishment_smart.html")
    assert "AI建议" not in html, "规则生成的建议列不得标注为 AI建议"
    assert "系统建议" in html


def test_t2_smart_page_declares_rule_basis():
    """T2: 规则补货页必须明示依据（规则判断，非模型生成）。"""
    html = _tpl("ai_replenishment_smart.html")
    assert ("规则" in html) and ("非模型生成" in html), "页面必须标注建议依据为规则判断"


def test_t3_smart_page_title_no_ai_claim():
    """T3: 规则补货页标题不得自称『智能/AI』。"""
    html = _tpl("ai_replenishment_smart.html")
    assert "智能补货建议" not in html
    assert "基于AI分析" not in html


def test_t4_csv_export_header_matches_template():
    """T4: CSV 导出表头与模板表头必须一致（系统建议）。"""
    src = _app_py()
    assert "'系统建议'" in src, "app.py CSV 导出表头应为『系统建议』"
    assert "f'近{days}天出库'" in src  # 定位导出代码块仍存在
    # 导出列表里不得残留 'AI建议'
    export_block = src[src.index("writer.writerow(["):]
    assert "'AI建议'" not in export_block.split("writer.writerows")[0] or "'AI建议'" not in src


def test_t5_document_anomaly_keeps_ai_label():
    """T5: 单据异常『AI建议』是真 LLM 输出（in_order.py:1467 调 _ai_call_llm_chat），必须保留。"""
    assert "AI建议" in _tpl("in_order_detail.html")
    assert "AI建议" in _tpl("out_order_detail.html")
    # 且后端链路确实存在 LLM 调用（证明保留是对的，防止未来误删）
    in_order_src = (APP_DIR / "routes" / "in_order.py").read_text(encoding="utf-8", errors="ignore")
    assert "_ai_call_llm_chat(prompt)" in in_order_src


def test_t6_supplier_evaluation_keeps_ai_wording():
    """T6: 供应商评估是真 LLM 链路，『智能』字样必须保留（证明不是无脑全删）。"""
    html = _tpl("ai_supplier_evaluation.html")
    assert "供应商智能评估" in html


def test_t7_plain_pages_titles_honest():
    """T7: 另两个规则页标题不得自称 AI（副标题本已如实描述规则依据）。"""
    assert "AI补货建议" not in _tpl("ai_replenishment.html")
    assert "AI库存健康度" not in _tpl("ai_inventory_health.html")


def test_t8_nav_no_smart_replenishment_claim():
    """T8: 导航浮层同步改名（智能补货建议 → 补货建议（规则））。"""
    base = _base_html()
    assert "智能补货建议" not in base
    assert "补货建议（规则）" in base
    # 真 LLM 入口保留原名
    assert "供应商智能评估" in base
    assert "智能库位推荐" in base


def test_t9_llm_gate_note_in_matrix():
    """T9: AI-LLM-GATE-002 补登记已写入矩阵文档（与 P0-4 同批的台账要求）。"""
    matrix = (ROOT / "AI_PERMISSION_MATRIX.md").read_text(encoding="utf-8", errors="ignore")
    assert "AI-LLM-GATE-002" in matrix
    assert "supplier_evaluation" in matrix
    assert "location_recommendation" in matrix
    assert "demand_forecast" in matrix
