"""Two independent operators must not silently overwrite a stale document page."""
import re

import pytest
import app as w
from tests.test_web_document_idempotency import receipt_case
from tests.test_document_create_number_conflicts import case as family_case, CASES, payload as family_payload


def revision(client, path):
    response = client.get(path)
    assert response.status_code == 200
    match = re.search(r'<meta name="document-revision" content="([^"]*)"', response.text)
    return match.group(1) if match else response.headers.get('X-WMS-Document-Read-Revision', '')


@pytest.fixture
def operators(receipt_case):
    client, payload = receipt_case
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 200
    with w.app.app_context():
        uid = w.User(username='second-operator', role='admin', password_hash='unused',
                     must_change_password=False)
        w.db.session.add(uid)
        w.db.session.commit()
        user_id = uid.id
        order_id = w.InOrder.query.one().id
    second = w.app.test_client()
    with second.session_transaction() as s:
        s['_user_id'] = str(user_id)
        s['_fresh'] = True
    yield client, second, order_id, payload


def test_guarded_document_write(operators):
    first, second, oid, payload = operators
    path = f'/in_order/add?order_id={oid}'
    one = revision(first, path)
    two = revision(second, path)
    edited = dict(payload, order_id=oid, remark='first operator saved')
    saved = first.post('/in_order/add', json=edited,
                       headers={'X-WMS-Document-Revision': one})
    assert saved.status_code == 200, saved.json
    stale = second.post('/in_order/add', json=dict(edited, remark='stale overwrite'),
                        headers={'X-WMS-Document-Revision': two})
    assert stale.status_code == 409, stale.json
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).remark == 'first operator saved'
        assert w.Material.query.one().stock == 0


def test_page_revision(operators):
    first, second, oid, payload = operators
    path = f'/in_order/add?order_id={oid}'
    one, two = revision(first, path), revision(second, path)
    assert one and two and one != two
    for c, value in [(first, 'first'), (second, 'refreshed')]:
        token = revision(c, path)
        result = c.post('/in_order/add', json=dict(payload, order_id=oid, remark=value),
                        headers={'X-WMS-Document-Revision': token})
        assert result.status_code == 200, result.json
        assert result.headers.get('X-WMS-Document-Revision')
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).remark == 'refreshed'


@pytest.mark.parametrize('entry', CASES, ids=[c[0] for c in CASES])
def test_document_family_rejects_stale_full_form(family_case, entry):
    clients, ids = family_case
    kind, endpoint, model_name, _ = entry
    data = family_payload(kind, ids, 'VERSION-' + kind)
    created = clients[0].post(endpoint, json=data)
    assert created.status_code == 200, created.json
    oid = created.json['id']
    with w.app.app_context():
        other = w.User(username='other-editor', role='admin', password_hash='unused', must_change_password=False)
        w.db.session.add(other); w.db.session.commit(); uid = other.id
    with clients[1].session_transaction() as session:
        session['_user_id'] = str(uid); session['_fresh'] = True
    if kind in ('sale', 'other', 'requisition'):
        page = f'/out_order/add?order_id={oid}'
    elif kind == 'after':
        page = f'/after_sale_out/{oid}/edit'
    elif kind == 'request':
        page = f'/purchase_request/{oid}/edit'
    else:
        page = '/' + endpoint.split('/')[1] + '/' + str(oid)
    one, two = [revision(c, page) for c in clients]
    assert one and two
    key = 'request_id' if kind == 'request' else 'order_id'
    edited = family_payload(kind, ids, data['order_no'], second=True)
    edited[key] = oid
    first = clients[0].post(endpoint, json=edited, headers={'X-WMS-Document-Revision': one})
    assert first.status_code == 200, first.json
    stale = clients[1].post(endpoint, json=dict(data, **{key: oid}), headers={'X-WMS-Document-Revision': two})
    assert stale.status_code == 409, stale.json
    with w.app.app_context():
        doc = w.db.session.get(getattr(w, model_name), oid)
        assert doc.items[0].material_id == ids['mats'][1]
        assert w.Material.query.order_by(w.Material.id).first().stock == 30


