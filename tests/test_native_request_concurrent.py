"""B2 real connections, native HTTP races, and no writer lock during model wait."""
from pathlib import Path
import sqlite3
import threading

import pytest

import app as w


@pytest.fixture()
def file_case(monkeypatch, request):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        database = w.db.engine.url.database
        if database == ':memory:':
            pytest.skip('Requires a dedicated fresh, explicitly allowlisted synthetic SQLite file')
        lab = Path(r'C:\Users\Administrator\Documents\Codex\2026-11-07\wms-improvement-90\lab')
        assert Path(database).resolve().is_relative_to(lab.resolve())
        assert Path(database).name == 'synthetic.sqlite'
        w.db.create_all()
        suffix = request.node.name.replace('[', '-').replace(']', '')
        user = w.User(username=suffix, role='admin', password_hash='unused', must_change_password=False)
        warehouse = w.Warehouse(code=suffix, name='合成仓-'+suffix, status='active')
        material = w.Material(code=suffix, name='合成物料-'+suffix, stock=0, price=0)
        w.db.session.add_all([user, warehouse, material])
        w.db.session.commit()
        uid, mid, warehouse_code, material_code = user.id, material.id, warehouse.code, material.code
        engine = w.db.engine
        w.db.session.remove()
    monkeypatch.setattr(w, 'get_bearer_user', lambda: w.db.session.get(w.User, uid))
    monkeypatch.setattr('routes.print_queue.enqueue_auto_print_job', lambda *a, **k: None)
    return engine, database, uid, mid, warehouse_code, material_code


@pytest.mark.parametrize('mode', ('same', 'changed', 'different_keys', 'user_isolation'))
def test_native_requests_use_real_connections(file_case, monkeypatch, mode):
    engine, _database, uid, mid, warehouse, code = file_case
    second_uid = uid
    if mode == 'user_isolation':
        with w.app.app_context():
            second = w.User(username='second-native-actor', role='admin', password_hash='unused',
                            must_change_password=False)
            w.db.session.add(second)
            w.db.session.commit()
            second_uid = second.id
            w.db.session.remove()
        from flask import request
        monkeypatch.setattr(w, 'get_bearer_user', lambda: w.db.session.get(
            w.User, int(request.headers.get('X-Synthetic-Actor', uid))))
    barrier = threading.Barrier(2)
    results, errors, connections = [], [], set()
    mutex = threading.Lock()

    def submit(index):
        try:
            with w.app.app_context():
                connection = w.db.session.connection()
                with mutex:
                    connections.add(id(connection.connection.driver_connection))
                barrier.wait(timeout=10)
                quantity = 2 if mode == 'same' or index == 0 else 3
                key = str(index) if mode == 'different_keys' else 'same'
                response = w.app.test_client().post('/api/inbound',
                    headers={'X-Synthetic-Actor': str(second_uid if index else uid)}, json={
                    'warehouse_code': warehouse, 'request_id': key,
                    'lines': [{'material_code': code, 'quantity': quantity}]})
                with mutex:
                    results.append((index, response.status_code, response.get_json()))
                w.db.session.remove()
        except Exception as exc:
            with mutex:
                errors.append(repr(exc))

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=40)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors, errors
    assert len(connections) == 2
    assert len(results) == 2
    if mode == 'same':
        assert all(status in (200, 503) for _, status, _ in results), results
        retry = w.app.test_client().post('/api/inbound', json={
            'warehouse_code': warehouse, 'request_id': 'same',
            'lines': [{'material_code': code, 'quantity': 2}]})
        assert retry.status_code == 200
        assert all(body == retry.get_json() for _, status, body in results if status == 200)
    elif mode == 'changed':
        assert sorted(status for _, status, _ in results) == [200, 409], results
    else:
        assert all(status == 200 for _, status, _ in results), results
    with w.app.app_context():
        material = w.db.session.get(w.Material, mid)
        expected = 5 if mode in ('different_keys', 'user_isolation') else next(
            2 if index == 0 or mode == 'same' else 3 for index, status, _ in results if status == 200)
        assert material.stock == expected
        txns = w.StockTransaction.query.filter_by(material_id=mid).all()
        assert len(txns) == (2 if mode in ('different_keys', 'user_isolation') else 1)
        assert sum(row.quantity for row in txns) == expected
        w.db.session.remove()


