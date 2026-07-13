from __future__ import annotations


AI_CAPABILITY_ROLES = {
    'out_order_draft': frozenset({'warehouse', 'production'}),
    'sales_out_draft': frozenset({'warehouse'}),
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

AI_CAPABILITY_RISK_LEVELS = {
    'out_order_draft': 'draft',
    'sales_out_draft': 'draft',
    'in_order_draft': 'draft',
    'purchase_receive_draft': 'draft',
    'transfer_draft': 'draft',
    'check_draft': 'draft',
    'adjustment_draft': 'draft',
    'purchase_request_draft': 'draft',
    'warehouse_patrol_agent': 'read',
    'purchase_followup_agent': 'draft',
    'replenishment_planning': 'read',
    'replenishment_smart': 'read',
    'inventory_health': 'read',
    'knowledge_base': 'read',
    'admin_insights': 'sensitive_read',
}


def is_ai_capability_allowed_for_role(capability: str, role: str) -> bool:
    """Return whether a business role may use a declared AI capability."""
    if capability not in AI_CAPABILITY_ROLES:
        return False
    return role == 'admin' or role in AI_CAPABILITY_ROLES[capability]
