"""B2: native replay must identify content and commit the receipt with business writes."""
import json

import pytest
from flask import jsonify, make_response
from sqlalchemy import event

import app as w


ENDPOINTS = ('inbound', 'outbound', 'stocktake', 'opening_stock_edit',
             'opening_stock', 'inbound_draft', 'voice_out_draft',
             'voice_intent', 'assistant_chat')


@pytest.fixture()
def native_case(monkeypatch):
    with w.app.app_context():
        monkeypatch.setitem(w.app.config, 'TESTING', True)
        monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='b2-synthetic', role='admin', password_hash='unused',
                      must_change_password=False, status='normal')
        warehouse = w.Warehouse(code='B2-A', name='B2合成仓', status='active', is_default=True)
        material = w.Material(code='B2-M', name='B2合成物料', stock=0, price=0)
        w.db.session.add_all([user, warehouse, material])
        w.db.session.commit()
        uid = user.id
        monkeypatch.setattr(w, 'get_bearer_user', lambda: w.db.session.get(w.User, uid))
        monkeypatch.setattr('routes.print_queue.enqueue_auto_print_job', lambda *a, **k: None)
        yield w.app.test_client(), uid
        w.db.session.rollback()
        w.db.session.remove()


@pytest.mark.parametrize('endpoint', ENDPOINTS)
def test_mobile_api_idempotent(native_case, endpoint):
    """Every registered consumer rejects a changed body; the original response stays exact."""
    _client, uid = native_case
    calls = []

    @w.mobile_api_idempotent(endpoint)
    def handler(user):
        calls.append(user.id)
        return jsonify(status='success', data={'call': len(calls)})

    def send(quantity):
        with w.app.test_request_context('/b2/'+endpoint, method='POST',
                                       json={'request_id': 'same-key', 'quantity': quantity}):
            return make_response(handler(w.db.session.get(w.User, uid)))

    first = send(2)
    replay = send(2)
    changed = send(3)
    assert first.status_code == replay.status_code == 200
    assert replay.get_json() == first.get_json()
    assert changed.status_code == 409
    assert calls == [uid]


def test_native_receipt_failure_rolls_back_stock_and_retry_once(native_case):
    client, _uid = native_case
    payload = {'warehouse_code': 'B2-A', 'request_id': 'receipt-failure',
               'lines': [{'material_code': 'B2-M', 'quantity': 3}]}

    def fail_success_receipt(_mapper, _connection, target):
        if target.status_code >= 200:
            raise RuntimeError('synthetic receipt storage fault')

    event.listen(w.MobileApiRequest, 'before_insert', fail_success_receipt)
    event.listen(w.MobileApiRequest, 'before_update', fail_success_receipt)
    try:
        failed = client.post('/api/inbound', json=payload)
    finally:
        event.remove(w.MobileApiRequest, 'before_insert', fail_success_receipt)
        event.remove(w.MobileApiRequest, 'before_update', fail_success_receipt)
    assert failed.status_code == 503
    assert w.InOrder.query.count() == 0
    assert w.StockTransaction.query.count() == 0
    assert w.Material.query.one().stock == 0
    retry = client.post('/api/inbound', json=payload)
    replay = client.post('/api/inbound', json=payload)
    assert retry.status_code == replay.status_code == 200
    assert retry.get_json() == replay.get_json()
    assert w.InOrder.query.count() == 1
    assert w.StockTransaction.query.count() == 1
    assert w.Material.query.one().stock == 3
    assert w.MobileApiRequest.query.count() == 1


def test_native_legacy_receipt_cannot_confirm_an_unknown_body(native_case):
    client, uid = native_case
    w.db.session.add(w.MobileApiRequest(user_id=uid, endpoint='inbound',
                                       request_key='legacy', status_code=200,
                                       response_json=json.dumps({'status': 'success', 'data': {'id': 999}})))
    w.db.session.commit()
    response = client.post('/api/inbound', json={
        'request_id': 'legacy', 'warehouse_code': 'B2-A',
        'lines': [{'material_code': 'B2-M', 'quantity': 3}]})
    assert response.status_code == 409
    assert w.InOrder.query.count() == 0
    assert w.Material.query.one().stock == 0


def test_native_invalid_request_does_not_hold_its_key(native_case):
    client, _uid = native_case
    assert client.post('/api/inbound', json={'request_id': 'validation'}).status_code == 400
    assert w.MobileApiRequest.query.count() == 0
    valid = client.post('/api/inbound', json={
        'request_id': 'validation', 'warehouse_code': 'B2-A',
        'lines': [{'material_code': 'B2-M', 'quantity': 1}]})
    assert valid.status_code == 200
    assert w.InOrder.query.count() == 1
    assert w.Material.query.one().stock == 1


def test_commit(native_case):
    """Nested service commits cannot escape a later response-storage failure."""
    _client, uid = native_case

    @w.mobile_api_idempotent('assistant_chat')
    def handler(_user):
        material = w.Material.query.one()
        material.stock = 1
        w.db.session.commit()
        material.stock = 2
        w.db.session.commit()
        return jsonify(status='success')

    def fault(_mapper, _connection, row):
        if row.status_code >= 200:
            raise RuntimeError('synthetic final receipt fault')

    event.listen(w.MobileApiRequest, 'before_insert', fault)
    event.listen(w.MobileApiRequest, 'before_update', fault)
    try:
        with w.app.test_request_context('/b2/nested', method='POST', json={'request_id': 'nested'}):
            result = make_response(handler(w.db.session.get(w.User, uid)))
    finally:
        event.remove(w.MobileApiRequest, 'before_insert', fault)
        event.remove(w.MobileApiRequest, 'before_update', fault)
    assert result.status_code == 503
    assert w.Material.query.one().stock == 0
    assert w.MobileApiRequest.query.count() == 0


