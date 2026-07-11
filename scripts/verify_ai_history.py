from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-history-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.history import append_history, clear_history, get_history


def login_as(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        user = wms_app.User(
            username='history-endpoint-user',
            password_hash='not-used',
            role='user',
            status='normal',
        )
        other_user = wms_app.User(
            username='history-endpoint-other',
            password_hash='not-used',
            role='warehouse',
            status='normal',
        )
        wms_app.db.session.add_all([user, other_user])
        wms_app.db.session.flush()
        user_id = user.id
        other_user_id = other_user.id
        wms_app.db.session.commit()

    clear_history(user_id)
    clear_history(other_user_id)
    append_history(user_id, 'user', 'hello')
    append_history(user_id, 'assistant', 'world')
    append_history(other_user_id, 'user', 'keep me')

    client = app.test_client()
    failures: list[str] = []

    anonymous = client.post('/api/ai/chat/clear')
    if anonymous.status_code not in (302, 401):
        failures.append(f'anonymous request should require login, got {anonymous.status_code}')

    login_as(client, user_id)
    response = client.post('/api/ai/chat/clear')
    if response.status_code != 200:
        failures.append(f'authenticated clear expected 200, got {response.status_code}')
    else:
        payload = response.get_json() or {}
        if payload.get('status') != 'success':
            failures.append('clear response status is not success')

    if get_history(user_id):
        failures.append('current user history was not cleared')
    if len(get_history(other_user_id)) != 1:
        failures.append('clear endpoint changed another user history')

    if failures:
        print('FAIL AI-HISTORY:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-HISTORY: chat clear endpoint requires login and clears current user history')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
