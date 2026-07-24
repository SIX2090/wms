from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-permission-matrix-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.tools.registry import AI_TOOL_REGISTRY


ROLES = ('admin', 'warehouse', 'purchase', 'sales', 'production', 'user')

EXPECTED = {
    'out_order_draft': {'admin', 'warehouse'},
    # sales_out_draft / after_sale_out_draft 策略含 sales，但业务路由 add_after_sale_out_order 仅 warehouse，运行时收窄后 sales 不可用
    'sales_out_draft': {'admin', 'warehouse'},
    # 新增（AI-SALES-F01-FIX-02）：拆分 sales_out_draft
    'after_sale_out_draft': {'admin', 'warehouse'},
    # create_sales_outbound_draft 业务路由含 sales，与策略交集后 sales 可用
    'sales_outbound_draft': {'admin', 'warehouse', 'sales'},
    'in_order_draft': {'admin', 'warehouse'},
    'purchase_receive_draft': {'admin', 'warehouse', 'purchase'},
    'transfer_draft': {'admin', 'warehouse'},
    'check_draft': {'admin', 'warehouse'},
    'adjustment_draft': {'admin', 'warehouse'},
    'purchase_request_draft': {'admin', 'purchase'},
    'warehouse_insights': {'admin', 'warehouse'},
    'purchase_insights': {'admin', 'purchase'},
    # 新增（AI-SALES-F02 / AI-AUTH-002）：销售只读洞察与跟进 Agent 必须纳入自动化覆盖
    'sales_insights': {'admin', 'sales'},
    'sales_followup_agent': {'admin', 'sales'},
    'replenishment_planning': {'admin', 'warehouse', 'purchase'},
    'replenishment_smart': {'admin', 'warehouse', 'purchase'},
    'inventory_health': {'admin', 'warehouse', 'purchase'},
    'warehouse_patrol_agent': {'admin', 'warehouse'},
    'purchase_followup_agent': {'admin', 'purchase'},
    'knowledge_base': {'admin', 'warehouse', 'purchase', 'production', 'user'},
    'master_data_insights': {'admin', 'warehouse'},
    'admin_insights': {'admin'},
    'alias_management': {'admin', 'warehouse', 'purchase'},
}


def allowed_for(role: str, capability: str) -> bool:
    user = wms_app.User(
        id=1000 + ROLES.index(role),
        username=f'verify-{role}',
        role=role,
        status='normal',
    )
    with wms_app.app.test_request_context('/_verify/ai-permission-matrix'):
        wms_app.login_user(user)
        return bool(wms_app._ai_capability_allowed(capability))


def _ensure_rollout_all() -> None:
    """测试默认使用 all 模式以隔离角色权限矩阵检查（F01 默认 off）。"""
    with wms_app.app.app_context():
        wms_app.db.create_all()
        wms_app.set_system_setting('ai_feature_rollout_mode', 'all')
        wms_app.db.session.commit()


def main() -> int:
    _ensure_rollout_all()
    actual_capabilities = set(wms_app.AI_CAPABILITY_ROLES)
    expected_capabilities = set(EXPECTED)
    registered_capabilities = set(AI_TOOL_REGISTRY)
    failures: list[str] = []

    missing = expected_capabilities - actual_capabilities
    extra = actual_capabilities - expected_capabilities
    if missing:
        failures.append(f'missing capabilities: {sorted(missing)}')
    if extra:
        failures.append(f'unexpected capabilities without test coverage: {sorted(extra)}')
    if registered_capabilities != actual_capabilities:
        failures.append(
            'tool registry capabilities do not match policy capabilities: '
            f'registry={sorted(registered_capabilities)}, policy={sorted(actual_capabilities)}'
        )

    for capability, allowed_roles in sorted(EXPECTED.items()):
        spec = AI_TOOL_REGISTRY.get(capability)
        if spec is None:
            failures.append(f'{capability}: missing from AI_TOOL_REGISTRY')
            continue
        if set(spec.allowed_roles) != set(wms_app.AI_CAPABILITY_ROLES[capability]):
            failures.append(f'{capability}: registry allowed_roles differs from policy')
        if capability.endswith('_draft') and spec.risk_level != 'draft':
            failures.append(f'{capability}: draft tool must have draft risk level')
        if capability.endswith('_draft') and not spec.confirmation_required:
            failures.append(f'{capability}: draft tool must require confirmation')
        for role in ROLES:
            expected = role in allowed_roles
            actual = allowed_for(role, capability)
            if actual != expected:
                failures.append(
                    f'{capability}/{role}: expected {expected}, got {actual}'
                )

    for role in ROLES:
        if allowed_for(role, 'unknown_capability_for_verification'):
            failures.append(f'unknown capability was allowed for role {role}')

    if failures:
        print('FAIL AI-PERMISSION-MATRIX:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-PERMISSION-MATRIX: roles, known capabilities, and unknown capability denial are enforced')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
