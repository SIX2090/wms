import json

import pytest

import app as wms
from tests.test_document_create_number_conflicts import case, rows, snapshot
from tests.test_web_stock_posting_audit import fail_audit, posting_actors


@pytest.mark.parametrize('direction', ['issue', 'receive'])
@pytest.mark.parametrize('action', ['quick', 'complete', 'revert'])
def test_subcontract_stock_audit_rolls_back_document_stock_and_parent(posting_actors, direction, action):
    creator, poster, ids = posting_actors
    issuing = direction == 'issue'
    model = wms.SubcontractIssue if issuing else wms.SubcontractReceive
    item_model = wms.SubcontractIssueItem if issuing else wms.SubcontractReceiveItem
    kind = f'subcontract_{direction}'
    number_key = f'{direction}_no'
    material_id = ids['mats'][0]
    with wms.app.app_context():
        wms.db.session.get(wms.User, ids['poster']).role = 'production'
        parent = wms.SubcontractOrder(order_no='SUBCONTRACT-AUDIT', status='pending',
                                      warehouse=ids['names'][0], operator_id=ids['user'])
        wms.db.session.add(parent)
        wms.db.session.flush()
        parent_id = parent.id
        wms.db.session.add(wms.SubcontractItem(subcontract_order_id=parent_id, material_id=material_id, quantity=3))
        order_id = None
        if action != 'quick':
            order = model(subcontract_order_id=parent_id, operator_id=ids['user'], status='pending',
                          warehouse=ids['names'][0], **{number_key: 'SUB-AUDIT-DRAFT'})
            wms.db.session.add(order)
            wms.db.session.flush()
            order_id = order.id
            wms.db.session.add(item_model(material_id=material_id, quantity=3, **{f'{direction}_id': order_id}))
        wms.db.session.commit()
    if action == 'revert':
        prepared = creator.post(f'/{kind}/{order_id}/complete')
        assert prepared.json['status'] == 'success', prepared.json
    with wms.app.app_context():
        before = snapshot(model), rows(wms.SubcontractOrder), rows(wms.SubcontractProgress), rows(wms.OperationAudit)

    operation = f'{"revert" if action == "revert" else "complete"}_{kind}'
    url = f'/subcontract/{parent_id}/{direction}' if action == 'quick' else f'/{kind}/{order_id}/{action}'
    data = {'material_code': 'DC-M1', 'quantity': '3', 'price': '2'} if action == 'quick' else {}
    with fail_audit(operation, order_id) as attempted:
        failed = poster.post(url, data=data)
    assert failed.json['status'] == 'error', failed.json
    assert len(attempted) == 1
    with wms.app.app_context():
        assert (snapshot(model), rows(wms.SubcontractOrder), rows(wms.SubcontractProgress),
                rows(wms.OperationAudit)) == before

    response = poster.post(url, data=data)
    assert response.json['status'] == 'success', response.json
    with wms.app.app_context():
        order = model.query.one()
        audit = wms.OperationAudit.query.filter_by(operation=operation, target_type=kind, target_id=order.id).one()
        assert audit.user_id == ids['poster'] and audit.username == 'web-stock-poster'
        assert audit.target_name == getattr(order, number_key)
        old = json.loads(audit.old_data) if audit.old_data else None
        new = json.loads(audit.new_data)
        assert old == (None if action == 'quick' else {'status': 'completed' if action == 'revert' else 'pending'})
        assert new['status'] == order.status == ('pending' if action == 'revert' else 'completed')
        assert new['items'][0]['quantity'] == 3 and new['warehouse'] == ids['names'][0]
        assert len(new['movements']) == 1 and new['movements'][0]['warehouse_id'] == ids['a']
        delta = (3 if issuing else -3) if action == 'revert' else (-3 if issuing else 3)
        assert new['movements'][0]['quantity'] == delta
        assert new['movements'][0]['operator_id'] == ids['poster']
        assert wms.db.session.get(wms.Material, material_id).stock == (30 if action == 'revert' else 30 + delta)
        if not issuing:
            assert wms.db.session.get(wms.SubcontractOrder, parent_id).status == (
                'processing' if action == 'revert' else 'completed')
