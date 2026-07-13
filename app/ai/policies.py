from __future__ import annotations


AI_CAPABILITY_ROLES = {
    'out_order_draft': frozenset({'warehouse'}),
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
    'warehouse_patrol_agent': 'read',
    'purchase_followup_agent': 'draft',
    'replenishment_planning': 'read',
    'replenishment_smart': 'read',
    'inventory_health': 'read',
    'knowledge_base': 'read',
    'admin_insights': 'sensitive_read',
}


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