def test_revision_is_user_bound_and_invalid_signature_cannot_write(operators):
    first, second, oid, payload = operators
    token = revision(first, f'/in_order/add?order_id={oid}')
    assert token
    data = dict(payload, order_id=oid, remark='forged')
    for client, value in [(second, token), (first, token + 'broken')]:
        response = client.post('/in_order/add', json=data, headers={'X-WMS-Document-Revision': value})
        assert response.status_code == 409
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).remark != 'forged'


def test_stale_line_and_completion_are_rejected(operators):
    first, second, oid, payload = operators
    path = f'/in_order/{oid}'
    stale = revision(second, path)
    current = revision(first, path)
    with w.app.app_context():
        item_id = w.db.session.get(w.InOrder, oid).items[0].id
    changed = first.post('/in_order/item/update', data={'id': item_id, 'quantity': '3'},
                         headers={'X-WMS-Document-Revision': current})
    assert changed.status_code == 200 and changed.json['status'] == 'success', changed.json
    for endpoint, data in [(f'/in_order/{oid}/complete', {}),
                           ('/in_order/item/update', {'id': item_id, 'quantity': '9'})]:
        response = second.post(endpoint, data=data, headers={'X-WMS-Document-Revision': stale})
        assert response.status_code == 409, response.json
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).status == 'pending'
        assert w.db.session.get(w.InOrderItem, item_id).quantity == 3
        assert w.Material.query.one().stock == 0


def test_success_header_supports_next_save_without_reloading(operators):
    first, _, oid, payload = operators
    token = revision(first, f'/in_order/add?order_id={oid}')
    for remark in ['save-one', 'save-two', 'save-three']:
        response = first.post('/in_order/add', json=dict(payload, order_id=oid, remark=remark),
                              headers={'X-WMS-Document-Revision': token})
        assert response.status_code == 200, response.json
        next_token = response.headers.get('X-WMS-Document-Revision')
        assert next_token and next_token != token
        token = next_token
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).remark == 'save-three'


def test_failed_commit_rolls_back_and_original_revision_can_retry(operators):
    from sqlalchemy import event
    first, _, oid, payload = operators
    token = revision(first, f'/in_order/add?order_id={oid}')
    with w.app.app_context():
        engine = w.db.engine
    def fail_commit(connection):
        raise RuntimeError('synthetic commit failure')
    event.listen(engine, 'commit', fail_commit)
    try:
        response = first.post('/in_order/add', json=dict(payload, order_id=oid, remark='must rollback'),
                              headers={'X-WMS-Document-Revision': token})
        assert response.json['status'] == 'error'
        assert not response.headers.get('X-WMS-Document-Revision')
    finally:
        event.remove(engine, 'commit', fail_commit)
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).remark != 'must rollback'
    retry = first.post('/in_order/add', json=dict(payload, order_id=oid, remark='retry saved'),
                       headers={'X-WMS-Document-Revision': token})
    assert retry.status_code == 200, retry.json


