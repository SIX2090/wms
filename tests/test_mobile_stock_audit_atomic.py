"""Mobile stock actors and audit writes share the actual business transaction."""
import json
from contextlib import contextmanager
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import event

import app as w
from tests.test_document_create_number_conflicts import case, rows, snapshot


@pytest.fixture
def mobile_actors(case):
    clients, ids = case
    with w.app.app_context():
        actor = w.User(username='mobile-audit-actor', role='warehouse',
                       password_hash='synthetic', must_change_password=False)
        w.db.session.add(actor)
        w.db.session.flush()
        ids['mobile_actor'] = actor.id
        w.db.session.add(w.ApiToken(user_id=actor.id, token=w.hash_access_token('synthetic-stock-audit'),
                                   expires_at=datetime.now() + timedelta(days=7), last_used_at=datetime.now()))
        w.db.session.commit()
    return clients[0], w.app.test_client(), {'Authorization': 'Bearer synthetic-stock-audit'}, ids


@contextmanager
def reject_audit(operation):
    attempted = []

    def fail_on_insert(_mapper, _connection, row):
        if row.operation == operation:
            attempted.append(row.operation)
            raise RuntimeError('synthetic audit write failure')

    event.listen(w.OperationAudit, 'before_insert', fail_on_insert)
    try:
        yield attempted
    finally:
        event.remove(w.OperationAudit, 'before_insert', fail_on_insert)


@pytest.mark.parametrize('mode,delta', [('in', 3), ('out', -3)])
@pytest.mark.parametrize('confirm', [False, True])
def test_snapshot_audit_row(mobile_actors, mode, delta, confirm):
    web, mobile, headers, ids = mobile_actors
    model, kind = (w.InOrder, 'in_order') if mode == 'in' else (w.OutOrder, 'out_order')
    if confirm:
        created = web.post('/mobile/api/scan_batch_draft', json={
            'mode': mode, 'warehouse_id': ids['a'],
            'lines': [{'material_code': 'DC-M1', 'quantity': 3}],
        })
        assert created.status_code == 200, created.json
        oid = created.json['data']['order_id']
        path, body = f'/mobile/api/scan_draft_confirm/{oid}', {'order_type': mode}
        operation = 'h5_confirm_' + kind
        with w.app.app_context():
            # A previously completed then reverted draft already has movements.
            for qty in (2, -2):
                w.db.session.add(w.StockTransaction(material_id=ids['mats'][0], warehouse_id=ids['a'],
                    transaction_type='in', quantity=qty, reference_type=kind, reference_id=oid,
                    operator_id=ids['user']))
            w.db.session.commit()
    else:
        path = '/mobile/api/scan_submit'
        body = {'mode': mode, 'warehouse_id': ids['a'], 'code': 'DC-M1', 'quantity': 3}
        operation = 'h5_inbound' if mode == 'in' else 'h5_outbound'
    headers = {**headers, 'X-Idempotency-Key': 'h5-stock-audit'}
    with w.app.app_context():
        before = snapshot(model), rows(w.PrintJob), rows(w.MobileApiRequest)
    with reject_audit(operation) as attempted:
        failed = mobile.post(path, headers=headers, json=body)
    assert failed.status_code == 500, failed.json
    assert attempted == [operation]
    with w.app.app_context():
        assert (snapshot(model), rows(w.PrintJob), rows(w.MobileApiRequest)) == before
        assert w.OperationAudit.query.count() == 0
    response = mobile.post(path, headers=headers, json=body)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert mobile.post(path, headers=headers, json=body).json == response.json
    with w.app.app_context():
        order = model.query.one()
        assert order.operator_id == ids['user' if confirm else 'mobile_actor']
        audit = w.OperationAudit.query.filter_by(operation=operation, target_id=order.id).one()
        assert audit.user_id == ids['mobile_actor']
        assert audit.target_name == order.order_no
        if confirm:
            assert json.loads(audit.old_data) == {'status': 'pending'}
        saved = json.loads(audit.new_data)
        assert saved['status'] == 'completed' and saved['warehouse'] == ids['names'][0]
        assert len(saved['movements']) == 1
        movement = w.db.session.get(w.StockTransaction, saved['movements'][0]['id'])
        assert movement.operator_id == saved['movements'][0]['operator_id'] == ids['mobile_actor']
        assert movement.quantity == saved['movements'][0]['quantity'] == delta
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 30 + delta


