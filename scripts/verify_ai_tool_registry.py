from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-tool-registry-secret'
sys.path.insert(0, str(APP_DIR))

from ai.policies import AI_CAPABILITY_ROLES, is_ai_capability_allowed_for_role
from ai.tools.registry import AI_TOOL_REGISTRY, list_ai_tool_specs, list_ai_tools_for_role


ROLES = ('admin', 'warehouse', 'purchase', 'production', 'user')


def main() -> int:
    failures: list[str] = []

    if len(list_ai_tool_specs()) != len(AI_TOOL_REGISTRY):
        failures.append('list_ai_tool_specs does not return every registered tool')

    for name, spec in AI_TOOL_REGISTRY.items():
        public = spec.to_public_dict()
        required = {
            'name',
            'description',
            'input_schema',
            'allowed_roles',
            'risk_level',
            'confirmation_required',
            'idempotent',
            'audit_category',
            'handler_name',
        }
        missing = required - set(public)
        if missing:
            failures.append(f'{name}: public schema missing keys {sorted(missing)}')
        if public['name'] != name:
            failures.append(f'{name}: public schema name mismatch')
        if public['allowed_roles'] != sorted(AI_CAPABILITY_ROLES[name]):
            failures.append(f'{name}: public allowed_roles mismatch')

    expected_handlers = {
        'warehouse_insights': '_ai_warehouse_insights_response',
        'purchase_insights': '_ai_purchase_insights_response',
        'master_data_insights': '_ai_master_data_insights_response',
        'admin_insights': '_ai_admin_insights_response',
    }
    for name, handler_name in expected_handlers.items():
        spec = AI_TOOL_REGISTRY.get(name)
        if not spec or spec.handler_name != handler_name:
            failures.append(f'{name}: expected handler_name {handler_name}, got {getattr(spec, "handler_name", None)}')

    for role in ROLES:
        visible_names = {tool['name'] for tool in list_ai_tools_for_role(role)}
        expected_names = {
            name
            for name in AI_CAPABILITY_ROLES
            if is_ai_capability_allowed_for_role(name, role)
        }
        if visible_names != expected_names:
            failures.append(
                f'{role}: visible tools mismatch, expected {sorted(expected_names)}, got {sorted(visible_names)}'
            )

    if failures:
        print('FAIL AI-TOOL-REGISTRY:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-TOOL-REGISTRY: public tool metadata and role-filtered listings match policies')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
