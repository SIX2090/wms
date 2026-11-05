"""Real bearer users, stale/missing row versions, delta ledger and replay."""
from datetime import date
import pytest
from werkzeug.security import generate_password_hash
import app as w
from tests.test_document_create_number_conflicts import case, snapshot


@pytest.fixture
def opening_actors(case):
    clients, ids = case
    created = clients[0].post('/opening_stock/save', json={
        'warehouse_id': ids['a'], 'date': date.today().isoformat(),
        'items': [{'material_id': ids['mats'][0], 'warehouse_id': ids['a'], 'quantity': 5, 'price': 2}],
    })
    assert created.status_code == 200, created.json
    with w.app.app_context():
        line = w.OpeningStock.query.one()
        line_id = line.id
        for name in ('revision-mobile-A', 'revision-mobile-B'):
            w.db.session.add(w.User(username=name, role='warehouse', must_change_password=False,
                                   password_hash=generate_password_hash('isolated-fixed-test')))
        w.db.session.commit()
    actors = []
    for name in ('revision-mobile-A', 'revision-mobile-B'):
        client = w.app.test_client()
        response = client.post('/api/login', json={'username': name, 'password': 'isolated-fixed-test'})
        assert response.status_code == 200, response.json
        headers = {'Authorization': 'Bearer '+response.json['data']['token']}
        listed = client.get('/api/opening_stock', query_string={'warehouse_id': ids['a']}, headers=headers)
        assert listed.status_code == 200, listed.json
        row = next(item for item in listed.json['data']['items'] if item['id'] == line_id)
        actors.append((client, headers, row.get('revision')))
    return actors, ids, line_id


def test_opening_line_revision(opening_actors):
    actors, ids, line_id = opening_actors
    first, second = actors
    assert first[2] != second[2]
    response = first[0].post(f'/api/opening_stock/{line_id}',
                           json={'quantity': 7, 'revision': first[2]}, headers=first[1])
    assert response.status_code == 200, response.json
    with w.app.app_context():
        saved = snapshot(w.InOrder)
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 37
        assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, ids['b']))[ids['mats'][0]] == 10
    for revision in (second[2], first[2], None, 'forged'):
        data = {'quantity': 99}
        if revision is not None:
            data['revision'] = revision
        stale = second[0].post(f'/api/opening_stock/{line_id}', json=data, headers=second[1])
        assert stale.status_code == 409, stale.json
        with w.app.app_context():
            assert snapshot(w.InOrder) == saved
            assert w.db.session.get(w.OpeningStock, line_id).quantity == 7


def test_opening_line_revision_matches(opening_actors):
    actors, _, line_id = opening_actors
    client, headers, token = actors[0]
    headers = dict(headers, **{'X-Idempotency-Key': 'opening-edit-one'})
    body = {'quantity': 7, 'revision': token}
    first = client.post(f'/api/opening_stock/{line_id}', json=body, headers=headers)
    replay = client.post(f'/api/opening_stock/{line_id}', json=body, headers=headers)
    assert first.status_code == replay.status_code == 200, (first.json, replay.json)
    assert first.json == replay.json
    current = first.json['data'].get('revision')
    assert current
    next_save = client.post(f'/api/opening_stock/{line_id}',
                            json={'quantity': 8, 'revision': current}, headers=actors[0][1])
    assert next_save.status_code == 200, next_save.json
    with w.app.app_context():
        assert w.db.session.get(w.OpeningStock, line_id).quantity == 8


def test_orphan_opening_web_edit_uses_read_row_version(case):
    clients, ids = case
    created = clients[0].post('/opening_stock/save', json={
        'warehouse_id': ids['a'], 'date': date.today().isoformat(),
        'items': [{'material_id': ids['mats'][0], 'warehouse_id': ids['a'], 'quantity': 5, 'price': 2}],
    })
    assert created.status_code == 200, created.json
    with w.app.app_context():
        row = w.OpeningStock.query.one(); row.doc_id = None
        w.db.session.commit(); line_id = row.id
    data = dict(material_id=ids['mats'][0], warehouse_id=ids['a'], quantity=7, price=2,
                date=date.today().isoformat())
    endpoint = f'/opening_stock/edit/{line_id}'
    missing = clients[0].post(endpoint, data=data)
    assert missing.status_code == 409, missing.json
    listed = clients[0].get('/api/opening_stock', query_string={'warehouse_id': ids['a']})
    assert listed.status_code == 200, listed.json
    token = next(item['revision'] for item in listed.json['data']['items'] if item['id'] == line_id)
    saved = clients[0].post(endpoint, data=data, headers={'X-WMS-Document-Revision': token})
    assert saved.status_code == 200 and saved.json['status'] == 'success', saved.json
    stale = clients[0].post(endpoint, data=dict(data, quantity=9), headers={'X-WMS-Document-Revision': token})
    assert stale.status_code == 409, stale.json
    with w.app.app_context():
        assert w.db.session.get(w.OpeningStock, line_id).quantity == 7
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 37


def test_native_opening_missing_version_does_not_write(opening_actors):
    actors, _, line_id = opening_actors
    client, headers, _ = actors[0]
    with w.app.app_context():
        before = snapshot(w.InOrder)
    response = client.post(f'/api/opening_stock/{line_id}', json={'quantity': 999}, headers=headers)
    assert response.status_code == 409, response.json
    with w.app.app_context():
        assert snapshot(w.InOrder) == before
        assert w.db.session.get(w.OpeningStock, line_id).quantity == 5


def test_native_large_url_id_does_not_write(opening_actors):
    actors, _, _ = opening_actors
    client, headers, token = actors[0]
    with w.app.app_context():
        before = snapshot(w.InOrder)
    response = client.post(f'/api/opening_stock/{2**63}', json={'quantity': 7, 'revision': token}, headers=headers)
    assert response.status_code == 400, response.json
    with w.app.app_context():
        assert snapshot(w.InOrder) == before


@pytest.mark.parametrize('payload', [{'remark': [1]}, {'remark': {'bad': 'text'}},
    {'quantity': True}, {'price': [1]}, [1], {'request_id': [1], 'quantity': 7}])
def test_native_opening_bad_types_do_not_write(opening_actors, payload):
    actors, _, line_id = opening_actors
    client, headers, token = actors[0]
    if isinstance(payload, dict):
        payload = dict(payload, revision=token)
    with w.app.app_context():
        before = snapshot(w.InOrder)
    response = client.post(f'/api/opening_stock/{line_id}', json=payload, headers=headers)
    assert response.status_code == 400, response.json
    with w.app.app_context():
        assert snapshot(w.InOrder) == before
