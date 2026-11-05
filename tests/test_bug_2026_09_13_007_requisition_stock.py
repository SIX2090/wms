import pytest

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene, _stock


@pytest.mark.parametrize('entry', ['save', 'add', 'edit', 'batch'])
@pytest.mark.parametrize('available, legacy, negative', [
    (0, False, False), (10, False, False), (17, False, False),
    (17, True, False), (0, False, True),
])
def test_requisition_stock_entries(scene, entry, available, legacy, negative):
    client, source, other, material = scene
    _stock(material, source, available, legacy=legacy)
    wms.set_system_setting('allow_negative_stock', '1' if negative else '0')
    order = wms.ProductionRequisition(req_no='REQ-STOCK', status='pending',
                                      warehouse=source.code if legacy else source.name)
    wms.db.session.add(order)
    wms.db.session.flush()
    sibling = wms.ProductionRequisitionItem(requisition_id=order.id,
                                            material_id=material.id, quantity=7)
    wms.db.session.add(sibling)
    item = None
    if entry == 'edit':
        item = wms.ProductionRequisitionItem(requisition_id=order.id,
                                             material_id=material.id, quantity=1)
        wms.db.session.add(item)
    wms.db.session.commit()
    order_id = order.id
    transaction_count = wms.StockTransaction.query.count()
    if entry == 'save':
        response = client.post('/requisition/save_table', json={
            'order_id': order_id, 'order_no': order.req_no,
            'header': {'warehouse': order.warehouse},
            'items': [{'code': material.code, 'quantity': 7},
                      {'code': material.code, 'quantity': 10}],
        })
    elif entry == 'edit':
        response = client.post(f'/requisition/{order_id}/item/{item.id}/update',
                               data={'quantity': 10})
    elif entry == 'add':
        response = client.post(f'/requisition/{order_id}/item/add',
                               data={'material_code': material.code, 'quantity': 10})
    else:
        response = client.post(f'/requisition/{order_id}/batch_add_items',
                               json={'content': f'{material.code},10'})
    result = response.get_json()
    succeeds = available >= 17 or negative
    assert result['status'] == ('success' if succeeds else 'error'), result
    wms.db.session.expire_all()
    rows = wms.ProductionRequisitionItem.query.filter_by(requisition_id=order_id).all()
    original = 8 if entry == 'edit' else 7
    assert sum(row.quantity for row in rows) == (17 if succeeds else original)
    assert order.status == 'pending'
    assert wms.StockTransaction.query.count() == transaction_count
    assert wms.get_warehouse_stock_quantities(source).get(material.id, 0) == available
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == available + 100


def test_requisition_batch_counts_accepted_rows(scene):
    client, source, other, material = scene
    _stock(material, source, 10)
    order = wms.ProductionRequisition(req_no='REQ-BATCH', status='pending', warehouse=source.name)
    wms.db.session.add(order)
    wms.db.session.commit()
    result = client.post(f'/requisition/{order.id}/batch_add_items', json={
        'content': f'{material.code},7\n{material.code},7',
    }).get_json()
    assert result['status'] == 'success', result
    rows = wms.ProductionRequisitionItem.query.filter_by(requisition_id=order.id).all()
    assert len(rows) == 1
    assert rows[0].quantity == 7
