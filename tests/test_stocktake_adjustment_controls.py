from collections import defaultdict
from datetime import datetime
from io import BytesIO
from types import SimpleNamespace

import re

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
    assert '确认调整库存' in client.get(f'/adjustment/{order.id}').get_data(as_text=True)
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


@pytest.mark.parametrize('batch', [False, True], ids=['single', 'batch'])
def test_delete_withdrawn_adjustment_preserves_ledger_and_allows_new_draft(scene, batch):
    client, _, wh, material = scene
    check = _count(client, wh, material, [{'actual_stock': 110}])
    assert _complete(client, check)['status'] == 'success'
    order = w.AdjustmentOrder.query.one()
    order_id, number = order.id, order.adjustment_no
    assert document_post(client, f'/adjustment/{order_id}/complete', json={}).json['status'] == 'success'
    assert document_post(client, f'/adjustment/{order_id}/delete', json={}).json['status'] == 'error'
    assert document_post(client, f'/adjustment/{order_id}/revert', json={}).json['status'] == 'success'
    assert document_post(client, f'/check/{check}/revert', json={}).json['status'] == 'success'
    assert order.status == 'cancelled'
    flow_query = w.StockTransaction.query.filter_by(reference_type='adjustment', reference_id=order_id)
    visible = client.get('/adjustment', query_string={'warehouse_id': wh.id}).get_data(as_text=True)
    checkbox = re.search(r'class="check-item" value="' + str(order_id) + r'" [^>]*?>', visible)
    assert checkbox is not None and 'disabled' not in checkbox[0]
    assert f'delBtn" data-id="{order_id}"' in visible
    assert 'data-wms-no-delete' not in client.get(f'/adjustment/{order_id}').get_data(as_text=True)
    old_flows = [(row.id, row.quantity, row.warehouse_id) for row in flow_query.order_by(w.StockTransaction.id)]
    assert sorted(qty for _, qty, _ in old_flows) == [-10, 10]

    url = '/adjustment/batch_delete' if batch else f'/adjustment/{order_id}/delete'
    payload = {'ids': [order_id, order_id]} if batch else {}
    result = document_post(client, url, json=payload).json
    assert result['status'] == 'success', result
    if batch:
        assert result['deleted'] == 1
    assert document_post(client, url, json=payload).json['status'] == 'error'
    assert w.db.session.get(w.AdjustmentOrder, order_id).status == 'deleted'
    assert material.stock == 100
    assert [(row.id, row.quantity, row.warehouse_id) for row in flow_query.order_by(w.StockTransaction.id)] == old_flows
    assert w.OperationAudit.query.filter_by(operation='delete_adjustment', target_name=number).count() == 1

    filters = {'warehouse_id': wh.id, 'search': number}
    html = client.get('/adjustment', query_string=filters).get_data(as_text=True)
    assert f'<tr data-id="{order_id}">' not in html and f'>{number}</a>' not in html
    for suffix in ('', '/print', '/print_excel', '/print_options', '/print_preview'):
        assert client.get(f'/adjustment/{order_id}{suffix}').status_code == 404
    nav = client.get('/api/document_navigation/adjustment', query_string={'q': number})
    assert number not in nav.get_data(as_text=True)
    from io import BytesIO
    from openpyxl import load_workbook

    exported = client.get('/adjustment/export', query_string=filters)
    assert exported.status_code == 200
    with BytesIO(exported.data) as stream:
        workbook = load_workbook(stream, read_only=True)
        try:
            assert not any(number in row for row in workbook.active.values)
        finally:
            workbook.close()
    assert number not in client.get(f'/check/{check}').get_data(as_text=True)
    with w.app.test_request_context():
        assert w._report_reference_info('adjustment', order_id) == (number, '')
    assert _complete(client, check, confirm=True)['status'] == 'success'
    new_order = w.AdjustmentOrder.query.filter_by(status='pending').one()
    assert new_order.id != order_id and new_order.adjustment_no != number


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
    ([{'actual_stock': 40}, {'area': 'Rack B', 'actual_stock': None}], 40, None),
])
def test_stocktake_report_totals(scene, rows, quantity, variance):
    client, _, wh, material = scene
    check = _count(client, wh, material, rows)
    report = w._sql_paged_check_report(defaultdict(str, warehouse=wh.name, warehouse_id=wh.id))
    assert [v for v in (row['system_stock'] for row in report[1]) if v is not None] == [100]
    assert sorted(row['actual_stock'] for row in report[1] if row['actual_stock'] is not None) == sorted(
        row['actual_stock'] for row in rows if row['actual_stock'] is not None)
    unit = material.unit.name if material.unit else '未设单位'
    if variance is None:
        assert report[2] == {'count': 2, 'quantity': quantity, 'amount': None, 'uncounted_groups': 1, 'quantity_text': f'{quantity} {unit}'}
        assert all(row['difference'] is None for row in report[1])
        assert '1 组物料尚未盘齐' in w._ai_stage4_stocktake_variance_report()
    else:
        assert report[2] == {'count': 2, 'quantity': quantity, 'amount': abs(variance),
                             'quantity_text': f'{quantity} {unit}', 'amount_text': f'{abs(variance)} {unit}'}
        assert [row['difference'] for row in report[1] if row['difference'] is not None] == [variance]
        assert f' | 100.0 | {float(quantity)} | {float(variance)} |' in w._ai_stage4_stocktake_variance_report()
    download = client.get(f'/check/{check}/export')
    cells = list(load_workbook(BytesIO(download.data), read_only=True).active.values)
    assert [row[cells[0].index('实际库存')] for row in cells[1:]] == [row['actual_stock'] for row in rows]
    if rows[-1]['actual_stock'] is None:
        assert _complete(client, check)['code'] == 'check_uncounted'
        assert w.AdjustmentOrder.query.count() == 0
        return
    assert _complete(client, check)['status'] == 'success'

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
