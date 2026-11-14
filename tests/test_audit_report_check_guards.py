"""Real synthetic HTTP checks for existing report/stocktake input guard omissions.

Execution requires the repository's verified isolated runtime before app import.
This module is prepared only; no result is implied by adding these tests.
"""
import io
import json
from datetime import datetime, timedelta

from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

import pytest
import app as w
from tests.document_revision_client import document_post
from tests.test_flow_source_limits import flow_case


@pytest.fixture
def guarded_case(flow_case, monkeypatch):
    client, ids = flow_case
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    response = client.post('/api/csrf_refresh')
    assert response.status_code == 200, response.get_data(as_text=True)
    token = response.get_json()['csrf_token']
    assert token
    yield client, ids, {'X-CSRFToken': token}


def _report_documents(ids):
    for suffix, warehouse, incoming, outgoing in (
            ('A', '审计仓A', 2, 1), ('B', '审计仓B', 9, 3)):
        inbound = w.InOrder(order_no='IN-AUDIT-' + suffix,
            business_type='其他入库', warehouse=warehouse, status='completed',
            total_amount=incoming * 5)
        outbound = w.OutOrder(order_no='OUT-AUDIT-' + suffix,
            business_type='领料单', warehouse=warehouse, status='completed',
            total_amount=outgoing * 5)
        w.db.session.add_all([inbound, outbound])
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=inbound.id,
            material_id=ids['mat'], quantity=incoming, price=5, amount=incoming * 5))
        w.db.session.add(w.OutOrderItem(out_order_id=outbound.id,
            material_id=ids['mat'], quantity=outgoing, price=5, amount=outgoing * 5))
    w.db.session.commit()


@pytest.mark.parametrize('path', [
    '/report/api/in_detail', '/report/api/out_detail',
    '/report/api/in_detail?export=excel', '/report/api/out_detail?export=excel',
    '/report/in_detail/print_excel', '/report/out_detail/print_excel',
])
def test_nonexistent_report_warehouse_is_rejected(guarded_case, path):
    client, ids, _ = guarded_case
    with w.app.app_context():
        _report_documents(ids)
        assert w.db.session.get(w.Warehouse, 987654321) is None
    separator = '&' if '?' in path else '?'
    response = client.get(path + separator + 'warehouse_id=987654321')
    assert response.status_code == 400, (path, response.status_code)
    body = response.get_json()
    assert body and body['status'] == 'error', (path, body)
    assert 'data' not in body


@pytest.mark.parametrize('kind,prefix', [('in_detail', 'IN'), ('out_detail', 'OUT')])
def test_valid_report_warehouse_still_isolates_rows_and_summary(guarded_case, kind, prefix):
    client, ids, _ = guarded_case
    with w.app.app_context():
        _report_documents(ids)
    quantities = (2, 9) if kind == 'in_detail' else (1, 3)
    for warehouse, suffix, quantity in zip((ids['wh'], ids['other']), ('A', 'B'), quantities):
        response = client.get(f'/report/api/{kind}?warehouse_id={warehouse}&page_size=1')
        assert response.status_code == 200, response.get_data(as_text=True)
        body = response.get_json()
        assert body['status'] == 'success' and body['total'] == 1
        rows = json.dumps(body['data'], ensure_ascii=False)
        assert f'{prefix}-AUDIT-{suffix}' in rows
        assert f'{prefix}-AUDIT-{"B" if suffix == "A" else "A"}' not in rows
        assert body['summary']['quantity'] == quantity


def test_existing_inactive_report_warehouse_remains_queryable(guarded_case):
    client, ids, _ = guarded_case
    with w.app.app_context():
        _report_documents(ids)
        w.db.session.get(w.Warehouse, ids['other']).status = 'inactive'
        w.db.session.commit()
    response = client.get(f'/report/api/in_detail?warehouse_id={ids["other"]}')
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()['total'] == 1


def test_report_default_and_missing_default_keep_existing_contract(guarded_case):
    client, ids, _ = guarded_case
    with w.app.app_context():
        _report_documents(ids)
    response = client.get('/report/api/in_detail')
    assert response.status_code == 200 and response.get_json()['total'] == 1
    with w.app.app_context():
        w.Warehouse.query.update({'is_default': False})
        w.db.session.commit()
    response = client.get('/report/api/in_detail')
    assert response.status_code == 400, response.get_data(as_text=True)


def test_report_preview_already_rejects_nonexistent_warehouse(guarded_case):
    client, _, _ = guarded_case
    response = client.get('/report/in_detail/print_preview?warehouse_id=987654321')
    assert response.status_code == 400, response.get_data(as_text=True)


def _check_document(ids):
    check = w.InventoryCheck(check_no='CHECK-AUDIT', warehouse='审计仓A',
        status='pending', frozen_at=datetime.now(), operator_id=ids['user'])
    w.db.session.add(check)
    w.db.session.flush()
    line = w.InventoryCheckItem(inventory_check_id=check.id,
        material_id=ids['mat'], system_stock=10, actual_stock=8,
        difference=-2, reason='original', area='')
    w.db.session.add(line)
    w.db.session.commit()
    return check.id, line.id


