"""Missing revisions cannot silently turn an old editor into a current writer."""
import pytest
import app as w
from tests.test_document_edit_conflicts import operators, revision
from tests.test_web_document_idempotency import receipt_case
from tests.test_document_create_number_conflicts import case, CASES, payload, snapshot
from tests.test_document_edit_route_coverage import subcontract_case


@pytest.mark.parametrize('entry', CASES, ids=[entry[0] for entry in CASES])
@pytest.mark.parametrize('transport', ['json', 'form'])
def test_guarded_document_write_requires_revision(case, entry, transport):
    clients, ids = case
    kind, endpoint, model_name, _ = entry
    created = clients[0].post(endpoint, json=payload(kind, ids, 'REQUIRED-'+kind))
    assert created.status_code == 200, created.json
    oid = created.json['id']
    model = getattr(w, model_name)
    data = payload(kind, ids, 'REQUIRED-'+kind, True)
    data['request_id' if kind == 'request' else 'order_id'] = oid
    with w.app.app_context():
        before = snapshot(model)
    response = clients[1].post(endpoint, **{transport if transport == 'json' else 'data': data})
    assert response.status_code == 409, response.json
    assert response.json['code'] == 'DOCUMENT_REVISION_REQUIRED'
    with w.app.app_context():
        assert snapshot(model) == before


def test_missing_revision_after_other_account_save_is_not_a_bypass(operators):
    first, second, oid, data = operators
    revision(second, f'/in_order/{oid}')
    token = revision(first, f'/in_order/{oid}')
    saved = first.post('/in_order/add', json=dict(data, order_id=oid, remark='A saved'),
                       headers={'X-WMS-Document-Revision': token})
    assert saved.status_code == 200, saved.json
    stale = second.post('/in_order/add', json=dict(data, order_id=oid, remark='B stale'))
    assert stale.status_code == 409 and stale.json['code'] == 'DOCUMENT_REVISION_REQUIRED'
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).remark == 'A saved'


def test_large_url_item_id_is_controlled(operators):
    first, _, oid, _ = operators
    token = revision(first, f'/in_order/{oid}')
    with w.app.app_context():
        before = snapshot(w.InOrder)
    response = first.post(f'/in_order/{oid}/delete_item/{2**63}',
                          headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 400 and response.json['code'] == 'INVALID_DOCUMENT_ID', response.json
    with w.app.app_context():
        assert snapshot(w.InOrder) == before


def test_zero_alias_cannot_hide_purchase_request_edit(case):
    clients, ids = case
    data = payload('request', ids, 'REQUIRED-ALIAS')
    created = clients[0].post('/purchase_request/add', json=data)
    assert created.status_code == 200, created.json
    oid = created.json['id']
    with w.app.app_context():
        before = snapshot(w.PurchaseRequest)
    response = clients[1].post('/purchase_request/add',
        json=dict(data, order_id='0', request_id=oid, remark='must not overwrite'))
    assert response.status_code == 409 and response.json['code'] == 'DOCUMENT_REVISION_REQUIRED'
    with w.app.app_context():
        assert snapshot(w.PurchaseRequest) == before


def test_conflicting_document_id_aliases_never_choose_a_target(case):
    clients, ids = case
    data = payload('other', ids, 'REQUIRED-CONFLICTING-ID')
    created = clients[0].post('/out_order/add', json=data)
    assert created.status_code == 200, created.json
    with w.app.app_context():
        before = snapshot(w.OutOrder)
    response = clients[0].post('/out_order/add', json=dict(data, order_id=created.json['id'], id=999))
    assert response.status_code == 400 and response.json['code'] == 'INVALID_DOCUMENT_ID'
    with w.app.app_context():
        assert snapshot(w.OutOrder) == before


@pytest.mark.parametrize('invalid', [True, 1.5, [1], {'id': 1}, 2**63, '-1'])
def test_positive_id(case, invalid):
    clients, ids = case
    data = payload('request', ids, 'REQUIRED-TYPED-ID')
    created = clients[0].post('/purchase_request/add', json=data)
    assert created.status_code == 200, created.json
    with w.app.app_context():
        before = snapshot(w.PurchaseRequest)
    response = clients[0].post('/purchase_request/add',
        json=dict(data, request_id=invalid, remark='must not choose or create a record'))
    assert response.status_code == 400 and response.json['code'] == 'INVALID_DOCUMENT_ID', response.json
    with w.app.app_context():
        assert snapshot(w.PurchaseRequest) == before


def test_edit_endpoint_registry_names_are_real():
    from services.document_edit_guard import EDIT_ENDPOINTS
    assert EDIT_ENDPOINTS <= set(w.app.view_functions)


@pytest.mark.parametrize('family,model_name,number_field', [
    ('subcontract_issue', 'SubcontractIssue', 'issue_no'),
    ('subcontract_receive', 'SubcontractReceive', 'receive_no'),
])
def test_missing_subcontract_detail_revision(subcontract_case, family, model_name, number_field):
    client, ids = subcontract_case
    model = getattr(w, model_name)
    with w.app.app_context():
        row = model(**{number_field: 'REQUIRED-'+family}, subcontract_order_id=ids['order'],
                    warehouse=w.db.session.get(w.Warehouse, ids['a']).name, status='pending')
        w.db.session.add(row); w.db.session.commit(); oid = row.id
    data = {'material_code': 'SIGN-M', 'quantity': '1', 'price': '1', 'location': 'L-1'}
    endpoint = f'/{family}/{oid}/item/add'
    missing = client.post(endpoint, data=data)
    assert missing.status_code == 409 and missing.json['code'] == 'DOCUMENT_REVISION_REQUIRED'
    token = revision(client, f'/{family}/{oid}')
    saved = client.post(endpoint, data=data, headers={'X-WMS-Document-Revision': token})
    assert saved.status_code == 200 and saved.json['status'] == 'success', saved.json
    stale = client.post(endpoint, data=data, headers={'X-WMS-Document-Revision': token})
    assert stale.status_code == 409, stale.json
    with w.app.app_context():
        assert len(w.db.session.get(model, oid).items) == 1
