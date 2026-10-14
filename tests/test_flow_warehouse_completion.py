"""Warehouse validity is rechecked at the final transaction boundary."""
from datetime import datetime
import pytest
import app as w
from tests.test_flow_source_limits import flow_case


@pytest.mark.parametrize('kind', ['requisition', 'adjustment', 'check'])
@pytest.mark.parametrize('mode', ['active', 'inactive', 'missing', 'code'])
def test_completion_rechecks_warehouse(flow_case, kind, mode):
    client, ids = flow_case
    warehouse = 'WA' if mode == 'code' else '不存在的仓库' if mode == 'missing' else '审计仓A'
    with w.app.app_context():
        if kind == 'requisition':
            doc = w.ProductionRequisition(req_no='DOC', warehouse=warehouse, status='pending')
        elif kind == 'adjustment':
            doc = w.AdjustmentOrder(adjustment_no='DOC', adjustment_type='profit', source_type='manual',
                                    warehouse=warehouse, status='pending')
        else:
            doc = w.InventoryCheck(check_no='DOC', warehouse=warehouse, status='pending', frozen_at=datetime.now())
        w.db.session.add(doc)
        w.db.session.flush()
        if kind == 'requisition':
            row = w.ProductionRequisitionItem(requisition_id=doc.id, material_id=ids['mat'], quantity=2, unit_id=ids['each'])
        elif kind == 'adjustment':
            row = w.AdjustmentOrderItem(adjustment_order_id=doc.id, material_id=ids['mat'], quantity=2, unit_id=ids['each'])
        else:
            row = w.InventoryCheckItem(inventory_check_id=doc.id, material_id=ids['mat'], system_stock=100,
                                       actual_stock=100, difference=0, counted_by=ids['user'], counted_at=datetime.now())
        w.db.session.add(row)
        w.db.session.commit()
        oid = doc.id
        if mode == 'inactive':
            w.db.session.get(w.Warehouse, ids['wh']).status = 'inactive'
            w.db.session.commit()
        before = w.StockTransaction.query.count()
    response = client.post(f'/{kind}/{oid}/complete', json={'force':True}).get_json()
    allowed = mode in ('active', 'code')
    assert (response['status'] == 'success') is allowed
    if not allowed:
        assert '仓库' in response['msg']
    with w.app.app_context():
        model = {'requisition':w.ProductionRequisition, 'adjustment':w.AdjustmentOrder, 'check':w.InventoryCheck}[kind]
        assert w.db.session.get(model, oid).status == ('completed' if allowed else 'pending')
        expected = 98 if allowed and kind == 'requisition' else 102 if allowed and kind == 'adjustment' else 100
        assert w.db.session.get(w.Material, ids['mat']).stock == expected
        assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, ids['other'])).get(ids['mat'], 0) == 0
        if not allowed:
            assert w.StockTransaction.query.count() == before
            assert w.AdjustmentOrder.query.filter_by(source_type='check').count() == 0
