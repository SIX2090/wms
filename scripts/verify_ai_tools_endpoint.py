from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-tools-endpoint-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.tools.registry import list_ai_tools_for_role


def login_as(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = {}
        for role in ('admin', 'warehouse', 'user'):
            user = wms_app.User(
                username=f'tools-endpoint-{role}',
                password_hash='not-used',
                role=role,
                status='normal',
            )
            wms_app.db.session.add(user)
            wms_app.db.session.flush()
            users[role] = user.id
        wms_app.db.session.commit()

    client = app.test_client()
    failures: list[str] = []

    anonymous = client.get('/api/ai/tools')
    if anonymous.status_code not in (302, 401):
        failures.append(f'anonymous request should require login, got {anonymous.status_code}')

    for role, user_id in users.items():
        login_as(client, user_id)
        response = client.get('/api/ai/tools')
        if response.status_code != 200:
            failures.append(f'{role}: expected 200, got {response.status_code}')
            continue
        payload = response.get_json() or {}
        expected_tools = list_ai_tools_for_role(role)
        if payload.get('status') != 'success':
            failures.append(f'{role}: status is not success')
        if payload.get('role') != role:
            failures.append(f'{role}: response role mismatch')
        if payload.get('tools') != expected_tools:
            failures.append(f'{role}: tools payload differs from registry filter')
        for tool in payload.get('tools') or []:
            if 'allowed_roles' not in tool or 'input_schema' not in tool:
                failures.append(f'{role}/{tool.get("name")}: missing public metadata')

    if failures:
        print('FAIL AI-TOOLS-ENDPOINT:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-TOOLS-ENDPOINT: authenticated users receive role-filtered AI tool metadata')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
