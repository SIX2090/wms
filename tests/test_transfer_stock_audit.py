import json

import pytest

import app as wms
from tests.test_document_create_number_conflicts import case, rows, snapshot
from tests.test_web_stock_posting_audit import fail_audit, posting_actors


@pytest.mark.parametrize('action', ['complete', 'revert'])
@pytest.mark.parametrize('locations', [False, True])
def test_transfer_audit_and_both_warehouse_movements_commit_together(posting_actors, action, locations):
    creator, poster, ids = posting_actors
    material_id = ids['mats'][0]
    with wms.app.app_context():
        order = wms.TransferOrder(
            transfer_no='TRANSFER-AUDIT', status='pending', operator_id=ids['user'],
            from_warehouse=ids['names'][0], to_warehouse=ids['names'][1],
            from_location='A-BIN', to_location='B-BIN',
        )
        wms.db.session.add(order)
        wms.db.session.flush()
        order_id = order.id
        wms.db.session.add(wms.TransferOrderItem(
            transfer_order_id=order_id, material_id=material_id, quantity=3, price=1, amount=3,
        ))
        if locations:
            wms.set_system_setting('location_management_enabled', '1')
            wms.db.session.add_all([
                wms.LocationInventory(material_id=material_id, warehouse_id=ids['a'], location='A-BIN', quantity=20),
                wms.LocationInventory(material_id=material_id, warehouse_id=ids['b'], location='B-BIN', quantity=10),
            ])
        wms.db.session.commit()

    if action == 'revert':
        prepared = creator.post(f'/transfer/{order_id}/complete')
        assert prepared.json['status'] == 'success', prepared.json
    with wms.app.app_context():
        before = snapshot(wms.TransferOrder), rows(wms.OperationAudit), rows(wms.OperationLog)

    operation = f'{action}_transfer'
    url = f'/transfer/{order_id}/{action}'
    with fail_audit(operation, order_id) as attempted:
        failed = poster.post(url)
    assert failed.json['status'] == 'error', failed.json
    assert attempted == [order_id]
    with wms.app.app_context():
        assert (snapshot(wms.TransferOrder), rows(wms.OperationAudit), rows(wms.OperationLog)) == before

    saved = poster.post(url)
    assert saved.json['status'] == 'success', saved.json
    with wms.app.app_context():
        order = wms.db.session.get(wms.TransferOrder, order_id)
        assert order.operator_id == ids['user']
        audit = wms.OperationAudit.query.filter_by(
            operation=operation, target_type='transfer', target_id=order_id,
        ).one()
        audit_id = audit.id
        assert audit.target_name == 'TRANSFER-AUDIT'
        assert audit.username == 'web-stock-poster' and audit.user_id == ids['poster']
        old, new = json.loads(audit.old_data), json.loads(audit.new_data)
        completing = action == 'complete'
        assert old['status'] == ('pending' if completing else 'completed')
        assert new['status'] == order.status == ('completed' if completing else 'pending')
        assert new['warehouse'] == ' → '.join(ids['names'])
        assert new['items'][0]['material_id'] == material_id and new['items'][0]['quantity'] == 3
        expected = {ids['a']: -3 if completing else 3, ids['b']: 3 if completing else -3}
        assert len(new['movements']) == 2
        assert {movement['warehouse_id']: movement['quantity'] for movement in new['movements']} == expected
        for movement in new['movements']:
            txn = wms.db.session.get(wms.StockTransaction, movement['id'])
            assert txn.operator_id == movement['operator_id'] == ids['poster']
            assert txn.quantity == movement['quantity']
        assert wms.db.session.get(wms.Material, material_id).stock == 30
        if locations:
            bins = wms.LocationInventory.query.filter_by(material_id=material_id).all()
            assert {row.warehouse_id: row.quantity for row in bins} == {
                ids['a']: 17 if completing else 20, ids['b']: 13 if completing else 10,
            }

    detail = creator.get('/operation_audit', query_string={'search': 'TRANSFER-AUDIT', 'audit_detail': audit_id})
    assert detail.status_code == 200
    page = detail.get_data(as_text=True)
    assert '本次库存流水' in page and 'web-stock-poster' in page
    assert f'{ids["names"][0]} #{ids["a"]}' in page and f'{ids["names"][1]} #{ids["b"]}' in page
    assert '>-3</td>' in page and '>+3</td>' in page
