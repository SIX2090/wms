from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-chat-stream-secret'
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
            username='chat-stream-endpoint-user',
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
    calls: list[dict[str, object]] = []
    original_handler = wms_app._ai_handle_chat_stream_request

    def fake_handler(payload):
        calls.append(dict(payload or {}))

        def generate():
            yield 'data: {"type":"token","content":"ok"}\n\n'
            yield 'data: {"type":"done","content":"ok"}\n\n'

        return wms_app.Response(
            wms_app.stream_with_context(generate()),
            content_type='text/event-stream; charset=utf-8',
        )

    wms_app._ai_handle_chat_stream_request = fake_handler
    try:
        anonymous = client.post('/api/ai/chat/stream', json={'request_id': 'verify-stream-route-0000', 'message': 'hello'})
        if anonymous.status_code not in (302, 401):
            failures.append(f'anonymous request should require login, got {anonymous.status_code}')

        login_as(client, user_id)

        missing_request_id = client.post('/api/ai/chat/stream', json={'message': 'hello'})
        if missing_request_id.status_code != 400:
            failures.append(f'missing request_id expected 400, got {missing_request_id.status_code}')

        payload = {'request_id': 'verify-stream-route-0001', 'message': 'hello'}
        first = client.post('/api/ai/chat/stream', json=payload, buffered=True)
        second = client.post('/api/ai/chat/stream', json=payload, buffered=True)
        if first.status_code != 200 or second.status_code != 200:
            failures.append(f'idempotent stream calls expected 200/200, got {first.status_code}/{second.status_code}')
        if first.get_data() != second.get_data():
            failures.append('replayed chat stream response differs from first response')
        if len(calls) != 1:
            failures.append(f'chat stream handler should execute once, got {len(calls)}')
        if calls and calls[0] != payload:
            failures.append(f'chat stream handler payload mismatch: {calls[0]!r}')
    finally:
        wms_app._ai_handle_chat_stream_request = original_handler

    if failures:
        print('FAIL AI-CHAT-STREAM-ENDPOINT:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-CHAT-STREAM-ENDPOINT: Blueprint SSE route keeps login and request_id idempotency')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
