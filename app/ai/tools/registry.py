from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ai.policies import AI_CAPABILITY_RISK_LEVELS, AI_CAPABILITY_ROLES
from ai.schemas import SchemaValidationResult, validate_json_schema_payload


DEFAULT_INPUT_SCHEMA = MappingProxyType({
    'type': 'object',
    'additionalProperties': True,
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
    *,
    confirmation_required: bool = False,
    idempotent: bool = True,
    handler_name: str | None = None,
) -> AIToolSpec:
    risk_level = AI_CAPABILITY_RISK_LEVELS.get(name, 'read')
    return AIToolSpec(
        name=name,
        description=description,
        input_schema=DEFAULT_INPUT_SCHEMA,
        allowed_roles=AI_CAPABILITY_ROLES[name],
        risk_level=risk_level,
        confirmation_required=confirmation_required,
        idempotent=idempotent,
        audit_category=audit_category,
        handler_name=handler_name,
    )


AI_TOOL_REGISTRY = MappingProxyType({
    'out_order_draft': _tool('out_order_draft', 'Create an outbound material issue draft for manual review.', 'warehouse_draft', confirmation_required=True),
    'sales_out_draft': _tool('sales_out_draft', 'Create an after-sales outbound draft for manual review.', 'warehouse_draft', confirmation_required=True),
    'in_order_draft': _tool('in_order_draft', 'Create a general inbound draft for manual review.', 'warehouse_draft', confirmation_required=True),
    'purchase_receive_draft': _tool('purchase_receive_draft', 'Create a purchase receiving draft linked to a purchase order.', 'purchase_receive_draft', confirmation_required=True),
    'transfer_draft': _tool('transfer_draft', 'Create an internal stock transfer draft for manual review.', 'warehouse_draft', confirmation_required=True),
    'check_draft': _tool('check_draft', 'Create an inventory stocktake draft for manual review.', 'warehouse_draft', confirmation_required=True),
    'adjustment_draft': _tool('adjustment_draft', 'Create an inventory adjustment draft for manual review.', 'warehouse_draft', confirmation_required=True),
    'purchase_request_draft': _tool('purchase_request_draft', 'Create a purchase request draft for manual review.', 'purchase_draft', confirmation_required=True),
    'warehouse_insights': _tool('warehouse_insights', 'Read warehouse exceptions, stock status, pending documents, and warehouse summaries.', 'warehouse_read', handler_name='_ai_warehouse_insights_response'),
    'purchase_insights': _tool('purchase_insights', 'Read purchase workbench, supplier follow-up, and purchase exception summaries.', 'purchase_read', handler_name='_ai_purchase_insights_response'),
    'replenishment_planning': _tool('replenishment_planning', 'Read projected shortages, stock coverage, on-order quantity, and replenishment suggestions.', 'purchase_read', handler_name='_ai_replenishment_planning_response'),
    'replenishment_smart': _tool('replenishment_smart', 'Read smart replenishment suggestions with AI analysis, trend indicators, priority scores, and CSV export.', 'purchase_read'),
    'inventory_health': _tool('inventory_health', 'Read inventory health scores, shortage/overstock/stagnant risks, and optimization suggestions.', 'warehouse_read'),
    'warehouse_patrol_agent': _tool('warehouse_patrol_agent', 'Run a controlled warehouse patrol agent and persist auditable task steps.', 'agent_task', handler_name='_ai_run_warehouse_patrol_agent'),
    'purchase_followup_agent': _tool('purchase_followup_agent', 'Run a controlled purchase follow-up agent and persist auditable task steps.', 'agent_task', confirmation_required=True, handler_name='_ai_run_purchase_followup_agent'),
    'knowledge_base': _tool('knowledge_base', 'Explain WMS SOPs, page locations, status rules, fields, and report basis without replacing live data queries.', 'knowledge_read', handler_name='_ai_knowledge_response'),
    'master_data_insights': _tool('master_data_insights', 'Read material and master-data quality checks.', 'master_data_read', handler_name='_ai_master_data_insights_response'),
    'admin_insights': _tool('admin_insights', 'Read sensitive system, audit, permission, and health-check summaries.', 'admin_read', handler_name='_ai_admin_insights_response'),
    'alias_management': _tool('alias_management', 'Open or inspect AI material alias management workflows.', 'master_data_read'),
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
