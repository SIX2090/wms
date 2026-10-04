# -*- coding: utf-8 -*-
"""AI-PROMPT-V2-2026-10-04 回归守护：copilot-v2 结构化 prompt 必须就位并生效。

背景：legacy-v1 三条缺陷——①红线是口号没有行为指令；②R5「低置信度必须回退
人工」只写在 AGENTS.md，运行时 prompt 未注入；③无输出格式契约。v2 修复之。

兼容性：tests/test_bug_2026_08_12_003_system_prompt_redlines.py 锁定的
'Never auto-submit' 与 8 个红线关键词，v2 必须全部保留（本测试显式复核，
防止为"写得更好"而把被锁定的语义写丢）。
"""
from __future__ import annotations

from ai.prompts import AI_PROMPTS, CURRENT_PROMPT_VERSION, get_prompt_spec


def test_v2_registered_and_current():
    assert 'copilot-v2' in AI_PROMPTS, 'copilot-v2 未注册进 AI_PROMPTS'
    assert CURRENT_PROMPT_VERSION == 'copilot-v2', (
        f'CURRENT_PROMPT_VERSION 应为 copilot-v2，实际 {CURRENT_PROMPT_VERSION}'
    )
    assert get_prompt_spec().version == 'copilot-v2'


def test_v2_keeps_locked_safety_keywords():
    """BUG-2026-08-12-003 锁定的英文边界与红线关键词一个都不能少。"""
    text = get_prompt_spec().system_prompt
    assert 'Never auto-submit' in text, '英文安全边界丢失（verify_ai_platform_foundations 依赖）'
    for keyword in (
        '只能创建草稿', '人工在业务页面确认', '送货通知', '严禁生成采购申请',
        '可选来源', '仓库必填', '不得编造', '密码',
    ):
        assert keyword in text, f'v2 丢失被锁定红线: {keyword}'


def test_v2_has_fallback_obligation():
    """R5 运行时义务：查不到要如实说、低置信度要标待核对、越界要拒答。"""
    text = get_prompt_spec().system_prompt
    assert '我没查到' in text, '缺少"查不到如实说"的回退指令'
    assert '待人工核对' in text, '缺少低置信度标注义务（R5）'
    assert '这个我做不了' in text, '缺少能力边界拒答指令'


def test_v2_has_output_contract():
    """输出契约：草稿不多加字段、缺失标 null、禁止猜默认值。"""
    text = get_prompt_spec().system_prompt
    assert 'JSON schema' in text, '缺少结构化输出契约'
    assert 'null' in text and '待补充' in text, '缺失字段处理契约丢失'
    assert '禁止填猜测的默认值' in text, '禁止猜测默认值的约束丢失'


def test_v2_redlines_are_behavioral():
    """红线必须是行为指令而非口号：人工操作请求要给出明确应答方式。"""
    text = get_prompt_spec().system_prompt
    assert '请在业务页面人工操作' in text, (
        '人工操作类请求的固定应答缺失——光说"不许做"模型仍会尝试执行'
    )
