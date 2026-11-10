"""Current AI permissions must also apply to saved native responses."""
import json
import pytest

import app as w
from tests.test_native_request_atomicity import native_case


def prepare(monkeypatch, endpoint):
    monkeypatch.setattr(w, '_ai_global_enabled', lambda: True)
    monkeypatch.setattr(w, '_ai_call_llm_intent',
                        lambda *_args, **_kwargs: {'intent': 'today_summary', 'params': {}})
    monkeypatch.setattr('routes.native_api._parse_voice_out_text_llm', lambda _text: None)
    payload = {'text': '今天概况', 'request_id': 'replay-permissions'}
    if endpoint == 'voice_out_draft':
        payload.update(text='领B2合成物料 1个', warehouse_code='B2-A', dry_run=True)
    return '/api/mobile/' + endpoint, payload


@pytest.mark.parametrize('endpoint', ['voice_out_draft', 'voice_intent', 'assistant_chat'])
@pytest.mark.parametrize('revoke', ['global', 'capability'])
def test_native_request_idempotent_rechecks_ai_access(native_case, monkeypatch, endpoint, revoke):
    client, _uid = native_case
    path, payload = prepare(monkeypatch, endpoint)
    first = client.post(path, json=payload)
    assert first.status_code == 200, first.json
    stored = w.MobileApiRequest.query.one().response_json
    from ai.models import AIConversation, AIMessage
    counts = (AIConversation.query.count(), AIMessage.query.count(), w.OutOrder.query.count())
    with monkeypatch.context() as revoked:
        if revoke == 'global':
            revoked.setattr(w, '_ai_global_enabled', lambda: False)
        else:
            revoked.setattr('ai.policies.is_ai_capability_allowed_for_role', lambda *_a, **_k: False)
        replay = client.post(path, json=payload)
        assert replay.status_code == 403, 'Revoked AI access must not disclose a cached success'
        assert replay.json != first.json
    assert w.MobileApiRequest.query.one().response_json == stored
    assert (AIConversation.query.count(), AIMessage.query.count(), w.OutOrder.query.count()) == counts
    allowed_again = client.post(path, json=payload)
    assert allowed_again.status_code == 200 and allowed_again.json == first.json


def test_native_request_idempotent_rechecks_voice_draft_action(native_case, monkeypatch):
    client, _uid = native_case
    path, payload = prepare(monkeypatch, 'voice_intent')
    monkeypatch.setattr(w, '_ai_call_llm_intent',
                        lambda *_a, **_k: {'intent': 'create_out_order_draft', 'params': {'material': 'B2-M'}})
    first = client.post(path, json=payload)
    assert first.status_code == 200 and first.json['data']['action'] == 'voice_out_draft'
    stored = w.MobileApiRequest.query.one().response_json
    from routes.native_api import _mobile_capability_allowed
    monkeypatch.setattr('routes.native_api._mobile_capability_allowed',
                        lambda user, capability, **kw: capability != 'voice_out_draft'
                        and _mobile_capability_allowed(user, capability, **kw))
    replay = client.post(path, json=payload)
    assert replay.status_code == 403
    assert w.MobileApiRequest.query.one().response_json == stored
    assert w.OutOrder.query.count() == 0


@pytest.mark.parametrize('endpoint', ['voice_intent', 'assistant_chat'])
def test_native_keyless_ai_retains_documented_compatibility(native_case, monkeypatch, endpoint):
    client, _uid = native_case
    path, payload = prepare(monkeypatch, endpoint)
    payload.pop('request_id')
    for _ in range(2):
        response = client.post(path, json=payload)
        assert response.status_code == 200, response.json
    assert w.MobileApiRequest.query.count() == 0
    assert w.OutOrder.query.count() == w.InOrder.query.count() == 0
    assert w.Material.query.one().stock == 0


@pytest.mark.parametrize('endpoint', ['voice_out_draft', 'voice_intent', 'assistant_chat'])
def test_native_legacy_ai_requires_review_without_altering_its_receipt(native_case, monkeypatch, endpoint):
    client, uid = native_case
    path, payload = prepare(monkeypatch, endpoint)
    old = json.dumps({'success': True, 'data': {'id': 42}})
    w.db.session.add(w.MobileApiRequest(user_id=uid, endpoint=endpoint,
                                      request_key=payload['request_id'], status_code=200, response_json=old))
    w.db.session.commit()
    response = client.post(path, json=payload)
    assert response.status_code == 409 and '核对' in response.json['msg']
    assert w.MobileApiRequest.query.one().response_json == old
    assert w.OutOrder.query.count() == w.InOrder.query.count() == 0
    assert w.Material.query.one().stock == 0
