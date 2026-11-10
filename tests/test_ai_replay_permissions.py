"""JSON and SSE replay must honor current access without rerunning AI."""
import pytest
from flask import Response, jsonify

import app as w
from tests.test_native_request_atomicity import native_case


@pytest.mark.parametrize('endpoint', ['warehouse_assistant', 'chat/stream'])
@pytest.mark.parametrize('revoke', ['global', 'role', 'capability'])
def test_replay_rechecks_current_permission(native_case, monkeypatch, endpoint, revoke):
    client, uid = native_case
    monkeypatch.setattr(w, '_ai_global_enabled', lambda: True)
    calls = []

    def respond(_payload):
        calls.append(True)
        assert w._ai_capability_allowed('admin_insights')
        if endpoint == 'chat/stream':
            return Response(iter(['data: {"type":"done","content":"synthetic-private"}\n\n']),
                            content_type='text/event-stream')
        return jsonify(status='success', reply='synthetic-private')

    handler = 'handle_chat_stream' if endpoint == 'chat/stream' else 'handle_warehouse_assistant'
    monkeypatch.setattr('ai.routes.' + handler, respond)
    with client.session_transaction() as session:
        session['_user_id'] = str(uid)
        session['_fresh'] = True
    path = '/api/ai/' + endpoint
    payload = {'message': 'synthetic', 'request_id': 'synthetic-replay-permission'}
    first = client.post(path, json=payload, buffered=True)
    assert first.status_code == 200, first.get_data(as_text=True)
    assert w.AIToolCall.query.filter_by(permission_allowed=True).count() == 1
    stored = w.AIRequestIdempotency.query.one().response_body
    with monkeypatch.context() as revoked:
        if revoke == 'global':
            revoked.setattr(w, '_ai_global_enabled', lambda: False)
        elif revoke == 'capability':
            revoked.setattr(w, '_ai_capability_allowed', lambda *_a, **_k: False)
        else:
            w.db.session.get(w.User, uid).role = 'viewer'
            w.db.session.commit()
        denied = client.post(path, json=payload, buffered=True)
        assert denied.status_code == 403
        assert 'synthetic-private' not in denied.get_data(as_text=True)
    if revoke == 'role':
        w.db.session.get(w.User, uid).role = 'admin'
        w.db.session.commit()
    assert w.AIRequestIdempotency.query.one().response_body == stored
    again = client.post(path, json=payload, buffered=True)
    assert again.status_code == 200 and again.get_data() == first.get_data()
    assert calls == [True]
    assert w.AIRun.query.count() == w.AIRequestIdempotency.query.count() == w.AIToolCall.query.count() == 1
