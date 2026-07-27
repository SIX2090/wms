from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.tools.registry import AI_TOOL_REGISTRY, validate_ai_tool_input


VALID_PAYLOADS = {
    'out_order_draft': {'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 2}]},
    'sales_out_draft': {'customer_id': 1, 'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 2}]},
    # 新增（AI-SALES-F01-FIX-02）：拆分 sales_out_draft
    'after_sale_out_draft': {'customer_id': 1, 'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 2}]},
    'sales_outbound_draft': {'sales_order_id': 1},
    'in_order_draft': {'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 2}]},
    'purchase_receive_draft': {'purchase_order_id': 1, 'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 2}]},
    'transfer_draft': {'source_warehouse_id': 1, 'target_warehouse_id': 2, 'items': [{'material_id': 1, 'quantity': 2}]},
    'check_draft': {'warehouse_id': 1, 'items': [{'material_id': 1, 'counted_quantity': 0}]},
    'adjustment_draft': {
        'warehouse_id': 1,
        'reason': '盘点差异人工确认',
        'items': [{'material_id': 1, 'adjustment_type': 'increase', 'quantity': 2}],
    },
    'purchase_request_draft': {'items': [{'material_id': 1, 'quantity': 2}]},
    'warehouse_insights': {'page_url': '/stock_query', 'page_title': '库存查询', 'days': 30},
    'purchase_insights': {'page_url': '/purchase_order', 'status': 'overdue', 'limit': 20},
    'replenishment_planning': {'days': 30, 'coverage_days': 30, 'risk': 'action'},
    'replenishment_smart': {'days': 30, 'coverage_days': 30, 'risk': 'all'},
    'inventory_health': {'days': 30, 'risk': 'stagnant'},
    'warehouse_patrol_agent': {'warehouse_id': 1, 'days': 7, 'max_steps': 10},
    'purchase_followup_agent': {'supplier_id': 1, 'days': 30, 'max_steps': 10},
    # 新增（AI-SALES-F02）：销售履约跟进 + 销售洞察
    'sales_followup_agent': {'customer_id': 1, 'days': 30, 'max_steps': 10},
    'sales_insights': {'page_url': '/sales_order', 'status': 'all', 'days': 30, 'limit': 20},
    'knowledge_base': {'query': '采购入库单如何确认', 'limit': 5},
    'master_data_insights': {'entity_type': 'material', 'limit': 50},
    'admin_insights': {'section': 'audit', 'days': 7},
    'alias_management': {'query': '6204轴承', 'material_id': 1},
}

DRAFT_TOOLS = {
    'out_order_draft',
    'sales_out_draft',
    # 新增（AI-SALES-F01-FIX-02）：拆分 sales_out_draft
    'after_sale_out_draft',
    'in_order_draft',
    'purchase_receive_draft',
    'transfer_draft',
    'check_draft',
    'adjustment_draft',
    'purchase_request_draft',
}


def _expect_invalid(name: str, payload: dict, label: str, failures: list[str]) -> None:
    result = validate_ai_tool_input(name, payload)
    if result.valid:
        failures.append(f'{name}: accepted invalid payload ({label})')


def main() -> int:
    failures: list[str] = []

    if set(VALID_PAYLOADS) != set(AI_TOOL_REGISTRY):
        missing = set(AI_TOOL_REGISTRY) - set(VALID_PAYLOADS)
        extra = set(VALID_PAYLOADS) - set(AI_TOOL_REGISTRY)
        failures.append(f'valid payload coverage mismatch missing={sorted(missing)} extra={sorted(extra)}')

    for name, spec in AI_TOOL_REGISTRY.items():
        schema = spec.input_schema
        if schema.get('type') != 'object':
            failures.append(f'{name}: root schema must be object')
        if schema.get('additionalProperties') is not False:
            failures.append(f'{name}: additionalProperties must be false')

        valid_payload = VALID_PAYLOADS.get(name, {})
        result = validate_ai_tool_input(name, valid_payload)
        if not result.valid:
            failures.append(f'{name}: rejected valid payload: {result.errors}')

        payload_with_extra = dict(valid_payload)
        payload_with_extra['unexpected_field'] = 'blocked'
        _expect_invalid(name, payload_with_extra, 'additional property', failures)

    for name in DRAFT_TOOLS:
        valid_payload = VALID_PAYLOADS[name]
        empty_items = dict(valid_payload)
        empty_items['items'] = []
        _expect_invalid(name, empty_items, 'empty items', failures)

    for name in DRAFT_TOOLS - {'check_draft'}:
        invalid_quantity = dict(VALID_PAYLOADS[name])
        invalid_quantity['items'] = [dict(VALID_PAYLOADS[name]['items'][0])]
        invalid_quantity['items'][0]['quantity'] = 0
        _expect_invalid(name, invalid_quantity, 'zero quantity', failures)
        invalid_quantity['items'][0]['quantity'] = -1
        _expect_invalid(name, invalid_quantity, 'negative quantity', failures)

    _expect_invalid(
        'purchase_receive_draft',
        {'warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 2}]},
        'missing purchase order',
        failures,
    )
    _expect_invalid(
        'transfer_draft',
        {'source_warehouse_id': 1, 'items': [{'material_id': 1, 'quantity': 2}]},
        'missing target warehouse',
        failures,
    )
    _expect_invalid(
        'in_order_draft',
        {'warehouse_id': 1, 'date': '2026/07/13', 'items': [{'material_id': 1, 'quantity': 2}]},
        'invalid date',
        failures,
    )
    _expect_invalid('warehouse_insights', {'limit': 0}, 'zero limit', failures)
    _expect_invalid('knowledge_base', {'query': 'x' * 501}, 'oversized query', failures)
    _expect_invalid('inventory_health', {'risk': 'unknown'}, 'invalid enum', failures)

    if failures:
        print('FAIL AI-TOOL-SCHEMAS:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-TOOL-SCHEMAS: all registered tools enforce strict fields, bounds, and non-empty draft items')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
