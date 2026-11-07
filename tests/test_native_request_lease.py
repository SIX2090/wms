"""Native claim lifetime, owner fencing and failure paths on synthetic memory data."""
from datetime import datetime, timedelta

import pytest

import app as w
from tests.test_native_request_atomicity import native_case

_REAL_BEARER_USER = w.get_bearer_user


def test_activate_native_business_transaction(native_case):
    from services.native_request_idempotency import (
        _claim, _release, activate_native_business_transaction,
    )
    _client, uid = native_case
    first, response = _claim(uid, 'inbound', 'expired', 'synthetic-fingerprint')
    assert response is None
    row = w.db.session.get(w.MobileApiRequest, first['id'])
    row.created_at = datetime.now() - timedelta(minutes=5)
    w.db.session.commit()
    replacement, response = _claim(uid, 'inbound', 'expired', 'synthetic-fingerprint')
    assert response is None
    assert replacement['id'] == first['id']
    assert replacement['pending'] != first['pending']
    session = w.db.session()
    session.info['native_request'] = first
    try:
        with pytest.raises(RuntimeError, match='ownership changed'):
            activate_native_business_transaction()
    finally:
        session.info.pop('native_request', None)
        session.rollback()
    _release(first)
    assert w.MobileApiRequest.query.count() == 1
    assert w.MobileApiRequest.query.one().response_json == replacement['pending']
    assert w.Material.query.one().stock == 0
    _release(replacement)
    assert w.MobileApiRequest.query.count() == 0


def test_native_request_idempotent(native_case):
    from services.native_request_idempotency import _claim
    _client, uid = native_case
    state, response = _claim(uid, 'voice_intent', 'busy', 'same-fingerprint')
    assert response is None
    second, busy = _claim(uid, 'voice_intent', 'busy', 'same-fingerprint')
    assert second is None and busy.status_code == 503
    assert busy.headers['Retry-After'] == '1'
    assert w.MobileApiRequest.query.count() == 1
    conflict, response = _claim(uid, 'voice_intent', 'busy', 'different-fingerprint')
    assert conflict is None and response.status_code == 409
    assert w.MobileApiRequest.query.one().response_json == state['pending']


def test_initial_claim_failure_never_runs_native_business(native_case):
    from sqlalchemy import event
    client, _uid = native_case

    def fault(_mapper, _connection, _target):
        raise RuntimeError('synthetic initial claim fault')

    event.listen(w.MobileApiRequest, 'before_insert', fault)
    try:
        response = client.post('/api/inbound', json={
            'warehouse_code': 'B2-A', 'request_id': 'claim-fault',
            'lines': [{'material_code': 'B2-M', 'quantity': 2}]})
    finally:
        event.remove(w.MobileApiRequest, 'before_insert', fault)
    assert response.status_code == 503
    assert w.InOrder.query.count() == 0
    assert w.StockTransaction.query.count() == 0
    assert w.Material.query.one().stock == 0
    assert w.MobileApiRequest.query.count() == 0


def test_authentication_precedes_native_replay(native_case, monkeypatch):
    client, _uid = native_case
    payload = {'warehouse_code': 'B2-A', 'request_id': 'private',
               'lines': [{'material_code': 'B2-M', 'quantity': 1}]}
    assert client.post('/api/inbound', json=payload).status_code == 200
    monkeypatch.setattr(w, 'get_bearer_user', lambda: None)
    assert client.post('/api/inbound', json=payload).status_code == 401
    assert w.InOrder.query.count() == 1
    assert w.Material.query.one().stock == 1


def test_real_bearer_usage_and_expiry_precede_replay(native_case, monkeypatch):
    client, uid = native_case
    token = w.ApiToken(user_id=uid, token=w.hash_access_token('b2-synthetic-only-token'),
                       expires_at=datetime.now()+timedelta(days=7), revoked=False)
    w.db.session.add(token)
    w.db.session.commit()
    token_id = token.id
    monkeypatch.setattr(w, 'get_bearer_user', _REAL_BEARER_USER)
    headers = {'Authorization': 'Bearer b2-synthetic-only-token'}
    payload = {'warehouse_code': 'B2-A', 'request_id': 'real-bearer',
               'lines': [{'material_code': 'B2-M', 'quantity': 1}]}
    response = client.post('/api/inbound', json=payload, headers=headers)
    assert response.status_code == 200, response.get_json()
    token = w.db.session.get(w.ApiToken, token_id)
    assert token.last_used_at is not None
    token.expires_at = datetime.now()-timedelta(days=2)
    w.db.session.commit()
    denied = client.post('/api/inbound', json=payload, headers=headers)
    assert denied.status_code == 401
    assert w.InOrder.query.count() == 1
    assert w.Material.query.one().stock == 1
    assert w.MobileApiRequest.query.count() == 1


def test_response_loss_after_commit_replays_without_another_stock_write(native_case, monkeypatch):
    from flask import jsonify, request
    client, _uid = native_case
    lose = [True]

    def lose_first_response(response):
        if request.path == '/api/inbound' and lose[0] and response.status_code == 200:
            lose[0] = False
            replacement = jsonify(status='error', msg='synthetic response delivery failure')
            replacement.status_code = 503
            return replacement
        return response

    hooks = dict(w.app.after_request_funcs)
    hooks[None] = [*hooks.get(None, []), lose_first_response]
    monkeypatch.setattr(w.app, 'after_request_funcs', hooks)
    payload = {'warehouse_code': 'B2-A', 'request_id': 'lost-response',
               'lines': [{'material_code': 'B2-M', 'quantity': 3}]}
    lost = client.post('/api/inbound', json=payload)
    assert lost.status_code == 503
    assert w.InOrder.query.count() == 1
    assert w.Material.query.one().stock == 3
    retry = client.post('/api/inbound', json=payload)
    replay = client.post('/api/inbound', json=payload)
    assert retry.status_code == replay.status_code == 200
    assert retry.get_json() == replay.get_json()
    assert retry.get_json()['data']['id'] == w.InOrder.query.one().id
    assert w.InOrder.query.count() == 1
    assert w.Material.query.one().stock == 3
    assert w.StockTransaction.query.count() == 1
    assert w.MobileApiRequest.query.count() == 1
