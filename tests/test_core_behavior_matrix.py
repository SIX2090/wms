"""Stock/state matrix with real handlers, two warehouses and historical attribution."""
from datetime import datetime

import pytest
import app as w
from tests.test_document_create_number_conflicts import case as family_case, payload
from tests.test_document_edit_conflicts import revision


CASES = [
    ('in', '/in_order/add', 'InOrder', 'in_order', 1, True),
    ('sale', '/out_order/add', 'OutOrder', 'out_order', -1, True),
    ('other', '/out_order/add', 'OutOrder', 'out_order', -1, True),
    ('requisition', '/out_order/add', 'OutOrder', 'out_order', -1, True),
    ('after', '/after_sale_out/add', 'AfterSaleOutOrder', 'after_sale_out', -1, True),
    ('transfer', '/transfer/save_table', 'TransferOrder', 'transfer', 0, True),
    ('check', '/check/save_table', 'InventoryCheck', 'check', 0, True),
    ('adjustment', '/adjustment/add', 'AdjustmentOrder', 'adjustment', 1, True),
    ('production', '/requisition/save_table', 'ProductionRequisition', 'requisition', -1, False),
]


@pytest.mark.parametrize('kind,save,model_name,domain,delta,reversible', CASES, ids=[c[0] for c in CASES])
def test_signed_completion_repetition_and_reversion(family_case, kind, save, model_name, domain, delta, reversible):
    clients, ids = family_case
    client = clients[0]
    data = payload(kind, ids, 'MATRIX-' + kind)
    if kind == 'in':
        data['business_type'] = '产品入库'
    if kind == 'production':
        data['header']['warehouse_id'] = ids['a']
    result = client.post(save, json=data)
    assert result.status_code == 200 and result.json['status'] == 'success', result.json
    model = getattr(w, model_name)
    with w.app.app_context():
        doc = model.query.one(); oid = doc.id
        if kind == 'check':
            # A counted/frozen synthetic batch is the valid completion precondition.
            doc.frozen_at = datetime.now()
            for item in doc.items:
                item.counted_by = ids['user']; item.counted_at = datetime.now()
            w.db.session.commit()
    page = f'/{domain}/{oid}'
    token = revision(client, page)
    assert token
    response = client.post(f'/{domain}/{oid}/complete?force=true', json={'force': True},
                           headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    def assert_balances(expected_delta):
        with w.app.app_context():
            material = w.db.session.get(w.Material, ids['mats'][0])
            a = w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, ids['a'])).get(material.id, 0)
            b = w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, ids['b'])).get(material.id, 0)
            transfer = expected_delta == 0 and kind == 'transfer' and w.db.session.get(model, oid).status == 'completed'
            assert material.stock == 30 + expected_delta
            assert a == (19 if transfer else 20 + expected_delta)
            assert b == (11 if transfer else 10)
            assert a + b == material.stock
            transactions = w.StockTransaction.query.filter_by(material_id=material.id).all()
            assert sum(t.quantity for t in transactions) == material.stock
            return [(t.id, t.quantity) for t in transactions]
    before = assert_balances(delta)
    repeated = client.post(f'/{domain}/{oid}/complete?force=true', json={'force': True},
                           headers={'X-WMS-Document-Revision': token})
    assert repeated.status_code >= 400 and repeated.json['status'] == 'error'
    assert assert_balances(delta) == before
    if reversible:
        token = revision(client, page)
        reverted = client.post(f'/{domain}/{oid}/revert', headers={'X-WMS-Document-Revision': token})
        assert reverted.status_code == 200 and reverted.json['status'] == 'success', reverted.json
        with w.app.app_context():
            assert w.db.session.get(model, oid).status == 'pending'
        before = assert_balances(0)
        repeated = client.post(f'/{domain}/{oid}/revert', headers={'X-WMS-Document-Revision': token})
        assert repeated.status_code >= 400 and repeated.json['status'] == 'error'
        assert assert_balances(0) == before
