"""AI 工具注册表：Schema、权限、风险级别、审计类别统一声明。
# AI_TASK: AI-R01
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ai.policies import AI_CAPABILITY_RISK_LEVELS, AI_CAPABILITY_ROLES
from ai.schemas import SchemaValidationResult, validate_json_schema_payload


def _object_schema(
    properties: Mapping[str, object],
    *,
    required: tuple[str, ...] = (),
) -> Mapping[str, object]:
    schema: dict[str, object] = {
        'type': 'object',
        'additionalProperties': False,
        'properties': dict(properties),
    }
    if required:
        schema['required'] = list(required)
    return MappingProxyType(schema)


POSITIVE_ID = {'type': 'integer', 'minimum': 1}
POSITIVE_QUANTITY = {'type': 'number', 'exclusiveMinimum': 0, 'maximum': 1_000_000_000}
NON_NEGATIVE_QUANTITY = {'type': 'number', 'minimum': 0, 'maximum': 1_000_000_000}
SHORT_TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 100}
REMARK_TEXT = {'type': 'string', 'maxLength': 500}
PAGE_URL = {'type': 'string', 'maxLength': 500}
PAGE_TITLE = {'type': 'string', 'maxLength': 200}
QUERY_TEXT = {'type': 'string', 'maxLength': 500}
DATE_TEXT = {'type': 'string', 'pattern': r'^\d{4}-\d{2}-\d{2}$'}

PAGE_CONTEXT_PROPERTIES = {
    'page_url': PAGE_URL,
    'page_title': PAGE_TITLE,
    'url': PAGE_URL,
}

STANDARD_ITEM_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['material_id', 'quantity'],
    'properties': {
        'material_id': POSITIVE_ID,
        'quantity': POSITIVE_QUANTITY,
        'warehouse_id': POSITIVE_ID,
        'location_id': POSITIVE_ID,
        'unit_id': POSITIVE_ID,
        'price': NON_NEGATIVE_QUANTITY,
        'batch_no': SHORT_TEXT,
        'serial_no': {'type': 'string', 'maxLength': 200},
        'remark': REMARK_TEXT,
    },
}

CHECK_ITEM_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['material_id', 'counted_quantity'],
    'properties': {
        'material_id': POSITIVE_ID,
        'counted_quantity': NON_NEGATIVE_QUANTITY,
        'location_id': POSITIVE_ID,
        'batch_no': SHORT_TEXT,
        'serial_no': {'type': 'string', 'maxLength': 200},
        'remark': REMARK_TEXT,
    },
}

ADJUSTMENT_ITEM_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['material_id', 'adjustment_type', 'quantity'],
    'properties': {
        'material_id': POSITIVE_ID,
        'adjustment_type': {'type': 'string', 'enum': ['increase', 'decrease']},
        'quantity': POSITIVE_QUANTITY,
        'location_id': POSITIVE_ID,
        'batch_no': SHORT_TEXT,
        'serial_no': {'type': 'string', 'maxLength': 200},
        'reason': {'type': 'string', 'minLength': 1, 'maxLength': 300},
        'remark': REMARK_TEXT,
    },
}


def _items_schema(item_schema: Mapping[str, object]) -> dict[str, object]:
    return {
        'type': 'array',
        'minItems': 1,
        'maxItems': 500,
        'items': item_schema,
    }


OUT_ORDER_DRAFT_SCHEMA = _object_schema({
    'warehouse_id': POSITIVE_ID,
    'department_id': POSITIVE_ID,
    'employee_id': POSITIVE_ID,
    'date': DATE_TEXT,
    'project_no': SHORT_TEXT,
    'remark': REMARK_TEXT,
    'items': _items_schema(STANDARD_ITEM_SCHEMA),
}, required=('warehouse_id', 'items'))

SALES_OUT_DRAFT_SCHEMA = _object_schema({
    'customer_id': POSITIVE_ID,
    'warehouse_id': POSITIVE_ID,
    'date': DATE_TEXT,
    'project_no': SHORT_TEXT,
    'remark': REMARK_TEXT,
    'items': _items_schema(STANDARD_ITEM_SCHEMA),
}, required=('customer_id', 'warehouse_id', 'items'))

# 新增（AI-SALES-F01-FIX-02）：售后出库草稿 schema，与原 SALES_OUT_DRAFT_SCHEMA 字段一致
AFTER_SALE_OUT_DRAFT_SCHEMA = SALES_OUT_DRAFT_SCHEMA

# 新增（AI-SALES-F01-FIX-02）：销售出库草稿 schema
# 与 /sales/<int:id>/create_outbound 路由对齐：以已确认销售订单为来源生成 OutOrder
# 不需要 items（系统按销售订单未发货数量自动生成），仅需订单 ID 和可选备注
SALES_OUTBOUND_DRAFT_SCHEMA = _object_schema({
    'sales_order_id': POSITIVE_ID,
    'remark': REMARK_TEXT,
}, required=('sales_order_id',))

IN_ORDER_DRAFT_SCHEMA = _object_schema({
    'supplier_id': POSITIVE_ID,
    'warehouse_id': POSITIVE_ID,
    'date': DATE_TEXT,
    'delivery_note_no': SHORT_TEXT,
    'project_no': SHORT_TEXT,
    'remark': REMARK_TEXT,
    'items': _items_schema(STANDARD_ITEM_SCHEMA),
}, required=('warehouse_id', 'items'))

PURCHASE_RECEIVE_DRAFT_SCHEMA = _object_schema({
    'purchase_order_id': POSITIVE_ID,
    'warehouse_id': POSITIVE_ID,
    'date': DATE_TEXT,
    'delivery_note_no': SHORT_TEXT,
    'remark': REMARK_TEXT,
    'items': _items_schema(STANDARD_ITEM_SCHEMA),
}, required=('purchase_order_id', 'warehouse_id', 'items'))

TRANSFER_DRAFT_SCHEMA = _object_schema({
    'source_warehouse_id': POSITIVE_ID,
    'target_warehouse_id': POSITIVE_ID,
    'date': DATE_TEXT,
    'remark': REMARK_TEXT,
    'items': _items_schema(STANDARD_ITEM_SCHEMA),
}, required=('source_warehouse_id', 'target_warehouse_id', 'items'))

CHECK_DRAFT_SCHEMA = _object_schema({
    'warehouse_id': POSITIVE_ID,
    'date': DATE_TEXT,
    'remark': REMARK_TEXT,
    'items': _items_schema(CHECK_ITEM_SCHEMA),
}, required=('warehouse_id', 'items'))

ADJUSTMENT_DRAFT_SCHEMA = _object_schema({
    'warehouse_id': POSITIVE_ID,
    'date': DATE_TEXT,
    'reason': {'type': 'string', 'minLength': 1, 'maxLength': 300},
    'remark': REMARK_TEXT,
    'items': _items_schema(ADJUSTMENT_ITEM_SCHEMA),
}, required=('warehouse_id', 'reason', 'items'))

PURCHASE_REQUEST_DRAFT_SCHEMA = _object_schema({
    'department_id': POSITIVE_ID,
    'requester_id': POSITIVE_ID,
    'required_date': DATE_TEXT,
    'project_no': SHORT_TEXT,
    'remark': REMARK_TEXT,
    'items': _items_schema(STANDARD_ITEM_SCHEMA),
}, required=('items',))

WAREHOUSE_INSIGHTS_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'query': QUERY_TEXT,
    'material_id': POSITIVE_ID,
    'warehouse_id': POSITIVE_ID,
    'status': {'type': 'string', 'enum': ['all', 'draft', 'pending', 'completed', 'exception']},
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200},
})

PURCHASE_INSIGHTS_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'query': QUERY_TEXT,
    'supplier_id': POSITIVE_ID,
    'purchase_order_id': POSITIVE_ID,
    'status': {'type': 'string', 'enum': ['all', 'pending', 'overdue', 'partial', 'completed']},
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200},
})

REPLENISHMENT_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'material_id': POSITIVE_ID,
    'warehouse_id': POSITIVE_ID,
    'supplier_id': POSITIVE_ID,
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'coverage_days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'risk': {'type': 'string', 'enum': ['action', 'all']},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200},
})

INVENTORY_HEALTH_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'material_id': POSITIVE_ID,
    'warehouse_id': POSITIVE_ID,
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'risk': {
        'type': 'string',
        'enum': ['all', 'critical', 'warning', 'healthy', 'shortage', 'overstock', 'stagnant'],
    },
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200},
})

WAREHOUSE_PATROL_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'warehouse_id': POSITIVE_ID,
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'max_steps': {'type': 'integer', 'minimum': 1, 'maximum': 50},
})

PURCHASE_FOLLOWUP_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'supplier_id': POSITIVE_ID,
    'purchase_order_id': POSITIVE_ID,
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'max_steps': {'type': 'integer', 'minimum': 1, 'maximum': 50},
})

# 新增（AI-SALES-F02）：销售侧只读洞察 schema
SALES_INSIGHTS_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'query': QUERY_TEXT,
    'customer_id': POSITIVE_ID,
    'sales_order_id': POSITIVE_ID,
    'status': {'type': 'string', 'enum': ['all', 'pending', 'overdue', 'partial', 'shipped']},
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200},
})

# 新增（AI-SALES-F02）：销售履约跟进 Agent schema
SALES_FOLLOWUP_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'customer_id': POSITIVE_ID,
    'sales_order_id': POSITIVE_ID,
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
    'max_steps': {'type': 'integer', 'minimum': 1, 'maximum': 50},
})

KNOWLEDGE_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'topic': {'type': 'string', 'maxLength': 200},
    'query': QUERY_TEXT,
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20},
})

MASTER_DATA_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'query': QUERY_TEXT,
    'entity_type': {'type': 'string', 'enum': ['all', 'material', 'supplier', 'customer', 'warehouse', 'unit', 'category']},
    'entity_id': POSITIVE_ID,
    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 200},
})

ADMIN_INSIGHTS_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'query': QUERY_TEXT,
    'section': {'type': 'string', 'enum': ['all', 'system', 'audit', 'permission', 'backup', 'ai']},
    'days': {'type': 'integer', 'minimum': 1, 'maximum': 365},
})

ALIAS_MANAGEMENT_SCHEMA = _object_schema({
    **PAGE_CONTEXT_PROPERTIES,
    'query': QUERY_TEXT,
    'material_id': POSITIVE_ID,
    'alias_id': POSITIVE_ID,
})


@dataclass(frozen=True)
class AIToolSpec:
    name: str
    description: str
    input_schema: Mapping[str, object]
    allowed_roles: frozenset[str]
    risk_level: str
    confirmation_required: bool
    idempotent: bool
    audit_category: str
    handler_name: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'input_schema': dict(self.input_schema),
            'allowed_roles': sorted(self.allowed_roles),
            'risk_level': self.risk_level,
            'confirmation_required': self.confirmation_required,
            'idempotent': self.idempotent,
            'audit_category': self.audit_category,
            'handler_name': self.handler_name,
        }


def _tool(
    name: str,
    description: str,
    audit_category: str,
    input_schema: Mapping[str, object],
    *,
    confirmation_required: bool = False,
    idempotent: bool = True,
    handler_name: str | None = None,
) -> AIToolSpec:
    risk_level = AI_CAPABILITY_RISK_LEVELS.get(name, 'read')
    return AIToolSpec(
        name=name,
        description=description,
        input_schema=input_schema,
        allowed_roles=AI_CAPABILITY_ROLES[name],
        risk_level=risk_level,
        confirmation_required=confirmation_required,
        idempotent=idempotent,
        audit_category=audit_category,
        handler_name=handler_name,
    )


AI_TOOL_REGISTRY = MappingProxyType({
    'out_order_draft': _tool('out_order_draft', 'Create an outbound material issue draft for manual review.', 'warehouse_draft', OUT_ORDER_DRAFT_SCHEMA, confirmation_required=True),
    'sales_out_draft': _tool('sales_out_draft', '[Deprecated alias of after_sale_out_draft] Create an after-sales outbound draft for manual review.', 'warehouse_draft', SALES_OUT_DRAFT_SCHEMA, confirmation_required=True),
    # 新增（AI-SALES-F01-FIX-02）：拆分 sales_out_draft 解决语义错配
    'after_sale_out_draft': _tool('after_sale_out_draft', 'Create an after-sales outbound draft (AfterSaleOutOrder) for manual review. Use this for customer returns, replacements, and warranty shipments.', 'warehouse_draft', AFTER_SALE_OUT_DRAFT_SCHEMA, confirmation_required=True),
    'sales_outbound_draft': _tool('sales_outbound_draft', 'Create a sales outbound draft (OutOrder) from a confirmed sales order for manual review. The system auto-fills items from the order\'s unshipped quantities.', 'warehouse_draft', SALES_OUTBOUND_DRAFT_SCHEMA, confirmation_required=True),
    'in_order_draft': _tool('in_order_draft', 'Create a general inbound draft for manual review.', 'warehouse_draft', IN_ORDER_DRAFT_SCHEMA, confirmation_required=True),
    'purchase_receive_draft': _tool('purchase_receive_draft', 'Create a purchase receiving draft. A purchase order is only an optional source; when linked, keep source, quantity and progress tracking.', 'purchase_receive_draft', PURCHASE_RECEIVE_DRAFT_SCHEMA, confirmation_required=True),
    'transfer_draft': _tool('transfer_draft', 'Create an internal stock transfer draft for manual review.', 'warehouse_draft', TRANSFER_DRAFT_SCHEMA, confirmation_required=True),
    'check_draft': _tool('check_draft', 'Create an inventory stocktake draft for manual review.', 'warehouse_draft', CHECK_DRAFT_SCHEMA, confirmation_required=True),
    'adjustment_draft': _tool('adjustment_draft', 'Create an inventory adjustment draft for manual review.', 'warehouse_draft', ADJUSTMENT_DRAFT_SCHEMA, confirmation_required=True),
    'purchase_request_draft': _tool('purchase_request_draft', 'Create a purchase request draft for manual review.', 'purchase_draft', PURCHASE_REQUEST_DRAFT_SCHEMA, confirmation_required=True),
    'warehouse_insights': _tool('warehouse_insights', 'Read warehouse exceptions, stock status, pending documents, and warehouse summaries.', 'warehouse_read', WAREHOUSE_INSIGHTS_SCHEMA, handler_name='_ai_warehouse_insights_response'),
    'purchase_insights': _tool('purchase_insights', 'Read purchase workbench, supplier follow-up, and purchase exception summaries.', 'purchase_read', PURCHASE_INSIGHTS_SCHEMA, handler_name='_ai_purchase_insights_response'),
    # 新增（AI-SALES-F02）：销售侧只读洞察
    'sales_insights': _tool('sales_insights', 'Read sales workbench, customer follow-up, and sales exception summaries.', 'sales_read', SALES_INSIGHTS_SCHEMA, handler_name='_ai_sales_insights_response'),
    'replenishment_planning': _tool('replenishment_planning', 'Read projected shortages, stock coverage, on-order quantity, and replenishment suggestions.', 'purchase_read', REPLENISHMENT_SCHEMA, handler_name='_ai_replenishment_planning_response'),
    'replenishment_smart': _tool('replenishment_smart', 'Read smart replenishment suggestions with AI analysis, trend indicators, priority scores, and CSV export.', 'purchase_read', REPLENISHMENT_SCHEMA),
    'inventory_health': _tool('inventory_health', 'Read inventory health scores, shortage/overstock/stagnant risks, and optimization suggestions.', 'warehouse_read', INVENTORY_HEALTH_SCHEMA),
    'warehouse_patrol_agent': _tool('warehouse_patrol_agent', 'Run a controlled warehouse patrol agent and persist auditable task steps.', 'agent_task', WAREHOUSE_PATROL_SCHEMA, handler_name='_ai_run_warehouse_patrol_agent'),
    'purchase_followup_agent': _tool('purchase_followup_agent', 'Run a controlled purchase follow-up agent and persist read-only auditable task steps.', 'agent_task', PURCHASE_FOLLOWUP_SCHEMA, handler_name='_ai_run_purchase_followup_agent'),
    # 新增（AI-SALES-F02）：销售履约跟进 Agent
    'sales_followup_agent': _tool('sales_followup_agent', 'Run a controlled sales follow-up agent and persist read-only auditable task steps. Customer messages are never sent automatically.', 'agent_task', SALES_FOLLOWUP_SCHEMA, handler_name='_ai_run_sales_followup_agent'),
    'knowledge_base': _tool('knowledge_base', 'Explain WMS SOPs, page locations, status rules, fields, and report basis without replacing live data queries.', 'knowledge_read', KNOWLEDGE_SCHEMA, handler_name='_ai_knowledge_response'),
    'master_data_insights': _tool('master_data_insights', 'Read material and master-data quality checks.', 'master_data_read', MASTER_DATA_SCHEMA, handler_name='_ai_master_data_insights_response'),
    'admin_insights': _tool('admin_insights', 'Read sensitive system, audit, permission, and health-check summaries.', 'admin_read', ADMIN_INSIGHTS_SCHEMA, handler_name='_ai_admin_insights_response'),
    'alias_management': _tool('alias_management', 'Open or inspect AI material alias management workflows.', 'master_data_read', ALIAS_MANAGEMENT_SCHEMA),
})


def get_ai_tool_spec(name: str) -> AIToolSpec | None:
    return AI_TOOL_REGISTRY.get(name)


def list_ai_tool_specs() -> list[AIToolSpec]:
    return list(AI_TOOL_REGISTRY.values())


def list_ai_tools_for_role(role: str) -> list[dict[str, Any]]:
    tools = []
    for spec in AI_TOOL_REGISTRY.values():
        if role == 'admin' or role in spec.allowed_roles:
            tools.append(spec.to_public_dict())
    return tools


def validate_ai_tool_input(name: str, payload: Any) -> SchemaValidationResult:
    spec = get_ai_tool_spec(name)
    if not spec:
        return SchemaValidationResult(False, (f'unknown tool: {name}',))
    return validate_json_schema_payload(spec.input_schema, payload)
