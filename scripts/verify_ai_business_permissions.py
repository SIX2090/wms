from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-business-permissions-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.policies import AI_CAPABILITY_BUSINESS_ENDPOINTS, effective_ai_capability_roles


EXPECTED_RESTRICTED_ROLES = {
    'out_order_draft': frozenset({'warehouse'}),
    'sales_out_draft': frozenset({'warehouse'}),
    'in_order_draft': frozenset({'warehouse'}),
    'purchase_receive_draft': frozenset({'warehouse', 'purchase'}),
    'transfer_draft': frozenset({'warehouse'}),
    'check_draft': frozenset({'warehouse'}),
    'adjustment_draft': frozenset({'warehouse'}),
    'purchase_request_draft': frozenset({'purchase'}),
    'warehouse_patrol_agent': frozenset({'warehouse'}),
    'purchase_followup_agent': frozenset({'purchase'}),
    'replenishment_planning': frozenset({'warehouse', 'purchase'}),
    'replenishment_smart': frozenset({'warehouse', 'purchase'}),
    'inventory_health': frozenset({'warehouse', 'purchase'}),
    'admin_insights': frozenset({'admin'}),
    'alias_management': frozenset({'warehouse', 'purchase'}),
}


def login_client(user_id: int):
    client = wms_app.app.test_client()
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True
    return client


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    failures: list[str] = []

    if set(AI_CAPABILITY_BUSINESS_ENDPOINTS) != set(wms_app.AI_CAPABILITY_ROLES):
        failures.append('every AI capability must map to one business endpoint')

    for capability, endpoint in sorted(AI_CAPABILITY_BUSINESS_ENDPOINTS.items()):
        view = app.view_functions.get(endpoint)
        if view is None:
            failures.append(f'{capability}: missing business endpoint {endpoint}')
            continue
        route_roles = getattr(view, '_required_roles', None)
        expected_roles = EXPECTED_RESTRICTED_ROLES.get(capability)
        if expected_roles is not None and route_roles != expected_roles:
            failures.append(
                f'{capability}: expected route roles {sorted(expected_roles)}, '
                f'got {sorted(route_roles or ())}'
            )
        effective_roles = effective_ai_capability_roles(capability, route_roles)
        if route_roles is not None and not effective_roles.issubset(route_roles):
            failures.append(f'{capability}: effective AI roles exceed business route roles')

    with app.test_request_context('/_verify/ai-business-permissions'):
        production = wms_app.User(
            id=9101,
            username='verify-production',
            role='production',
            status='normal',
        )
        wms_app.login_user(production)
        if wms_app._ai_capability_allowed('out_order_draft'):
            failures.append('production must not create outbound drafts through AI')

    with app.test_request_context('/_verify/ai-business-permissions'):
        warehouse = wms_app.User(
            id=9102,
            username='verify-warehouse',
            role='warehouse',
            status='normal',
        )
        wms_app.login_user(warehouse)
        if wms_app._ai_capability_allowed('purchase_request_draft'):
            failures.append('warehouse must not create purchase request drafts through AI')

    with app.app_context():
        wms_app.db.create_all()
        usernames = (
            'verify-business-warehouse',
            'verify-business-purchase',
            'verify-business-production',
        )
        wms_app.User.query.filter(wms_app.User.username.in_(usernames)).delete(
            synchronize_session=False
        )
        users = [
            wms_app.User(
                username=usernames[0],
                password_hash='not-used',
                role='warehouse',
                status='normal',
            ),
            wms_app.User(
                username=usernames[1],
                password_hash='not-used',
                role='purchase',
                status='normal',
            ),
            wms_app.User(
                username=usernames[2],
                password_hash='not-used',
                role='production',
                status='normal',
            ),
        ]
        wms_app.db.session.add_all(users)
        wms_app.db.session.commit()
        warehouse_id, purchase_id, production_id = (user.id for user in users)

    wrong_role_requests = (
        (
            login_client(warehouse_id).post(
                '/ai/agent_tasks/run/purchase_followup',
                headers={'Accept': 'application/json'},
            ),
            'warehouse purchase-followup route',
        ),
        (
            login_client(purchase_id).post(
                '/ai/agent_tasks/run/warehouse_patrol',
                headers={'Accept': 'application/json'},
            ),
            'purchase warehouse-patrol route',
        ),
        (
            login_client(production_id).get(
                '/ai/material_alias',
                headers={'Accept': 'application/json'},
            ),
            'production alias-management route',
        ),
    )
    for response, label in wrong_role_requests:
        if response.status_code != 403:
            failures.append(f'{label} expected 403, got {response.status_code}')

    if failures:
        print('FAIL AI-BUSINESS-PERMISSIONS:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-BUSINESS-PERMISSIONS: AI capabilities are bounded by business route roles')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
