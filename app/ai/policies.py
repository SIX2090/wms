"""AI 能力权限与风险级别策略表。
# AI_TASK: AI-R01
"""
from __future__ import annotations


AI_CAPABILITY_ROLES = {
    'out_order_draft': frozenset({'warehouse'}),
    'sales_out_draft': frozenset({'warehouse', 'sales'}),
    'in_order_draft': frozenset({'warehouse'}),
    'purchase_receive_draft': frozenset({'warehouse', 'purchase'}),
    'transfer_draft': frozenset({'warehouse'}),
    'check_draft': frozenset({'warehouse'}),
    'adjustment_draft': frozenset({'warehouse'}),
    'purchase_request_draft': frozenset({'purchase'}),
    'warehouse_insights': frozenset({'warehouse'}),
    'purchase_insights': frozenset({'purchase'}),
    'warehouse_patrol_agent': frozenset({'warehouse'}),
    'purchase_followup_agent': frozenset({'purchase'}),
    'replenishment_planning': frozenset({'warehouse', 'purchase'}),
    'replenishment_smart': frozenset({'warehouse', 'purchase'}),
    'inventory_health': frozenset({'warehouse', 'purchase'}),
    'knowledge_base': frozenset({'warehouse', 'purchase', 'production', 'user'}),
    'master_data_insights': frozenset({'warehouse'}),
    'admin_insights': frozenset({'admin'}),
    'alias_management': frozenset({'warehouse', 'purchase'}),
}

AI_CAPABILITY_BUSINESS_ENDPOINTS = {
    'out_order_draft': 'add_out_order',
    'sales_out_draft': 'add_after_sale_out_order',
    'in_order_draft': 'add_in_order',
    'purchase_receive_draft': 'create_in_order_from_purchase_order',
    'transfer_draft': 'add_transfer',
    'check_draft': 'add_check',
    'adjustment_draft': 'add_adjustment',
    'purchase_request_draft': 'add_purchase_request',
    'warehouse_insights': 'stock_query',
    'purchase_insights': 'purchase_order_list',
    'warehouse_patrol_agent': 'ai_agent_run_warehouse_patrol',
    'purchase_followup_agent': 'ai_agent_run_purchase_followup',
    'replenishment_planning': 'ai_replenishment_page',
    'replenishment_smart': 'ai_replenishment_smart_page',
    'inventory_health': 'ai_inventory_health_page',
    'knowledge_base': 'ai.warehouse_assistant',
    'master_data_insights': 'material_list',
    'admin_insights': 'ai_ops_dashboard',
    'alias_management': 'ai_material_alias_list',
}


AI_CAPABILITY_RISK_LEVELS = {
    'out_order_draft': 'draft',
    'sales_out_draft': 'draft',
    'in_order_draft': 'draft',
    'purchase_receive_draft': 'draft',
    'transfer_draft': 'draft',
    'check_draft': 'draft',
    'adjustment_draft': 'draft',
    'purchase_request_draft': 'draft',
    'warehouse_insights': 'read',
    'purchase_insights': 'read',
    'warehouse_patrol_agent': 'read',
    'purchase_followup_agent': 'read',
    'replenishment_planning': 'read',
    'replenishment_smart': 'read',
    'inventory_health': 'read',
    'knowledge_base': 'read',
    'master_data_insights': 'read',
    'admin_insights': 'sensitive_read',
    'alias_management': 'read',
}

AI_AUTONOMOUS_RISK_LEVELS = frozenset({'read', 'sensitive_read'})
AI_MANUAL_CONFIRMATION_RISK_LEVELS = frozenset({'draft'})
AI_FORBIDDEN_RISK_LEVELS = frozenset({'submit', 'audit', 'complete', 'void', 'delete', 'stock_write'})

AI_HIGH_RISK_OPERATION_KEYWORDS = {
    'submit': ('提交', 'submit'),
    'audit': ('审核', '审批', '反审', 'approve', 'audit'),
    'complete': ('完成入库', '完成出库', '完成单据', '完工', 'complete'),
    'void': ('作废', '冲销', '撤销单据', 'void'),
    'delete': ('删除单据', '删除草稿', '删掉单据', 'delete'),
    'stock_write': ('直接改库存', '修改库存', '清空库存', '清库', '库存增减', 'adjust stock'),
}

AI_HIGH_RISK_REQUEST_MARKERS = (
    '帮我', '替我', '给我', '请', '立即', '直接', '自动', '马上', '现在',
    '无需确认', '不用确认', '跳过确认', '绕过确认', '执行',
)

AI_HIGH_RISK_QUESTION_MARKERS = (
    '怎么', '如何', '为什么', '能否', '可以吗', '流程', '规则', '说明', '查询', '查看',
    '失败', '报错', '不能', '无法', '状态',
)


def ai_capability_requires_manual_confirmation(capability: str) -> bool:
    return AI_CAPABILITY_RISK_LEVELS.get(capability) in AI_MANUAL_CONFIRMATION_RISK_LEVELS


def is_ai_risk_level_autonomous(risk_level: str) -> bool:
    return risk_level in AI_AUTONOMOUS_RISK_LEVELS


def detect_ai_high_risk_operation(message: str) -> str | None:
    compact = ''.join(str(message or '').lower().split())
    if not compact:
        return None
    matched_operation = None
    matched_keywords: tuple[str, ...] = ()
    for operation, keywords in AI_HIGH_RISK_OPERATION_KEYWORDS.items():
        if any(keyword.lower() in compact for keyword in keywords):
            matched_operation = operation
            matched_keywords = keywords
            break
    if not matched_operation:
        return None
    explicit_request = any(
        f'{marker}{keyword.lower()}' in compact
        for marker in AI_HIGH_RISK_REQUEST_MARKERS
        for keyword in matched_keywords
    ) or any(
        f'{keyword.lower()}{suffix}' in compact
        for keyword in matched_keywords
        for suffix in ('一下', '掉', '了', '单据', '这张单', '这个单')
    )
    if any(marker in compact for marker in AI_HIGH_RISK_QUESTION_MARKERS) and not explicit_request:
        return None
    return matched_operation


def effective_ai_capability_roles(
    capability: str,
    business_roles: frozenset[str] | None = None,
) -> frozenset[str]:
    '''Return declared roles narrowed by the mapped business route roles.'''
    declared_roles = AI_CAPABILITY_ROLES.get(capability, frozenset())
    if business_roles is None:
        return declared_roles
    return declared_roles.intersection(business_roles)


def is_ai_capability_allowed_for_role(
    capability: str,
    role: str,
    business_roles: frozenset[str] | None = None,
) -> bool:
    """Return whether a business role may use a declared AI capability."""
    if capability not in AI_CAPABILITY_ROLES:
        return False
    return role == 'admin' or role in effective_ai_capability_roles(capability, business_roles)
