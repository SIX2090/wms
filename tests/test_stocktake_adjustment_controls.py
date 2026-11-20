from collections import defaultdict
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

import app as w
from services.stocktake import grouped_stocktake_counts, stocktake_quantities
from tests.document_revision_client import document_post
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene
from tests.test_bug_2026_09_13_004_check_row_identity import _save


def _count(client, warehouse, material, rows):
    response = _save(client, warehouse, material, rows)
    assert response['status'] == 'success', response
    return response['id']


def _complete(client, check_id, confirm=False):
    url = f'/check/{check_id}/complete'
    response = document_post(client, url, json={}).json
    if confirm:
        assert response['status'] == 'confirm', response
        response = document_post(client, url, json={
            'force': True, 'confirmation_token': response['confirmation_token'],
        }).json
    return response


def test_adjustment_delete_error(scene):
    client, other, wh, material = scene
    check = _count(client, wh, material, [{'actual_stock': 110}])
    assert _complete(client, check)['status'] == 'success'
    order = w.AdjustmentOrder.query.one()
    response = document_post(client, '/adjustment/add', json={
        'order_id': order.id, 'adjustment_no': order.adjustment_no,
        'adjustment_type': 'surplus', 'warehouse': other.name,
        'items': [{'material_id': material.id, 'quantity': 15}],
    }).json
    assert response['status'] == 'error'
    assert '完成调整' in client.get(f'/adjustment/{order.id}').get_data(as_text=True)
    for path, data in [(f'/adjustment/{order.id}/delete', {}), ('/adjustment/batch_delete', {'ids': [order.id]})]:
        assert document_post(client, path, json=data).json['status'] == 'error'
    assert document_post(client, f'/check/{check}/revert', json={}).json['status'] == 'success'
    assert w.AdjustmentOrder.query.count() == 0


def test_validate_stocktake_adjustment(scene):
    client, _, wh, material = scene
    check = _count(client, wh, material, [{'actual_stock': 110}])
    assert _complete(client, check)['status'] == 'success'
    order = w.AdjustmentOrder.query.one()
    order.items[0].quantity = 15  # Simulate an edited draft saved by an older version.
    w.db.session.commit()
    path = f'/adjustment/{order.id}/complete'
    assert document_post(client, path, json={}).json['status'] == 'error'
    order.items[0].quantity = 10
    w.db.session.commit()
    assert document_post(client, path, json={}).json['status'] == 'success'
    assert material.stock == 110
    assert document_post(client, f'/adjustment/{order.id}/revert', json={}).json['status'] == 'success'
    assert material.stock == 100
    assert document_post(client, f'/check/{check}/revert', json={}).json['status'] == 'success'
    assert order.status == 'cancelled'
    flows = w.StockTransaction.query.filter_by(reference_type='adjustment', reference_id=order.id).all()
    assert sorted(flow.quantity for flow in flows) == [-10, 10]
    assert document_post(client, f'/check/{check}/delete', json={}).json['status'] == 'error'
    assert _complete(client, check, confirm=True)['status'] == 'success'
    assert w.AdjustmentOrder.query.filter_by(status='pending').count() == 1


def test_overlapping_stocktake_adjustment(scene):
    client, _, wh, material = scene
    first = _count(client, wh, material, [{'actual_stock': 110}])
    second = _count(client, wh, material, [{'actual_stock': 110}])
    assert _complete(client, first)['status'] == 'success'
    order = w.AdjustmentOrder.query.one()
    rejected = _complete(client, second)
    assert rejected['status'] == 'error' and order.adjustment_no in rejected['msg']
    assert document_post(client, f'/adjustment/{order.id}/complete', json={}).json['status'] == 'success'
    rejected = _complete(client, second, confirm=True)
    assert rejected['status'] == 'error' and order.adjustment_no in rejected['msg']
    assert w.AdjustmentOrder.query.count() == 1 and material.stock == 110


def test_legacy_duplicate_draft_is_rechecked_at_posting(scene, monkeypatch):
    from services import stocktake

    client, _, wh, material = scene
    first = _count(client, wh, material, [{'actual_stock': 110}])
    second = _count(client, wh, material, [{'actual_stock': 110}])
    with monkeypatch.context() as legacy:
        legacy.setattr(stocktake, 'overlapping_stocktake_adjustment', lambda *args, **kwargs: None)
        assert _complete(client, first)['status'] == 'success'
        assert _complete(client, second)['status'] == 'success'
    orders = w.AdjustmentOrder.query.order_by(w.AdjustmentOrder.id).all()
    assert document_post(client, f'/adjustment/{orders[0].id}/complete', json={}).json['status'] == 'success'
    assert document_post(client, f'/adjustment/{orders[1].id}/complete', json={}).json['status'] == 'error'
    assert material.stock == 110


def test_stocktake_adjustment_history(scene):
    client, _, wh, material = scene
    order = w.AdjustmentOrder(adjustment_no='ADJ-UNPOSTED', warehouse=wh.name,
                              adjustment_type='surplus', source_type='manual', status='pending')
    w.db.session.add(order)
    w.db.session.commit()
    deleted = document_post(client, f'/adjustment/{order.id}/delete', json={}).json
    assert deleted['status'] == 'success', deleted
    record = w.OperationAudit.query.filter_by(operation='delete_adjustment', target_name='ADJ-UNPOSTED').one()
    assert record.target_type == 'adjustment'


@pytest.mark.parametrize('rows, quantity, variance', [
    ([{'actual_stock': 40}, {'actual_stock': 70}], 110, 10),
    ([{'actual_stock': 40}, {'area': 'Rack B', 'actual_stock': None}], 40, -60),
])
def test_stocktake_report_totals(scene, rows, quantity, variance):
    client, _, wh, material = scene
    check = _count(client, wh, material, rows)
    report = w._sql_paged_check_report(defaultdict(str, warehouse=wh.name, warehouse_id=wh.id))
    assert report[2] == {'count': 2, 'quantity': quantity, 'amount': abs(variance)}
    assert f' | 100.0 | {float(quantity)} | {float(variance)} |' in w._ai_stage4_stocktake_variance_report()
    download = client.get(f'/check/{check}/export')
    cells = list(load_workbook(BytesIO(download.data), read_only=True).active.values)
    assert [row[cells[0].index('实际库存')] for row in cells[1:]] == [row['actual_stock'] for row in rows]
    assert _complete(client, check, confirm=rows[-1]['actual_stock'] is None)['status'] == 'success'
    assert w.AdjustmentOrder.query.one().items[0].quantity == variance


def test_has_actual_count():
    blank = w.InventoryCheckItem(system_stock=100, actual_stock=100, area='Rack')
    zero = w.InventoryCheckItem(system_stock=0, actual_stock=0, counted_at=datetime.now())
    assert not blank.has_actual_count and zero.has_actual_count


def test_grouped_stocktake_counts():
    blank = w.InventoryCheckItem(id=10, material_id=1, system_stock=100, actual_stock=100, area='Rack')
    count = w.InventoryCheckItem(id=12, material_id=1, system_stock=90, actual_stock=40)
    assert grouped_stocktake_counts(SimpleNamespace(items=[count, blank])) == {1: (blank, [count])}


def test_stocktake_quantities():
    first = SimpleNamespace(system_stock=100)
    counted = [SimpleNamespace(actual_stock=40.125), SimpleNamespace(actual_stock=70.125)]
    assert stocktake_quantities(first, counted) == (100, 110.26, 10.26)