def test_native_opening_audit_and_rollback(mobile_actors):
    _, mobile, headers, ids = mobile_actors
    data = {'warehouse_code': 'DC-A', 'date': date.today().isoformat(), 'lines': [
        {'material_code': 'DC-M1', 'quantity': 5, 'price': 2, 'remark': 'before'},
    ]}
    with reject_audit('native_opening_save') as attempted:
        failed = mobile.post('/api/opening_stock', headers=headers, json=data)
    assert failed.status_code == 500, failed.json
    assert attempted == ['native_opening_save']
    with w.app.app_context():
        assert w.OpeningStock.query.count() == w.OpeningStockDoc.query.count() == 0
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 30
    created = mobile.post('/api/opening_stock', headers=headers, json=data)
    assert created.status_code == 200, created.json
    listing = mobile.get('/api/opening_stock', headers=headers, query_string={'warehouse_id': ids['a']})
    item = listing.json['data']['items'][0]
    path = f"/api/opening_stock/{item['id']}"
    change = {'quantity': 7, 'price': 3, 'remark': 'after', 'revision': item['revision']}
    with reject_audit('native_opening_edit') as attempted:
        failed = mobile.post(path, headers=headers, json=change)
    assert failed.status_code == 500, failed.json
    assert attempted == ['native_opening_edit']
    with w.app.app_context():
        assert w.OpeningStock.query.one().quantity == 5
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 35
    saved = mobile.post(path, headers=headers, json=change)
    assert saved.status_code == 200, saved.json
    note_only = mobile.post(path, headers=headers, json={'remark': 'note only',
                               'revision': saved.json['data']['revision']})
    assert note_only.status_code == 200, note_only.json
    with w.app.app_context():
        line = w.OpeningStock.query.one()
        assert line.operator_id == ids['mobile_actor']
        audits = w.OperationAudit.query.filter_by(target_type='opening_stock', target_id=line.id).order_by(w.OperationAudit.id).all()
        assert [audit.operation for audit in audits] == ['native_opening_save', 'native_opening_edit', 'native_opening_edit']
        assert all(audit.user_id == ids['mobile_actor'] and audit.target_name == line.doc.doc_no for audit in audits)
        assert audits[0].old_data is None
        old, new = json.loads(audits[1].old_data), json.loads(audits[1].new_data)
        assert (old['quantity'], old['price'], old['remark']) == (5, 2, 'before')
        assert (new['quantity'], new['price'], new['remark'], new['stock_delta']) == (7, 3, 'after', 2)
        assert json.loads(audits[2].new_data)['stock_delta'] == 0
        movements = w.StockTransaction.query.filter_by(reference_type='opening_stock', reference_id=line.id).order_by(w.StockTransaction.id).all()
        assert [(row.quantity, row.operator_id) for row in movements] == [(5, ids['mobile_actor']), (2, ids['mobile_actor'])]


@pytest.mark.parametrize('native', [False, True])
def test_void_scan_audit_and_rollback(mobile_actors, native):
    web, mobile, headers, ids = mobile_actors
    with w.app.app_context():
        batch = w.InventoryCheck(check_no='AUDIT-CHECK', warehouse=ids['names'][0], status='pending')
        w.db.session.add(batch)
        w.db.session.flush()
        batch_id = batch.id
        w.db.session.add(w.InventoryCheckItem(inventory_check_id=batch_id, material_id=ids['mats'][0],
                                             system_stock=20, actual_stock=20, difference=0))
        w.db.session.commit()
    for code in ('DC-M1', 'DC-M2'):
        result = web.post('/mobile/api/scan_submit', json={
            'mode': 'check', 'code': code, 'warehouse_id': ids['a'], 'check_id': batch_id, 'actual_stock': 18,
        })
        assert result.status_code == 200, result.json
    with w.app.app_context():
        scans = [(scan.id, scan.check_no) for scan in w.InventoryCheckScan.query.order_by(w.InventoryCheckScan.id)]
        before = rows(w.InventoryCheckItem), rows(w.StockTransaction), rows(w.OperationLog)
    for scan_id, number in scans:
        path, data = ('/api/stocktake/void', {'check_no': number}) if native else (
            f'/mobile/api/check_scan/{scan_id}/void', {})
        if scan_id == scans[0][0]:
            with reject_audit('void_check_scan') as attempted:
                failed = mobile.post(path, json=data, headers=headers)
            assert failed.status_code == 500, failed.json
            assert attempted == ['void_check_scan']
            with w.app.app_context():
                assert (rows(w.InventoryCheckItem), rows(w.StockTransaction), rows(w.OperationLog)) == before
                assert w.db.session.get(w.InventoryCheckScan, scan_id).status == 'completed'
        result = mobile.post(path, json=data, headers=headers)
        assert result.status_code == 200, result.json
        with w.app.app_context():
            audit = w.OperationAudit.query.filter_by(operation='void_check_scan', target_id=scan_id).one()
            old, new = json.loads(audit.old_data), json.loads(audit.new_data)
            assert audit.user_id == ids['mobile_actor'] and audit.target_name == number
            assert old['status'] == 'completed' and new['status'] == 'void'
            assert old['batch_items'][0]['actual_stock'] == 18
            assert old['batch_items'][0]['counted_by'] == ids['user']
            if scan_id == scans[0][0]:
                assert new['batch_items'][0]['actual_stock'] == 20
                assert new['batch_items'][0]['counted_by'] is None
            else:
                assert new['batch_items'] == []
            assert w.db.session.get(w.InventoryCheckScan, scan_id).status == 'void'
            assert rows(w.StockTransaction) == before[1]