def test_rollback(native_case):
    """A swallowed inner rollback must not be followed by a partial success."""
    _client, uid = native_case

    @w.mobile_api_idempotent('inbound')
    def handler(_user):
        material = w.Material.query.one()
        material.stock = 1
        w.db.session.commit()
        w.db.session.rollback()
        material.stock = 2
        w.db.session.commit()
        return jsonify(status='success')

    with w.app.test_request_context('/b2/rollback', method='POST', json={'request_id': 'rollback'}):
        result = make_response(handler(w.db.session.get(w.User, uid)))
    assert result.status_code == 503
    assert w.Material.query.one().stock == 0
    assert w.MobileApiRequest.query.count() == 0


def test_flush(native_case):
    _client, uid = native_case

    @w.mobile_api_idempotent('inbound_draft')
    def handler(_user):
        material = w.Material.query.one()
        material.stock = 2
        w.db.session.flush()
        assert w.db.session().info.get('native_request', {}).get('atomic') is True
        return jsonify(status='success')

    with w.app.test_request_context('/b2/flush', method='POST', json={'request_id': 'flush'}):
        result = make_response(handler(w.db.session.get(w.User, uid)))
    assert result.status_code == 200
    assert w.Material.query.one().stock == 2
    assert w.MobileApiRequest.query.count() == 1
    assert 'native_request' not in w.db.session().info


def test_native_request_path_is_part_of_identity(native_case):
    _client, uid = native_case

    @w.mobile_api_idempotent('opening_stock_edit')
    def handler(_user):
        return jsonify(status='success')

    results = []
    for path in ('/api/opening_stock/1', '/api/opening_stock/2'):
        with w.app.test_request_context(path, method='POST', json={'request_id': 'edit', 'quantity': 2}):
            results.append(make_response(handler(w.db.session.get(w.User, uid))))
    assert [response.status_code for response in results] == [200, 409]


def test_native_no_key_preserves_existing_operations(native_case):
    client, _uid = native_case
    payload = {'warehouse_code': 'B2-A', 'lines': [{'material_code': 'B2-M', 'quantity': 1}]}
    assert client.post('/api/inbound', json=payload).status_code == 200
    assert client.post('/api/inbound', json=payload).status_code == 200
    assert w.InOrder.query.count() == 2
    assert w.Material.query.one().stock == 2
    assert w.MobileApiRequest.query.count() == 0


@pytest.mark.parametrize('endpoint', ENDPOINTS)
def test_wrapped(native_case, monkeypatch, endpoint):
    client, uid = native_case
    monkeypatch.setattr(w, '_ai_global_enabled', lambda: True)
    monkeypatch.setattr(w, '_ai_call_llm_intent',
                        lambda *a, **k: {'intent': 'today_summary', 'params': {}})
    monkeypatch.setattr('routes.native_api._parse_voice_out_text_llm', lambda _text: None)
    payload = {'warehouse_code': 'B2-A', 'request_id': 'http-'+endpoint,
               'lines': [{'material_code': 'B2-M', 'quantity': 1}]}
    path = '/api/'+endpoint
    if endpoint == 'outbound':
        material = w.Material.query.one()
        warehouse = w.Warehouse.query.one()
        material.stock = 10
        w.db.session.add(w.StockTransaction(material_id=material.id, transaction_type='in',
                                            quantity=10, warehouse_id=warehouse.id,
                                            location=warehouse.name))
        w.db.session.commit()
    elif endpoint == 'stocktake':
        check = w.InventoryCheck(check_no='B2-CHECK', status='pending', warehouse='B2合成仓')
        w.db.session.add(check)
        w.db.session.commit()
        payload['check_id'] = check.id
        payload['lines'] = [{'material_code': 'B2-M', 'actual_stock': 1}]
    elif endpoint == 'opening_stock_edit':
        initial = client.post('/api/opening_stock', json={
            'warehouse_code': 'B2-A', 'lines': [{'material_code': 'B2-M', 'quantity': 1}]})
        assert initial.status_code == 200, initial.get_json()
        opening = w.OpeningStock.query.one()
        from services.document_edit_guard import opening_line_revision
        path = '/api/opening_stock/'+str(opening.id)
        payload = {'quantity': 2, 'revision': opening_line_revision(opening, uid),
                   'request_id': 'http-'+endpoint}
    elif endpoint == 'inbound_draft':
        path = '/api/mobile/inbound_draft'
        payload['business_type'] = '产品入库'
    elif endpoint == 'voice_out_draft':
        path = '/api/mobile/voice_out_draft'
        payload.update(text='领B2合成物料 1个', dry_run=False, material_code='B2-M', quantity=1)
    elif endpoint in ('voice_intent', 'assistant_chat'):
        path = '/api/mobile/'+endpoint
        payload = {'text': '今天概况', 'request_id': 'http-'+endpoint}
    first = client.post(path, json=payload)
    assert first.status_code == 200, (endpoint, first.get_json())

    def snapshot():
        from ai.models import AIConversation, AIMessage
        return (w.Material.query.one().stock,
                *[model.query.count() for model in (w.InOrder, w.OutOrder, w.InventoryCheckScan,
                                                    w.OpeningStock, w.StockTransaction,
                                                    AIConversation, AIMessage, w.MobileApiRequest)])

    saved = snapshot()
    replay = client.post(path, json=payload)
    changed = client.post(path, json={**payload, 'remark': 'changed content'})
    assert replay.status_code == 200
    assert replay.get_json() == first.get_json()
    assert changed.status_code == 409
    assert snapshot() == saved
    assert w.MobileApiRequest.query.count() == 1
