# -*- coding: utf-8 -*-
"""BUG-2026-08-12-003 回归：统一系统提示词必须注入核心业务红线。

规则依据（AGENTS.md）：AI 只能创建草稿，提交/审核/完成/作废/删除保持人工；
微信送货通知必须生成入库草稿而非采购申请；采购订单仅为可选来源；
仓库始终必填；库存数据必须实时查询不得编造；AI 不得修改/重置任何账号密码。

同时锁定 app.py 两条聊天提示词链路（_ai_call_llm_chat 与流式聊天路由）
必须以 get_prompt_spec().system_prompt 为基础约束。
"""
from __future__ import annotations

import inspect
from pathlib import Path

from ai.prompts import CURRENT_PROMPT_VERSION, get_prompt_spec

APP_PY = Path(__file__).resolve().parent.parent / 'app' / 'app.py'

REDLINE_KEYWORDS = (
    '只能创建草稿',
    '人工在业务页面确认',
    '送货通知',
    '严禁生成采购申请',
    '可选来源',
    '仓库必填',
    '不得编造',
    '密码',
)


def test_unified_prompt_keeps_english_safety_boundary():
    """verify_ai_platform_foundations.py 依赖的英文安全边界不得丢失。"""
    prompt = get_prompt_spec()
    assert prompt.version == CURRENT_PROMPT_VERSION
    assert 'Never auto-submit' in prompt.system_prompt


def test_unified_prompt_contains_core_redlines():
    """统一系统提示词必须包含全部核心业务红线关键词。"""
    text = get_prompt_spec().system_prompt
    for keyword in REDLINE_KEYWORDS:
        assert keyword in text, f'统一提示词缺少红线: {keyword}'


def test_app_call_llm_chat_prompt_chains_unified_redlines():
    """_ai_call_llm_chat 的系统提示词必须以统一提示词为基础约束。"""
    import app as wms_app

    src = inspect.getsource(wms_app._ai_call_llm_chat)
    assert 'get_prompt_spec().system_prompt' in src


def test_app_streaming_chat_prompt_chains_unified_redlines():
    """流式聊天路由的系统提示词同样必须接入统一提示词（两处链路都覆盖）。"""
    source = APP_PY.read_text(encoding='utf-8')
    # 非流式(_ai_call_llm_chat) + 流式(多轮上下文) 两条聊天链路都必须拼接统一提示词
    assert source.count('get_prompt_spec().system_prompt') >= 2
