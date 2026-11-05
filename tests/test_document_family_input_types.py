"""The same JSON text failure must be controlled in adjacent document families."""
import pytest
import app as w
from tests.test_document_create_number_conflicts import case, CASES, payload, snapshot


@pytest.mark.parametrize('entry', CASES, ids=[entry[0] for entry in CASES])
def test_document_family_text_types(case, entry):
    clients, ids = case
    kind, endpoint, model_name, _ = entry
    data = payload(kind, ids, 'TYPED-FAMILY-'+kind)
    if kind == 'transfer':
        data['header']['from_warehouse'] = ['not text']
    elif kind == 'check':
        data['header']['warehouse'] = ['not text']
    else:
        data['remark'] = {'not': 'text'}
    model = getattr(w, model_name)
    with w.app.app_context():
        before = snapshot(model)
    response = clients[0].post(endpoint, json=data)
    assert response.status_code == 400, response.json
    with w.app.app_context():
        assert snapshot(model) == before


@pytest.mark.parametrize('endpoint,model_name', [('/purchase_order/save','PurchaseOrder'),
    ('/sales/add','SalesOrder'), ('/requisition/save_table','ProductionRequisition'),
    ('/subcontract/add','SubcontractOrder'), ('/opening_stock/save','OpeningStockDoc')])
def test_other_document_text_types_are_rejected_before_creation(case, endpoint, model_name):
    clients, ids = case
    with w.app.app_context():
        before = snapshot(w.InOrder)
        count = getattr(w, model_name).query.count()
    response = clients[0].post(endpoint, json={'remark': ['not text'], 'warehouse_id': ids['a']})
    assert response.status_code == 400, response.json
    assert response.json['code'] == 'INVALID_DOCUMENT_INPUT'
    with w.app.app_context():
        assert getattr(w, model_name).query.count() == count
        assert snapshot(w.InOrder) == before
