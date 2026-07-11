from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-draft-check-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


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
            username='draft-check-endpoint-user',
            password_hash='not-used',
            role='warehouse',
            status='normal',
        )
        wms_app.db.session.add(user)
        wms_app.db.session.flush()
        user_id = user.id
        wms_app.db.session.commit()

    client = app.test_client()
    failures: list[str] = []
    captured: dict[str, object] = {}
    original_handler = wms_app._ai_draft_check_response

    def fake_draft_check_response(message, context=None):
        captured['message'] = message
        captured['context'] = context
        return wms_app.jsonify({'status': 'success', 'msg': 'ok'})

    wms_app._ai_draft_check_response = fake_draft_check_response
    try:
        anonymous = client.post('/api/ai/draft_check', json={'page_url': '/out_order/new'})
        if anonymous.status_code not in (302, 401):
            failures.append(f'anonymous request should require login, got {anonymous.status_code}')

        login_as(client, user_id)
        response = client.post('/api/ai/draft_check', json={'page_url': ' /out_order/new '})
        if response.status_code != 200:
            failures.append(f'authenticated draft check expected 200, got {response.status_code}')
        else:
            payload = response.get_json() or {}
            if payload.get('status') != 'success':
                failures.append('draft check response status is not success')

        if captured.get('message') != '检查当前草稿':
            failures.append('draft check route did not use the expected prompt')
        if captured.get('context') != {'page_url': '/out_order/new'}:
            failures.append(f'draft check route context mismatch: {captured.get("context")!r}')
    finally:
        wms_app._ai_draft_check_response = original_handler

    if failures:
        print('FAIL AI-DRAFT-CHECK-ENDPOINT:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-DRAFT-CHECK-ENDPOINT: draft check endpoint is authenticated and delegates through ai Blueprint')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
