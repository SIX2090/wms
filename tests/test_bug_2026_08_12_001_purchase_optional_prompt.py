# -*- coding: utf-8 -*-
"""BUG-2026-08-12-001 回归：AI 知识库与工具描述不得宣称"采购入库必须关联采购订单"。

规则依据（AGENTS.md）：采购订单仅作为可选来源，采购入库允许手工新增、
编辑、保存和完成；有关联订单时保留来源、数量和执行进度跟踪。
后端强制校验已由 purchase_in_order_requires_order() 开关守卫且默认停用
（BUG-2026-08-02-019），本测试锁定提示词/知识层表述不再回退。
"""
from __future__ import annotations

from ai.knowledge import AI_KNOWLEDGE_BASE
from ai.tools.registry import get_ai_tool_spec


def test_knowledge_base_has_no_mandatory_purchase_order_rule():
    """知识库任何条目都不得宣称采购入库强制关联采购订单。"""
    for entry in AI_KNOWLEDGE_BASE:
        assert '采购入库必须关联采购订单' not in entry.rule, entry.key
        assert '采购入库必须关联采购订单' not in entry.summary, entry.key


def test_purchase_receive_sop_rule_states_optional_source():
    """采购到货入库 SOP 必须明确采购订单是可选来源，并保留来源/数量/进度跟踪。"""
    entry = next(e for e in AI_KNOWLEDGE_BASE if e.key == 'purchase_receive_sop')
    assert '可选来源' in entry.rule
    assert '手工新增' in entry.rule
    assert '执行进度跟踪' in entry.rule
    # 送货单只能生成草稿的红线必须保留
    assert '不能直接完成入库' in entry.rule


def test_purchase_receive_draft_tool_description_states_optional_source():
    """purchase_receive_draft 工具描述不得暗示必须关联采购订单。"""
    spec = get_ai_tool_spec('purchase_receive_draft')
    assert spec is not None
    assert 'linked to a purchase order' not in spec.description
    assert 'optional source' in spec.description
    assert 'tracking' in spec.description