def test_two_real_connections_accept_only_one_old_page(operators, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import create_engine
    _, _, _, payload = operators
    engine = create_engine('sqlite:///' + str(tmp_path / 'two-operators.db'), connect_args={'timeout': 30})
    with w.app.app_context():
        w.db.session.remove()
        monkeypatch.setitem(w.db.engines, None, engine)
        w.db.create_all()
        users = [w.User(username='connection-' + str(i), role='admin', password_hash='unused',
                        must_change_password=False) for i in range(2)]
        wh = w.Warehouse(code='RETRY', name='重试仓', status='active', is_default=True)
        material = w.Material(code='RETRY', name='重试物料', stock=0)
        w.db.session.add_all([*users, wh, material]); w.db.session.commit()
        user_ids = [u.id for u in users]; payload = dict(payload, warehouse_id=wh.id)
        w.db.session.remove()
    clients = [w.app.test_client() for _ in users]
    for c, uid in zip(clients, user_ids):
        with c.session_transaction() as session:
            session['_user_id'] = str(uid); session['_fresh'] = True
    created = clients[0].post('/in_order/add', json=payload)
    assert created.status_code == 200, created.json
    oid = created.json['id']
    tokens = [revision(c, f'/in_order/add?order_id={oid}') for c in clients]
    gate = Barrier(2)
    def send(index):
        gate.wait(timeout=10)
        response = clients[index].post('/in_order/add', json=dict(payload, order_id=oid, remark=f'writer-{index}'),
                                       headers={'X-WMS-Document-Revision': tokens[index]})
        return index, response.status_code, response.json
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        assert sorted(r[1] for r in results) == [200, 409], results
        winner = next(r[0] for r in results if r[1] == 200)
        with w.app.app_context():
            assert w.InOrder.query.count() == 1
            assert w.db.session.get(w.InOrder, oid).remark == f'writer-{winner}'
            assert w.Material.query.one().stock == 0
            w.db.session.remove()
    finally:
        engine.dispose()


def test_csrf_and_read_only_role_still_precede_edit_guard(operators, monkeypatch):
    first, second, oid, payload = operators
    token = revision(first, f'/in_order/add?order_id={oid}')
    data = dict(payload, order_id=oid)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    response = first.post('/in_order/add', json=data,
                          headers={'X-WMS-Document-Revision': token, 'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 400
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        user = w.User.query.filter_by(username='second-operator').one()
        user.role = 'finance'; w.db.session.commit()
    response = second.post('/in_order/add', json=data,
                           headers={'X-WMS-Document-Revision': 'invalid', 'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 403


@pytest.mark.parametrize('kind', ['purchase', 'sales', 'production', 'subcontract', 'opening'])
def test_remaining_editable_document_forms(family_case, kind):
    from datetime import date
    clients, ids = family_case
    with w.app.app_context():
        supplier = w.Supplier(code='EDIT-S', name='版本供应商')
        customer = w.Customer(code='EDIT-C', name='版本客户')
        w.db.session.add_all([supplier, customer]); w.db.session.commit()
        sid, cid = supplier.id, customer.id
    line = dict(material_id=ids['mats'][0], code='DC-M1', quantity=1, price=2,
                warehouse_id=ids['a'])
    data = dict(warehouse_id=ids['a'], supplier_id=sid, customer_id=cid,
                date=date.today().isoformat(), remark='original', items=[line])
    if kind == 'purchase':
        endpoint, model, key = '/purchase_order/save', w.PurchaseOrder, 'order_id'
    elif kind == 'sales':
        endpoint, model, key = '/sales/add', w.SalesOrder, 'unused'
    elif kind == 'production':
        endpoint, model, key = '/requisition/save_table', w.ProductionRequisition, 'order_id'
        data['header'] = {'warehouse_id': ids['a'], 'remark': 'original'}
    elif kind == 'opening':
        endpoint, model, key = '/opening_stock/save', w.OpeningStockDoc, 'doc_id'
    else:
        endpoint, model, key = '/subcontract/add', w.SubcontractOrder, 'unused'
    created = clients[0].post(endpoint, data=data if kind == 'subcontract' else None,
                              json=data if kind != 'subcontract' else None)
    assert created.status_code == 200 and created.json['status'] == 'success', created.json
    with w.app.app_context():
        oid = model.query.one().id
        stocks = [(m.id, m.stock) for m in w.Material.query.order_by(w.Material.id)]
        other = w.User(username='independent-editor', role='admin', password_hash='unused', must_change_password=False)
        w.db.session.add(other); w.db.session.commit(); uid = other.id
    with clients[1].session_transaction() as session:
        session['_user_id'] = str(uid); session['_fresh'] = True
    paths = {'purchase': f'/purchase_order/{oid}/edit', 'sales': f'/sales/{oid}/edit',
             'production': f'/requisition/{oid}', 'opening': f'/opening_stock/{oid}',
             'subcontract': f'/subcontract/{oid}'}
    tokens = [revision(c, paths[kind]) for c in clients]
    assert all(tokens)
    if kind == 'sales':
        endpoint = f'/sales/{oid}/edit'
    elif kind == 'subcontract':
        endpoint = f'/subcontract/{oid}/edit'
    else:
        data[key] = oid
    edited = dict(data, remark='saved-first')
    if kind == 'production':
        edited['header'] = dict(data['header'], remark='saved-first')
    first = clients[0].post(endpoint, json=edited, headers={'X-WMS-Document-Revision': tokens[0]})
    assert first.status_code == 200 and first.json['status'] == 'success', first.json
    stale = clients[1].post(endpoint, json=data, headers={'X-WMS-Document-Revision': tokens[1]})
    assert stale.status_code == 409, stale.json
    missing = clients[1].post(endpoint, json=data)
    assert missing.status_code == 409, missing.json
    assert missing.json['code'] == 'DOCUMENT_REVISION_REQUIRED'
    missing = clients[1].post(endpoint, json=data)
    assert missing.status_code == 409, missing.json
    assert missing.json['code'] == 'DOCUMENT_REVISION_REQUIRED'
    with w.app.app_context():
        assert w.db.session.get(model, oid).remark == 'saved-first'
        assert [(m.id, m.stock) for m in w.Material.query.order_by(w.Material.id)] == stocks


def test_stale_delete_rejected_and_current_draft_delete_still_works(operators):
    first, second, oid, payload = operators
    path = f'/in_order/{oid}'
    stale = revision(second, path)
    token = revision(first, path)
    changed = first.post('/in_order/add', json=dict(payload, order_id=oid, remark='keep latest'),
                         headers={'X-WMS-Document-Revision': token})
    assert changed.status_code == 200
    response = second.post(f'/in_order/{oid}/delete', headers={'X-WMS-Document-Revision': stale})
    assert response.status_code == 409
    token = revision(first, path)
    response = first.post(f'/in_order/{oid}/delete', headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid) is None
        assert w.Material.query.one().stock == 0


def test_signed_native_form_header_edit_preserves_csrf_and_revision(operators):
    from datetime import date
    first, second, oid, payload = operators
    path = f'/in_order/{oid}'
    one, stale = revision(first, path), revision(second, path)
    data = dict(date=date.today().isoformat(), warehouse_id=payload['warehouse_id'], remark='form-saved',
                document_revision=one)
    response = first.post(f'/in_order/{oid}/update', data=data)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    response = second.post(f'/in_order/{oid}/update', data=dict(data, remark='stale', document_revision=stale))
    assert response.status_code == 409


def test_legacy_http_200_error_does_not_return_uncommitted_revision(operators):
    from flask import jsonify
    from flask_login import login_user
    from sqlalchemy import event
    from services.document_edit_guard import guarded_document_write
    first, _, oid, _ = operators
    token = revision(first, f'/in_order/{oid}')
    with w.app.app_context():
        engine = w.db.engine
        uid = w.User.query.filter_by(username='retry-test').one().id
    def fail_commit(connection):
        raise RuntimeError('synthetic commit failure')
    def legacy_error_view():
        order = w.db.session.get(w.InOrder, oid)
        order.remark = 'must not persist'
        try:
            w.db.session.commit()
        except RuntimeError:
            w.db.session.rollback()
            return jsonify(status='error', msg='legacy error envelope')
        pytest.fail('commit fault was not exercised')
    event.listen(engine, 'commit', fail_commit)
    try:
        with w.app.test_request_context(f'/in_order/{oid}/update', method='POST', headers={'X-WMS-Document-Revision': token}):
            login_user(w.db.session.get(w.User, uid))
            response = guarded_document_write(legacy_error_view)
            assert response.status_code == 200 and response.json['status'] == 'error'
            assert not response.headers.get('X-WMS-Document-Revision')
    finally:
        event.remove(engine, 'commit', fail_commit)
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).remark != 'must not persist'


def test_non_http_template_render_has_no_document_revision():
    from services.document_edit_guard import page_revision
    with w.app.app_context():
        assert page_revision() == {}


def _independent_editor(clients):
    with w.app.app_context():
        user = w.User(username='independent-line-editor', role='admin', password_hash='unused', must_change_password=False)
        w.db.session.add(user); w.db.session.commit(); uid = user.id
    with clients[1].session_transaction() as session:
        session['_user_id'] = str(uid); session['_fresh'] = True


def test_inline_check_path_without_update_word_still_rejects_stale_page(family_case):
    clients, ids = family_case
    _independent_editor(clients)
    response = clients[0].post('/check/save_table', json=family_payload('check', ids, 'INLINE-CHECK'))
    assert response.status_code == 200, response.json
    oid = response.json['id']
    with w.app.app_context():
        item_id = w.db.session.get(w.InventoryCheck, oid).items[0].id
    tokens = [revision(c, f'/check/{oid}') for c in clients]
    assert all(tokens)
    endpoint = f'/check/{oid}/item/{item_id}'
    first = clients[0].post(endpoint, data={'actual_stock': '2'}, headers={'X-WMS-Document-Revision': tokens[0]})
    assert first.status_code == 200 and first.json['status'] == 'success', first.json
    stale = clients[1].post(endpoint, data={'actual_stock': '3'}, headers={'X-WMS-Document-Revision': tokens[1]})
    assert stale.status_code == 409, stale.json
    with w.app.app_context():
        assert w.db.session.get(w.InventoryCheckItem, item_id).actual_stock == 2


def test_opening_stock_inline_edit_resolves_parent_revision(family_case):
    from datetime import date, timedelta
    clients, ids = family_case
    _independent_editor(clients)
    data = dict(warehouse_id=ids['a'], date=date.today().isoformat(),
                items=[dict(material_id=ids['mats'][0], warehouse_id=ids['a'], quantity=1, price=2)])
    response = clients[0].post('/opening_stock/save', json=data)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    with w.app.app_context():
        doc = w.OpeningStockDoc.query.one(); oid = doc.id; line_id = doc.lines[0].id
    tokens = [revision(c, f'/opening_stock/{oid}') for c in clients]
    assert all(tokens)
    line = dict(material_id=ids['mats'][0], warehouse_id=ids['a'], quantity=2, price=2, date=date.today().isoformat())
    endpoint = f'/opening_stock/edit/{line_id}'
    first = clients[0].post(endpoint, data=line, headers={'X-WMS-Document-Revision': tokens[0]})
    assert first.status_code == 200 and first.json['status'] == 'success', first.json
    stale = clients[1].post(endpoint, data=dict(line, quantity=3), headers={'X-WMS-Document-Revision': tokens[1]})
    assert stale.status_code == 409, stale.json
    with w.app.app_context():
        assert w.db.session.get(w.OpeningStock, line_id).quantity == 2
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 32
    tokens = [revision(c, f'/opening_stock/{oid}') for c in clients]
    previous_day = date.today() - timedelta(days=1)
    first = clients[0].post(f'/opening_stock/{oid}/date', json={'date':previous_day.isoformat()},
                            headers={'X-WMS-Document-Revision':tokens[0]})
    assert first.status_code == 200 and first.json['status'] == 'success', first.json
    stale = clients[1].post(f'/opening_stock/{oid}/date', json={'date':date.today().isoformat()},
                            headers={'X-WMS-Document-Revision':tokens[1]})
    assert stale.status_code == 409, stale.json
    with w.app.app_context():
        assert w.db.session.get(w.OpeningStockDoc, oid).date == previous_day
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 32


def test_copy_remains_a_new_intent_using_current_source(operators):
    first, second, oid, payload = operators
    old = revision(second, f'/in_order/{oid}')
    current = revision(first, f'/in_order/{oid}')
    response = first.post('/in_order/add', json=dict(payload, order_id=oid, remark='current source'),
                          headers={'X-WMS-Document-Revision': current})
    assert response.status_code == 200
    response = second.post(f'/in_order/{oid}/copy', headers={'X-WMS-Document-Revision': old})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert not response.headers.get('X-WMS-Document-Revision')
    with w.app.app_context():
        assert w.InOrder.query.count() == 2
        assert w.db.session.get(w.InOrder, oid).remark == 'current source'
        assert w.Material.query.one().stock == 0


@pytest.mark.parametrize('change', ['replace', 'delete'])
def test_disappeared_inline_row_still_returns_recoverable_conflict(operators, change):
    first, second, oid, payload = operators
    one, old = revision(first, f'/in_order/{oid}'), revision(second, f'/in_order/{oid}')
    with w.app.app_context():
        item_id = w.db.session.get(w.InOrder, oid).items[0].id
    if change == 'replace':
        # Another document makes a replacement row receive a different SQLite ID.
        assert first.post('/in_order/add', json=dict(payload, remark='unrelated')).status_code == 200
        response = first.post('/in_order/add', json=dict(payload, order_id=oid, remark='replaced'),
                              headers={'X-WMS-Document-Revision': one})
    else:
        response = first.post(f'/in_order/{oid}/delete_item/{item_id}', headers={'X-WMS-Document-Revision': one})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    with w.app.app_context():
        assert w.db.session.get(w.InOrderItem, item_id) is None
    response = second.post('/in_order/item/update', data={'id':item_id,'quantity':7.25},
                           headers={'X-WMS-Document-Revision': old})
    assert response.status_code == 409 and response.json['code'] == 'DOCUMENT_EDIT_CONFLICT', response.json
    with w.app.app_context():
        assert w.Material.query.one().stock == 0