def test_native_material_creation_is_serialized_before_matching(file_case):
    _engine, _database, uid, _mid, warehouse, _code = file_case
    barrier = threading.Barrier(2)
    results, errors, connections = [], [], set()
    mutex = threading.Lock()
    name = '合成并发自动建档物料'

    def submit(index):
        try:
            with w.app.app_context():
                connection = w.db.session.connection()
                with mutex:
                    connections.add(id(connection.connection.driver_connection))
                barrier.wait(timeout=10)
                response = w.app.test_client().post('/api/mobile/inbound_draft', json={
                    'request_id': 'auto-'+str(index), 'warehouse_code': warehouse,
                    'business_type': '产品入库', 'auto_create_material': True,
                    'lines': [{'material_code': 'NOT-REGISTERED', 'name': name, 'spec': 'SYNTHETIC',
                               'quantity': 1}]})
                with mutex:
                    results.append((response.status_code, response.get_json()))
                w.db.session.remove()
        except Exception as exc:
            with mutex:
                errors.append(repr(exc))

    threads = [threading.Thread(target=submit, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=40)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors, errors
    assert len(connections) == 2
    assert len(results) == 2
    assert all(status == 200 for status, _ in results), results
    with w.app.app_context():
        materials = w.Material.query.filter_by(name=name, spec='SYNTHETIC').all()
        assert len(materials) == 1
        assert materials[0].stock == 0
        orders = w.InOrder.query.filter_by(operator_id=uid).all()
        assert len(orders) == 2
        assert len({order.order_no for order in orders}) == 2
        assert all(order.status == 'pending' for order in orders)
        assert all(order.items[0].material_id == materials[0].id for order in orders)
        assert w.MobileApiRequest.query.filter_by(user_id=uid).count() == 2
        w.db.session.remove()


def test_model_wait_does_not_hold_sqlite_writer(file_case, monkeypatch):
    _engine, database, _uid, mid, _warehouse, _code = file_case
    entered, release = threading.Event(), threading.Event()
    results, errors = [], []

    def synthetic_model(_text, overrides=None):
        entered.set()
        assert release.wait(timeout=10)
        return {'intent': 'help', 'params': {}}

    monkeypatch.setattr(w, '_ai_global_enabled', lambda: True)
    monkeypatch.setattr(w, '_ai_call_llm_intent', synthetic_model)

    def send():
        try:
            response = w.app.test_client().post('/api/mobile/voice_intent',
                json={'request_id': 'slow-model', 'text': '合成模型等待测试'})
            results.append(response.status_code)
        except Exception as exc:
            errors.append(repr(exc))

    thread = threading.Thread(target=send)
    thread.start()
    try:
        assert entered.wait(timeout=10)
        with sqlite3.connect(database, timeout=0.2) as second:
            second.execute('UPDATE material SET price=? WHERE id=?', (1, mid))
            second.commit()
    finally:
        release.set()
        thread.join(timeout=20)
    assert not thread.is_alive()
    assert not errors, errors
    assert results == [200]
    with w.app.app_context():
        assert w.db.session.get(w.Material, mid).price == 1
        assert w.db.session.get(w.Material, mid).stock == 0
        w.db.session.remove()


def test_expired_http_owner_cannot_create_a_second_draft(file_case, monkeypatch):
    _engine, database, uid, _mid, warehouse, code = file_case
    entered, release = threading.Event(), threading.Event()
    results, errors = [], []
    counter = [0]
    mutex = threading.Lock()

    def synthetic_model(text):
        with mutex:
            counter[0] += 1
            number = counter[0]
        if number == 1:
            entered.set()
            assert release.wait(timeout=15)
        from routes.native_api import _parse_voice_out_text
        parsed = _parse_voice_out_text(text)
        parsed.update(keyword=code, spec_hint='', quantity=2)
        return parsed

    monkeypatch.setattr(w, '_ai_global_enabled', lambda: True)
    monkeypatch.setattr('routes.native_api._parse_voice_out_text_llm', synthetic_model)
    payload = {'request_id': 'lease-http', 'warehouse_code': warehouse,
               'text': '合成语音草稿 2个', 'material_code': code, 'quantity': 2, 'dry_run': False}

    def first_request():
        try:
            response = w.app.test_client().post('/api/mobile/voice_out_draft', json=payload)
            results.append(response.status_code)
        except Exception as exc:
            errors.append(repr(exc))

    thread = threading.Thread(target=first_request)
    thread.start()
    try:
        assert entered.wait(timeout=10)
        with sqlite3.connect(database, timeout=0.2) as second:
            changed = second.execute(
                'UPDATE mobile_api_request SET created_at=? WHERE user_id=? AND endpoint=? AND request_key=?',
                ('2000-01-01 00:00:00', uid, 'voice_out_draft', 'lease-http'))
            assert changed.rowcount == 1
            second.commit()
        replacement = w.app.test_client().post('/api/mobile/voice_out_draft', json=payload)
        assert replacement.status_code == 200, replacement.get_json()
    finally:
        release.set()
        thread.join(timeout=25)
    assert not thread.is_alive()
    assert not errors, errors
    assert results == [503]
    replay = w.app.test_client().post('/api/mobile/voice_out_draft', json=payload)
    assert replay.status_code == 200
    assert replay.get_json() == replacement.get_json()
    with w.app.app_context():
        assert w.OutOrder.query.filter_by(operator_id=uid).count() == 1
        assert w.MobileApiRequest.query.filter_by(user_id=uid).count() == 1
        w.db.session.remove()
