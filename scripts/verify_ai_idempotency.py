from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-idempotency-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    counters = {'json': 0, 'stream': 0}

    @app.post('/_verify/ai-idempotency/json')
    @wms_app.login_required
    @wms_app._ai_idempotent_request
    def verify_json():
        counters['json'] += 1
        wms_app._ai_capability_allowed('admin_insights')
        return wms_app.jsonify({'status': 'success', 'count': counters['json']})

    @app.post('/_verify/ai-idempotency/stream')
    @wms_app.login_required
    @wms_app._ai_idempotent_request
    def verify_stream():
        def generate():
            counters['stream'] += 1
            yield 'data: {"type":"done","content":"ok"}\n\n'

        return wms_app.Response(
            wms_app.stream_with_context(generate()),
            content_type='text/event-stream; charset=utf-8',
        )

    with app.app_context():
        wms_app.db.create_all()
        user = wms_app.User(
            username='idempotency-verifier',
            password_hash='not-used',
            role='admin',
            status='normal',
        )
        wms_app.db.session.add(user)
        wms_app.db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True

    json_payload = {'request_id': 'verify-json-0001', 'message': 'create draft'}
    missing_request_id = client.post(
        '/_verify/ai-idempotency/json',
        json={'message': 'missing request id'},
    )
    assert missing_request_id.status_code == 400
    first_json = client.post('/_verify/ai-idempotency/json', json=json_payload)
    second_json = client.post('/_verify/ai-idempotency/json', json=json_payload)
    assert first_json.status_code == 200
    assert second_json.status_code == 200
    assert first_json.get_data() == second_json.get_data()
    assert counters['json'] == 1

    mismatch = client.post(
        '/_verify/ai-idempotency/json',
        json={'request_id': 'verify-json-0001', 'message': 'different request'},
    )
    assert mismatch.status_code == 409

    stream_payload = {'request_id': 'verify-stream-0001', 'message': 'create draft'}
    first_stream = client.post('/_verify/ai-idempotency/stream', json=stream_payload, buffered=True)
    second_stream = client.post('/_verify/ai-idempotency/stream', json=stream_payload, buffered=True)
    assert first_stream.status_code == 200
    assert second_stream.status_code == 200
    assert first_stream.get_data() == second_stream.get_data()
    assert counters['stream'] == 1

    with app.app_context():
        runs = wms_app.AIRun.query.order_by(wms_app.AIRun.id.asc()).all()
        assert len(runs) == 2
        assert {run.status for run in runs} == {'completed'}
        assert all(run.duration_ms is not None and run.duration_ms >= 0 for run in runs)
        assert all(run.model for run in runs)
        assert wms_app.AIRequestIdempotency.query.count() == 2
        tool_calls = wms_app.AIToolCall.query.all()
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_name == 'admin_insights'
        assert tool_calls[0].permission_allowed is True
        assert tool_calls[0].ai_run_id == runs[0].id

    print('PASS AI-IDEMPOTENCY: requests execute once, replay responses, and persist run/tool audits')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
