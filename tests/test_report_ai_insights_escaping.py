# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011-F02：报表 AI 洞察必须转义后再拼 innerHTML。

LLM 返回内容属外部不可信输入（模型可能复述业务数据里的 <img onerror>）。
本用例是静态契约：模板一旦回退到未转义拼接，必须失败。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app' / 'templates' / 'report_dashboard.html'


def test_insights_lines_are_escaped():
    text = TEMPLATE.read_text(encoding='utf-8')
    assert "escapeHtml(line.replace(" in text
    assert "' + line.replace(" not in text


def test_error_messages_are_escaped():
    text = TEMPLATE.read_text(encoding='utf-8')
    assert "escapeHtml(res.msg || '生成失败')" in text
    assert "escapeHtml(err.message || '未知错误')" in text
