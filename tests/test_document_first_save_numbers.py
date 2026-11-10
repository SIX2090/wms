"""Remaining create consumers share formal numbering and immutable edit IDs."""
import pytest

import app as w
from tests.test_document_create_number_conflicts import case, payload
from tests.document_revision_client import document_post


@pytest.mark.parametrize('endpoint,model_name,field,prefix', [
    ('/purchase_order/save', 'PurchaseOrder', 'order_no', 'PO'),
    ('/requisition/save_table', 'ProductionRequisition', 'req_no', 'REQ'),
    ('/bom/save_table', 'BOM', 'bom_no', 'BOM'),
])
def test_new_document_ignores_preview_and_replays_same_request(case, endpoint, model_name, field, prefix):
    clients, ids = case
    data = payload('request', ids, 'STALE-PREVIEW')
    data['header'].update(product_code='NEW-PRODUCT', product_name='合成产品', warehouse=ids['names'][0])
    data.update(warehouse=ids['names'][0], bom_no='STALE-PREVIEW', req_no='STALE-PREVIEW')
    headers = {'X-Idempotency-Key': 'first-save'}
    first = clients[0].post(endpoint, json=data, headers=headers)
    assert first.status_code == 200 and first.json['status'] == 'success', first.json
    replay = clients[0].post(endpoint, json=data, headers=headers)
    assert replay.status_code == 200 and replay.json == first.json
    second = clients[1].post(endpoint, json=data, headers={'X-Idempotency-Key': 'second-save'})
    assert second.status_code == 200 and second.json['status'] == 'success', second.json
    assert first.json['id'] != second.json['id']
    with w.app.app_context():
        model = getattr(w, model_name)
        records = model.query.order_by(model.id).all()
        numbers = [getattr(row, field) for row in records]
        assert len(records) == len(set(numbers)) == 2
        assert all(number.startswith(prefix) for number in numbers)
        original = numbers[0]
    edited = dict(data, order_id=first.json['id'], order_no='ALTERED-PREVIEW')
    response = document_post(clients[0], endpoint, json=edited)
    assert response.status_code == 200 and response.json['id'] == first.json['id'], response.json
    with w.app.app_context():
        assert getattr(w.db.session.get(model, first.json['id']), field) == original
        assert model.query.count() == 2
        assert [m.stock for m in w.Material.query.order_by(w.Material.id)] == [30, 30]


@pytest.mark.parametrize('endpoint,model_name,field,prefix', [
    ('/subcontract/add', 'SubcontractOrder', 'order_no', 'SC'),
    ('/subcontract_issue/add', 'SubcontractIssue', 'issue_no', 'SF'),
    ('/subcontract_receive/add', 'SubcontractReceive', 'receive_no', 'SR'),
])
def test_subcontract_create_ignores_stale_number_and_keeps_replay(case, endpoint, model_name, field, prefix):
    clients, ids = case
    with w.app.app_context():
        parent = w.SubcontractOrder(order_no='HISTORICAL-PARENT', warehouse=ids['names'][0])
        w.db.session.add(parent)
        w.db.session.commit()
        parent_id = parent.id
    data = {field: 'STALE-PREVIEW', 'subcontract_order_id': parent_id, 'warehouse_id': ids['a']}
    first = clients[0].post(endpoint, data=data, headers={'X-Idempotency-Key': 'first'})
    assert first.status_code == 200 and first.json['status'] == 'success', first.get_data(as_text=True)
    replay = clients[0].post(endpoint, data=data, headers={'X-Idempotency-Key': 'first'})
    assert replay.status_code == 200 and replay.json == first.json
    second = clients[1].post(endpoint, data=data, headers={'X-Idempotency-Key': 'second'})
    assert second.status_code == 200 and second.json['status'] == 'success', second.json
    with w.app.app_context():
        model = getattr(w, model_name)
        records = model.query.filter(getattr(model, field).like(prefix+'%')).all()
        assert len(records) == len({getattr(row, field) for row in records}) == 2
        assert [m.stock for m in w.Material.query.order_by(w.Material.id)] == [30, 30]
