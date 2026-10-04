# -*- coding: utf-8 -*-
"""AI-PROMPT-V2-2026-10-04 回归守护：用户消息结构化截断 + 意图输出契约。

修复前：``user_message[:1000]`` 硬截断——长文本（多行送货单、长问题）后半段
静默丢失，且模型不知道数据不全，会把"没传过来"当"不存在"。

修复约定（本测试锁死）：
1. 短消息原样通过；长消息保留首尾 + 显式截断标记（告知模型数据不完整）。
2. call_llm_intent 的 system prompt 必须追加意图输出契约（JSON 字段 +
   unknown 兜底 + 禁止猜测）。
"""
from __future__ import annotations

from types import SimpleNamespace

from ai import providers


def test_short_message_passes_through():
    text = '查 A001 库存'
    assert providers.truncate_ai_user_message(text) == text


def test_long_message_keeps_head_and_tail_with_marker():
    head_part = '送货单 供应商：鑫达五金 日期：2026-10-04\n' + '明细行：' + '轴承 100套\n' * 200
    tail_part = '最后一行：M8螺母 500个，共 87 行明细，请核对'
    text = head_part + tail_part
    assert len(text) > 1000
    out = providers.truncate_ai_user_message(text)
    assert len(out) <= 1000
    assert out.startswith('送货单 供应商：鑫达五金'), '首段（表头信息）必须保留'
    assert out.endswith('请核对'), '尾段（末尾物料行/落款）必须保留'
    assert '已截断' in out, '必须含显式截断标记'
    assert '不得假设数据完整' in out, '标记必须告知模型数据不完整'


def test_marker_forbids_fabrication():
    """截断标记必须禁止模型臆造缺失部分。"""
    text = 'x' * 5000
    out = providers.truncate_ai_user_message(text)
    assert '待补充' in out and '禁止臆造' in out


def test_hard_truncation_removed_from_call_sites():
    """providers.py 不得再出现 [:1000] 硬截断（回归锁）。"""
    import inspect

    src = inspect.getsource(providers)
    assert 'user_message[:1000]' not in src, (
        'call_llm_intent/call_llm_chat 仍存在 [:1000] 硬截断'
    )


def test_intent_call_appends_output_contract(monkeypatch):
    """call_llm_intent 必须给 system prompt 追加 JSON 输出契约 + unknown 兜底。"""
    captured = {}

    def fake_call_llm(config, messages, **kwargs):
        captured['messages'] = messages
        return '{"intent": "unknown", "params": {}}'

    monkeypatch.setattr(providers, 'call_llm', fake_call_llm)
    config = SimpleNamespace(timeout_seconds=5)
    result = providers.call_llm_intent(config, '你是意图解析器。', '你好')

    assert result == {'intent': 'unknown', 'params': {}}
    system_content = captured['messages'][0]['content']
    assert '你是意图解析器。' in system_content, '调用方原始 prompt 必须保留'
    assert '"intent"' in system_content and '"params"' in system_content, '缺少 JSON 字段契约'
    assert 'unknown' in system_content, '缺少 unknown 兜底意图'
    assert '禁止猜测' in system_content, '缺少禁止猜测约束'
    user_content = captured['messages'][1]['content']
    assert user_content == '你好', '短消息不得被截断逻辑改动'


def test_intent_contract_forbids_high_risk_actions():
    """契约必须覆盖高风险人工操作的拒答路径（对接 copilot-v2 红线 1）。"""
    assert '提交' in providers._INTENT_OUTPUT_CONTRACT
    assert '删除' in providers._INTENT_OUTPUT_CONTRACT
