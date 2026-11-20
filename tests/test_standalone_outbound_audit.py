import json

import pytest

import app as wms
from tests.test_document_create_number_conflicts import case, rows, snapshot
from tests.test_web_stock_posting_audit import fail_audit, posting_actors


@pytest.mark.parametrize('action', ['complete', 'revert'])
@pytest.mark.parametrize('kind, role, model, line_model, number_key, parent_key', [
    ('requisition', 'production', wms.ProductionRequisition, wms.ProductionRequisitionItem,
     'req_no', 'requisition_id'),
])
def test_standalone_outbound_audit_commits_with_inventory(posting_actors, action, kind, role, model,
                                                         line_model, number_key, parent_key):
    creator, poster, ids = posting_actors
    number = 'STANDALONE-OUT-AUDIT'
    with wms.app.app_context():
        wms.db.session.get(wms.User, ids['poster']).role = role
        order = model(**{number_key: number}, status='pending', operator_id=ids['user'],
                      warehouse=ids['names'][0])
        wms.db.session.add(order)
        wms.db.session.flush()
        order_id = order.id
        material = wms.db.session.get(wms.Material, ids['mats'][0])
        wms.db.session.add(line_model(**{parent_key: order_id}, material_id=material.id,
                                      quantity=3, unit_id=material.unit_id))
        wms.db.session.commit()
    if action == 'revert':
        prepared = creator.post(f'/{kind}/{order_id}/complete')
        assert prepared.json['status'] == 'success', prepared.json
    with wms.app.app_context():
        before = snapshot(model), rows(wms.OperationAudit), rows(wms.OperationLog)

    operation = f'{action}_{kind}'
    url = f'/{kind}/{order_id}/{action}'
    with fail_audit(operation, order_id) as attempted:
        failed = poster.post(url)
    assert failed.json['status'] == 'error', failed.json
    assert attempted == [order_id]
    with wms.app.app_context():
        assert (snapshot(model), rows(wms.OperationAudit), rows(wms.OperationLog)) == before

    response = poster.post(url)
    assert response.json['status'] == 'success', response.json
    completing = action == 'complete'
    with wms.app.app_context():
        saved = wms.db.session.get(model, order_id)
        assert saved.operator_id == ids['user']
        audit = wms.OperationAudit.query.filter_by(operation=operation, target_type=kind, target_id=order_id).one()
        audit_id = audit.id
        assert audit.user_id == ids['poster'] and audit.username == 'web-stock-poster'
        assert audit.target_name == number
        old, new = json.loads(audit.old_data), json.loads(audit.new_data)
        assert old['status'] == ('pending' if completing else 'completed')
        assert new['status'] == saved.status == ('completed' if completing else 'pending')
        assert new['warehouse'] == ids['names'][0] and new['items'][0]['quantity'] == 3
        assert len(new['movements']) == 1
        movement = new['movements'][0]
        assert movement['warehouse_id'] == ids['a'] and movement['operator_id'] == ids['poster']
        assert movement['quantity'] == (-3 if completing else 3)
        assert wms.db.session.get(wms.Material, ids['mats'][0]).stock == (27 if completing else 30)

    detail = creator.get('/operation_audit', query_string={'search': number, 'audit_detail': audit_id})
    assert detail.status_code == 200
    page = detail.get_data(as_text=True)
    assert '本次库存流水' in page and ids['names'][0] in page and 'web-stock-poster' in page
    assert ('>-3</td>' if completing else '>+3</td>') in page
