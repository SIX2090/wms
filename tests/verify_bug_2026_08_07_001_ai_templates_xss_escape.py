# -*- coding: utf-8 -*-
"""
BUG-2026-08-07-001 回归测试：AI 相关模板动态内容拼接 innerHTML 必须经 escapeHtml 转义

原 Bug：以下模板把后端/AI 返回的字段直接拼入 innerHTML，存在存储型 XSS 风险：
  - ai_sales_workbench.html     销售履约工作台（section.title/count/metric_scope、item.title/subtitle/detail/jump_url）
  - ai_warehouse_workbench.html 仓库工作台（同上 + 汇总计数）
  - ai_purchase_workbench.html  采购到货工作台（同上）
  - sales_order_detail.html     AI 异常分析结果（kind/message/summary/order_no/status/msg）
  - ai_business_quality.html    业务质量看板（指标 label、维度值、样本字段、版本对比）
  - ai_supplier_evaluation.html 供应商评估（ai_analysis、msg、supplier_code/name/contact 等）
  - in_order_detail.html        入库单 AI 异常提醒（a.msg / a.ai_suggestion，更早一批修复）

修复：所有动态文本统一经 base.html 全局 escapeHtml() 转义；跳转链接统一经
safeJumpUrl() 白名单校验（仅允许 / 或 http(s):// 开头，其余回退 '#'）。

测试策略（静态扫描，防回归）：
  T1. 三个 AI 工作台模板必须定义 safeJumpUrl 且 item.title/subtitle/detail 均转义
  T2. sales_order_detail.html AI 分析结果 kind/message/summary 必须转义
  T3. ai_business_quality.html 指标 label、维度值、样本字段必须转义
  T4. ai_supplier_evaluation.html ai_analysis、msg、供应商三字段必须转义
  T5. in_order_detail.html 异常提醒 a.msg / a.ai_suggestion 必须转义
  T6. 七个模板不得残留未转义的危险拼接模式（如 '+ a.msg +'、'${section.title}'）
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates"

WORKBENCHES = [
    "ai_sales_workbench.html",
    "ai_warehouse_workbench.html",
    "ai_purchase_workbench.html",
]

ALL_SEVEN = WORKBENCHES + [
    "sales_order_detail.html",
    "ai_business_quality.html",
    "ai_supplier_evaluation.html",
    "in_order_detail.html",
]


def _read(name: str) -> str:
    return (TPL / name).read_text(encoding="utf-8")


class TestBug20260807001AiTemplatesXssEscape:
    """AI 模板动态内容必须经 escapeHtml/safeJumpUrl 防护。"""

    def test_T1_workbenches_escape_items_and_safe_url(self):
        for name in WORKBENCHES:
            src = _read(name)
            assert "function safeJumpUrl(" in src, f"{name} 缺 safeJumpUrl"
            for field in ("section.title", "section.count", "item.title",
                          "item.subtitle", "item.detail"):
                assert f"escapeHtml({field})" in src, f"{name} 未转义 {field}"
            assert "safeJumpUrl(section.jump_url)" in src, f"{name} section.jump_url 未走白名单"
            assert "safeJumpUrl(item.jump_url)" in src, f"{name} item.jump_url 未走白名单"

    def test_T2_sales_order_detail_ai_analysis_escaped(self):
        src = _read("sales_order_detail.html")
        for pat in ("escapeHtml(a.kind)", "escapeHtml(a.message)",
                    "escapeHtml(d.summary || '无异常')"):
            assert pat in src, f"sales_order_detail.html 缺 {pat}"

    def test_T3_business_quality_escaped(self):
        src = _read("ai_business_quality.html")
        for pat in ("escapeHtml(m.label)", "escapeHtml(value || '(空)')",
                    "escapeHtml(sample.original_value || '-')",
                    "escapeHtml(comparison.baseline_version)"):
            assert pat in src, f"ai_business_quality.html 缺 {pat}"

    def test_T4_supplier_evaluation_escaped(self):
        src = _read("ai_supplier_evaluation.html")
        for pat in ("escapeHtml(res.ai_analysis)", "escapeHtml(e.supplier_code)",
                    "escapeHtml(e.supplier_name)", "escapeHtml(e.contact)",
                    "escapeHtml(e.price_stability)"):
            assert pat in src, f"ai_supplier_evaluation.html 缺 {pat}"

    def test_T5_in_order_detail_anomaly_escaped(self):
        src = _read("in_order_detail.html")
        assert "escapeHtml(a.msg)" in src
        assert "escapeHtml(a.ai_suggestion)" in src

    def test_T6_no_unescaped_dangerous_patterns(self):
        # 模板字面量里直接插值后端字段（未包 escapeHtml）的回归模式
        bad_patterns = [
            r"\$\{section\.title\}", r"\$\{item\.title\}", r"\$\{item\.subtitle\}",
            r"\$\{item\.detail\}", r"\$\{m\.label\}", r"\$\{sample\.id\}",
            r"\+\s*a\.msg\s*\+", r"\+\s*a\.kind\s*\+", r"\+\s*res\.ai_analysis\s*\+",
            r"\+\s*e\.supplier_name\s*\+", r"\+\s*e\.supplier_code\s*\+",
        ]
        for name in ALL_SEVEN:
            src = _read(name)
            for pat in bad_patterns:
                assert not re.search(pat, src), f"{name} 残留未转义拼接：{pat}"
