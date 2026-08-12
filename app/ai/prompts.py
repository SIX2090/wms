from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


CURRENT_PROMPT_VERSION = 'legacy-v1'


@dataclass(frozen=True)
class AIPromptSpec:
    version: str
    purpose: str
    system_prompt: str


AI_PROMPTS = MappingProxyType({
    'legacy-v1': AIPromptSpec(
        version='legacy-v1',
        purpose='Compatibility prompt for the existing WMS assistant and local tool fallback.',
        system_prompt=(
            'You are a WMS business copilot. Prefer deterministic local tools for stock, '
            'documents, drafts, audits, and navigation. Never auto-submit, approve, complete, '
            'delete, or directly mutate inventory.'
            # BUG-2026-08-12-003：统一注入核心业务红线（AGENTS.md）
            '核心业务红线：'
            '1.AI只能创建草稿；提交、审核、完成、反审、作废、删除和直接改库存必须由人工在业务页面确认。'
            '2.微信文字或截图送货通知是供应商到货通知，只能生成采购入库/其他入库草稿，严禁生成采购申请。'
            '3.采购订单是采购入库的可选来源，不是强制条件；有关联订单时必须保留来源、数量与执行进度跟踪。'
            '4.所有出入库单据仓库必填；启用库位管理时库位也必填；缺少仓库/库位时必须标记待补充，不得猜测默认值。'
            '5.库存、数量、金额、单据状态必须经实时工具查询，不得编造。'
            '6.不得修改、重置或生成任何账号密码。'
        ),
    ),
})


def get_prompt_spec(version: str | None = None) -> AIPromptSpec:
    prompt_version = version or CURRENT_PROMPT_VERSION
    return AI_PROMPTS.get(prompt_version) or AI_PROMPTS[CURRENT_PROMPT_VERSION]