def _business_snapshot():
    models = (w.InventoryCheck, w.InventoryCheckItem, w.InventoryCheckScan,
        w.InventoryCheckScanItem, w.AdjustmentOrder, w.AdjustmentOrderItem,
        w.Material, w.StockTransaction, w.LocationInventory)
    return {model.__name__: [tuple(getattr(row, column.key)
        for column in model.__table__.columns)
        for row in model.query.order_by(model.id).all()] for model in models}


@pytest.mark.parametrize('invalid', ['Infinity', '-Infinity', 'NaN', '1e309', 'bad'])
def test_nonfinite_check_form_is_rejected_without_counting(guarded_case, invalid):
    client, ids, headers = guarded_case
    with w.app.app_context():
        check_id, line_id = _check_document(ids)
        before = _business_snapshot()
    response = document_post(client, f'/check/{check_id}/item/{line_id}',
        data={'actual_stock': invalid}, headers=headers)
    assert response.status_code == 400, response.get_data(as_text=True)
    body = response.get_json()
    assert body['status'] == 'error'
    assert ('数字' if invalid == 'bad' else '有限') in body['msg']
    with w.app.app_context():
        assert _business_snapshot() == before


@pytest.mark.parametrize('value', ['0', '6.25', '-2'])
def test_finite_check_form_preserves_existing_values(guarded_case, value):
    client, ids, headers = guarded_case
    with w.app.app_context():
        check_id, line_id = _check_document(ids)
        stock_before = w.db.session.get(w.Material, ids['mat']).stock
        flows_before = w.StockTransaction.query.count()
    response = document_post(client, f'/check/{check_id}/item/{line_id}',
        data={'actual_stock': value}, headers=headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()['status'] == 'success'
    with w.app.app_context():
        line = w.db.session.get(w.InventoryCheckItem, line_id)
        assert line.actual_stock == float(value)
        assert line.difference == float(value) - 10
        assert line.counted_by == ids['user'] and line.counted_at is not None
        assert w.db.session.get(w.Material, ids['mat']).stock == stock_before
        assert w.StockTransaction.query.count() == flows_before
        assert w.AdjustmentOrder.query.count() == 0


@pytest.mark.parametrize('channel', ['json', 'mobile', 'native'])
@pytest.mark.parametrize('invalid', ['Infinity', '-Infinity', 'NaN', '1e309'])
def test_nonfinite_stocktake_consumers_do_not_create_facts(guarded_case, channel, invalid):
    client, ids, headers = guarded_case
    with w.app.app_context():
        check_id, _ = _check_document(ids)
        if channel == 'native':
            token = 'synthetic-audit-stocktake-token'
            w.db.session.add(w.ApiToken(user_id=ids['user'],
                token=w.hash_access_token(token), expires_at=datetime.now() + timedelta(hours=1)))
            w.db.session.commit()
        before = _business_snapshot()
    if channel == 'json':
        response = document_post(client, '/check/save_table', headers=headers, json={
            'order_id': check_id, 'warehouse_id': ids['wh'],
            'items': [{'code': 'M1', 'actual_stock': invalid}]})
    elif channel == 'mobile':
        response = client.post('/mobile/api/scan_submit', headers=headers, json={
            'mode': 'check', 'code': 'M1', 'warehouse': '审计仓A',
            'check_id': check_id, 'actual_stock': invalid})
    else:
        response = w.app.test_client().post('/api/stocktake',
            headers={'Authorization': 'Bearer ' + token}, json={
                'warehouse': '审计仓A', 'check_id': check_id,
                'lines': [{'material_code': 'M1', 'actual_stock': invalid}]})
    assert response.status_code == 400, (channel, response.get_data(as_text=True))
    body = response.get_json()
    if channel == 'json':
        assert body['code'] == 'INVALID_DOCUMENT_INPUT'
    else:
        assert '有限' in body['msg']
    with w.app.app_context():
        assert _business_snapshot() == before


@pytest.mark.parametrize('channel', ['mobile', 'native'])
@pytest.mark.parametrize('value', ['0', '6.25', '-2', None, ''])
def test_stocktake_consumers_keep_finite_and_missing_value_contract(guarded_case, channel, value):
    client, ids, headers = guarded_case
    with w.app.app_context():
        check_id, line_id = _check_document(ids)
        stock_before = w.db.session.get(w.Material, ids['mat']).stock
        token = 'synthetic-audit-stocktake-token'
        if channel == 'native':
            w.db.session.add(w.ApiToken(user_id=ids['user'], token=w.hash_access_token(token),
                expires_at=datetime.now() + timedelta(hours=1)))
            w.db.session.commit()
    if channel == 'mobile':
        response = client.post('/mobile/api/scan_submit', headers=headers, json={
            'mode': 'check', 'code': 'M1', 'warehouse': '审计仓A',
            'check_id': check_id, 'actual_stock': value, 'quantity': '6.25'})
        expected = 6.25 if value in (None, '') else max(float(value), 0)
    else:
        response = w.app.test_client().post('/api/stocktake',
            headers={'Authorization': 'Bearer ' + token}, json={
                'warehouse': '审计仓A', 'check_id': check_id,
                'lines': [{'material_code': 'M1', 'actual_stock': value}]})
        expected = stock_before if value in (None, '') or float(value) < 0 else float(value)
    assert response.status_code == 200, (channel, response.get_data(as_text=True))
    body = response.get_json()
    assert body.get('status') == 'success' or body.get('success') is True, body
    with w.app.app_context():
        line = w.db.session.get(w.InventoryCheckItem, line_id)
        assert line.actual_stock == expected
        assert line.counted_by == ids['user'] and line.counted_at is not None
        assert w.db.session.get(w.Material, ids['mat']).stock == stock_before
        assert w.AdjustmentOrder.query.count() == 0


def test_check_form_omitted_value_keeps_old_value_and_empty_text_stays_invalid(guarded_case):
    client, ids, headers = guarded_case
    with w.app.app_context():
        check_id, line_id = _check_document(ids)
        before = _business_snapshot()
    path = f'/check/{check_id}/item/{line_id}'
    rejected = document_post(client, path, headers=headers, data={'actual_stock': ''})
    assert rejected.status_code == 400 and '数字' in rejected.get_json()['msg']
    with w.app.app_context():
        assert _business_snapshot() == before
    saved = document_post(client, path, headers=headers, data={})
    assert saved.status_code == 200 and saved.get_json()['status'] == 'success'
    with w.app.app_context():
        assert w.db.session.get(w.InventoryCheckItem, line_id).actual_stock == 8


@pytest.mark.parametrize('invalid', ['Infinity', '-Infinity'])
def test_legacy_nonfinite_actual_cannot_be_confirmed_into_adjustment_drafts(guarded_case, invalid):
    client, ids, headers = guarded_case
    with w.app.app_context():
        check_id, line_id = _check_document(ids)
        line = w.db.session.get(w.InventoryCheckItem, line_id)
        line.actual_stock = float(invalid)
        line.difference = float(invalid)
        line.counted_by = ids['user']
        line.counted_at = datetime.now()
        w.db.session.commit()
        before = _business_snapshot()
    response = document_post(client, f'/check/{check_id}/complete',
        headers=headers, json={'force': True})
    assert response.status_code == 400, response.get_json()
    assert '有限' in response.get_json()['msg']
    with w.app.app_context():
        assert _business_snapshot() == before


@pytest.mark.parametrize('invalid', ['Infinity', '-Infinity', 'NaN', '1e309'])
def test_nonfinite_excel_stocktake_row_is_skipped_before_creating_document(guarded_case, invalid):
    from openpyxl import Workbook
    client, _, headers = guarded_case
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['盘点单号', '物料编码', '仓库', '实际库存'])
    sheet.append(['CHECK-IMPORT-AUDIT', 'M1', '审计仓A', invalid])
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    with w.app.app_context():
        before = _business_snapshot()
    response = client.post('/check/import', headers=headers,
        data={'file': (stream, 'synthetic-stocktake.xlsx')})
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body['status'] == 'success'
    assert body['count'] == 0 and body['item_count'] == 0
    assert '有限' in body['warnings'] and '跳过 1 行' in body['msg']
    with w.app.app_context():
        assert _business_snapshot() == before


def test_excel_skips_invalid_unknown_material_and_keeps_valid_row(guarded_case):
    from openpyxl import Workbook
    client, ids, headers = guarded_case
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['盘点单号', '物料编码', '物料名称', '仓库', '实际库存'])
    sheet.append(['CHECK-INVALID', 'DO-NOT-CREATE', '禁止副作用', '审计仓A', 'Infinity'])
    sheet.append(['CHECK-VALID', 'M1', '审计物料', '审计仓A', '7'])
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    response = client.post('/check/import', headers=headers,
        data={'file': (stream, 'synthetic-mixed-stocktake.xlsx')})
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json()
    assert body['status'] == 'success' and body['count'] == 1 and body['item_count'] == 1
    assert '有限' in body['warnings'] and '跳过 1 行' in body['msg']
    with w.app.app_context():
        assert w.Material.query.filter_by(code='DO-NOT-CREATE').first() is None
        assert w.InventoryCheck.query.filter_by(check_no='CHECK-INVALID').first() is None
        check = w.InventoryCheck.query.filter_by(check_no='CHECK-VALID').one()
        assert check.items[0].actual_stock == 7
        assert w.db.session.get(w.Material, ids['mat']).stock == 100
