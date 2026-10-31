"""Current stock follows the document warehouse; frozen counts stay unchanged."""
from datetime import datetime

from flask import template_rendered
import pytest

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene


@pytest.mark.parametrize('doc_type', ['check', 'adjustment'])
@pytest.mark.parametrize('warehouse_ref', ['name', 'code', 'invalid'])
@pytest.mark.parametrize('status', ['pending', 'completed'])
def test_detail_current_stock_is_local_and_never_global(scene, doc_type, warehouse_ref, status):
    client, source, other, material = scene
    material.stock = 102
    wms.db.session.add(wms.StockTransaction(material_id=material.id, transaction_type='in',
        quantity=2, warehouse_id=None, location=source.code))
    wh = source.name if warehouse_ref == 'name' else source.code if warehouse_ref == 'code' else 'missing-warehouse'
    if doc_type == 'check':
        doc = wms.InventoryCheck(check_no='CK-DISPLAY', warehouse=wh, status=status, frozen_at=datetime.now())
        wms.db.session.add(doc)
        wms.db.session.flush()
        wms.db.session.add(wms.InventoryCheckItem(inventory_check_id=doc.id, material_id=material.id,
            system_stock=7, actual_stock=6, difference=-1))
    else:
        doc = wms.AdjustmentOrder(adjustment_no='ADJ-DISPLAY', warehouse=wh, status=status, adjustment_type='loss')
        wms.db.session.add(doc)
        wms.db.session.flush()
        wms.db.session.add(wms.AdjustmentOrderItem(adjustment_order_id=doc.id, material_id=material.id, quantity=-1))
    wms.db.session.commit()
    contexts = []
    def capture(sender, template, context, **extra):
        contexts.append(context)
    template_rendered.connect(capture, wms.app)
    try:
        response = client.get(f'/{doc_type}/{doc.id}?embedded=1')
    finally:
        template_rendered.disconnect(capture, wms.app)
    assert response.status_code == 200
    context = contexts[-1]
    expected = 0 if warehouse_ref == 'invalid' else 2
    assert context['existing_items'][0]['stock'] == expected
    assert next(m for m in context['materials'] if m['id'] == material.id)['stock'] == expected
    if doc_type == 'check':
        row = context['existing_items'][0]
        assert (row['system_stock'], row['actual_stock'], row['difference']) == (7, 6, -1)
    assert material.stock == 102
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
