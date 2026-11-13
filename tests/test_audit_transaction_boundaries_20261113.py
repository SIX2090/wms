"""Real WMS app/model requests, only through the OS-isolated pytest launcher.

These cases supplement the source/model probes for BUG-2026-11-08-011/013/017.
They must never be run by importing the application on the Windows host. The
explicit guard also keeps --noconftest from turning this into an unsafe entry.
"""
from datetime import datetime, timedelta

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from flask import g  # noqa: E402
from sqlalchemy import event, text  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import app as w  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402


@pytest.fixture
def audit_scene(monkeypatch):
    """Assert an actual private memory engine before touching its synthetic rows."""
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url) in ('sqlite://', 'sqlite:///:memory:')
        assert all(not row[2] for row in w.db.session.execute(text('PRAGMA database_list')))
        w.db.session.rollback()
        w.db.drop_all()
        w.db.create_all()
        # A fixture-held context must not cache the previous request's user.
        def fresh_user():
            g.pop('_login_user', None)
        hooks = dict(w.app.before_request_funcs)
        hooks[None] = [fresh_user, *hooks.get(None, [])]
        monkeypatch.setattr(w.app, 'before_request_funcs', hooks)
        user = w.User(username='audit-synthetic', password_hash=generate_password_hash('synthetic-fixture-only'),
                      role='admin', must_change_password=False)
        a = w.Warehouse(code='SYN-A', name='合成甲仓', status='active', is_default=True)
        b = w.Warehouse(code='SYN-B', name='合成乙仓', status='active')
        material = w.Material(code='SYN-M', name='合成物料', stock=0)
        customer = w.Customer(code='SYN-C', name='合成客户')
        w.db.session.add_all([user, a, b, material, customer])
        w.db.session.commit()
        client = w.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'], session['_fresh'] = str(user.id), True
        yield dict(client=client, user=user, a=a, b=b, material=material, customer=customer)
        w.db.session.remove()


def _seed_inbound(scene):
    purchase = w.PurchaseOrder(order_no='SYN-P', status='completed')
    order = w.InOrder(order_no='SYN-I', warehouse=scene['a'].name, status='pending', total_amount=17)
    w.db.session.add_all([purchase, order])
    w.db.session.flush()
    source = w.PurchaseOrderItem(purchase_order_id=purchase.id, material_id=scene['material'].id,
        quantity=10, received_quantity=7.25, price=2, amount=20)
    w.db.session.add(source)
    w.db.session.flush()
    item = w.InOrderItem(in_order_id=order.id, material_id=scene['material'].id,
        source_purchase_order_item_id=source.id, quantity=3.2, price=3.75, amount=12)
    other = w.InOrderItem(in_order_id=order.id, material_id=scene['material'].id, quantity=1, price=5, amount=5)
    w.db.session.add_all([item, other])
    w.db.session.commit()
    return order.id, item.id, source.id


@pytest.mark.parametrize('alias', [False, True])
def test_inbound_commit_failure_keeps_detail_source_total_and_has_no_success_log(audit_scene, alias):
    order_id, item_id, source_id = _seed_inbound(audit_scene)
    path = (f'/in_order/{order_id}/item/{item_id}/delete' if alias
            else f'/in_order/{order_id}/delete_item/{item_id}')
    # Fetch the real page/revision before arming the business-commit fault.
    from tests.document_revision_client import document_post as real_post
    observed = []
    session = w.db.session()
    def fail_business(_session):
        if any(isinstance(row, w.InOrderItem) for row in session.deleted):
            observed.append('delete')
            raise RuntimeError('synthetic business commit failure')
        # recalculate_order_total flushes the deleted row before commit.
        if session.info.pop('audit_delete_flushed', False):
            observed.append('flushed-delete')
            raise RuntimeError('synthetic business commit failure')
    def note_flush(_session, _flush_context):
        if any(isinstance(row, w.InOrderItem) for row in session.deleted):
            session.info['audit_delete_flushed'] = True
    event.listen(session, 'before_commit', fail_business)
    event.listen(session, 'after_flush', note_flush)
    try:
        response = real_post(audit_scene['client'], path)
    finally:
        event.remove(session, 'before_commit', fail_business)
        event.remove(session, 'after_flush', note_flush)
        session.info.pop('audit_delete_flushed', None)
    assert observed, 'Failure injection must reach the actual delete business transaction'
    assert response.status_code == 500, response.get_json()
    assert w.db.session.get(w.InOrderItem, item_id) is not None
    assert w.db.session.get(w.PurchaseOrderItem, source_id).received_quantity == 7.25
    assert w.db.session.get(w.InOrder, order_id).total_amount == 17
    assert w.OperationLog.query.filter_by(target_type='in_order', target_id=order_id).count() == 0


@pytest.mark.parametrize('alias', [False, True])
def test_inbound_actual_log_insert_failure_preserves_successful_business(audit_scene, alias):
    order_id, item_id, source_id = _seed_inbound(audit_scene)
    path = (f'/in_order/{order_id}/item/{item_id}/delete' if alias
            else f'/in_order/{order_id}/delete_item/{item_id}')
    observed = []
    def fail_log(_mapper, _connection, target):
        if target.target_type == 'in_order' and target.target_id == order_id:
            observed.append(target.operation_content)
            raise RuntimeError('synthetic operation-log insert failure')
    event.listen(w.OperationLog, 'before_insert', fail_log)
    try:
        response = document_post(audit_scene['client'], path)
    finally:
        event.remove(w.OperationLog, 'before_insert', fail_log)
    assert observed and '删除入库单明细' in observed[-1]
    assert response.status_code == 200 and response.get_json()['status'] == 'success'
    assert w.db.session.get(w.InOrderItem, item_id) is None
    assert w.db.session.get(w.PurchaseOrderItem, source_id).received_quantity == 4.05
    assert w.db.session.get(w.InOrder, order_id).total_amount == 5
    assert w.OperationLog.query.filter_by(target_type='in_order', target_id=order_id).count() == 0


def _source(scene, kind, warehouse, suffix):
    getters = w._ledger_source_warehouse_getters()
    model = getters[kind][0]
    names = dict(in_order='order_no', out_order='order_no', after_sale_out_order='order_no',
        requisition='req_no', sales='order_no', adjustment='adjustment_no', check='check_no', subcontract='order_no')
    if kind == 'opening_stock':
        row = model(material_id=scene['material'].id, warehouse_id=warehouse.id, quantity=0)
    elif kind == 'transfer':
        row = model(transfer_no='SYN-T-' + suffix, from_warehouse=scene['a'].name,
                    to_warehouse=scene['b'].name, from_location=scene['a'].name,
                    to_location=scene['b'].name)
    else:
        row = model(**{names[kind]: 'SYN-' + kind + suffix, 'warehouse': warehouse.name})
        if kind == 'sales':
            row.customer_id = scene['customer'].id
        elif kind == 'adjustment':
            row.adjustment_type = 'loss'
    w.db.session.add(row)
    w.db.session.flush()
    return row


@pytest.mark.parametrize('kind', ['in_order', 'out_order', 'after_sale_out_order', 'requisition',
    'sales', 'adjustment', 'check', 'subcontract', 'opening_stock', 'transfer'])
def test_opening_hint_real_historical_sources_use_own_warehouse(audit_scene, kind):
    a, b, material = (audit_scene[key] for key in ('a', 'b', 'material'))
    src_a = _source(audit_scene, kind, a, 'A')
    src_b = src_a if kind == 'transfer' else _source(audit_scene, kind, b, 'B')
    w.db.session.add_all([
        w.StockTransaction(material_id=material.id, transaction_type='out', quantity=-3, location='',
                           reference_type=kind, reference_id=src_a.id),
        w.StockTransaction(material_id=material.id, transaction_type='in', quantity=7, location='',
                           reference_type=kind, reference_id=src_b.id),
    ])
    material.stock = 4
    line = w.OpeningStock(material_id=material.id, warehouse_id=a.id, quantity=0)
    w.db.session.add(line)
    w.db.session.commit()
    hints = w._opening_stock_negative_hint([line])
    assert len(hints) == 1 and '合成甲仓' in hints[0] and '-3' in hints[0], hints
    assert '合成乙仓' not in hints[0]
    assert w.get_warehouse_stock_quantities(a)[material.id] == -3
    assert w.get_warehouse_stock_quantities(b)[material.id] == 7


@pytest.mark.parametrize('mode', ['doc', 'lines', 'all'])
def test_opening_delete_query_driver_error_does_not_undo_valid_reversal(audit_scene, monkeypatch, mode):
    material, warehouse = audit_scene['material'], audit_scene['a']
    doc = w.OpeningStockDoc(doc_no='SYN-QS', warehouse_id=warehouse.id)
    w.db.session.add(doc)
    w.db.session.flush()
    line = w.OpeningStock(doc_id=doc.id, material_id=material.id, warehouse_id=warehouse.id, quantity=10)
    w.db.session.add(line)
    w.db.session.flush()
    w.db.session.add(w.StockTransaction(material_id=material.id, warehouse_id=warehouse.id,
        transaction_type='in', quantity=10, reference_type='opening_stock', reference_id=line.id))
    material.stock = 10
    w.db.session.commit()
    doc_id, material_id, line_id = doc.id, material.id, line.id
    # The real savepoint executes a real SQLite driver error after business DML.
    calls = []
    def broken_balance(_warehouse):
        calls.append(True)
        return w.db.session.execute(text('SELECT * FROM synthetic_missing_balance_table')).all()
    # Page/revision reads also use balance queries, so arm only at the hint helper.
    original_hint = w._opening_stock_negative_hint
    def failing_hint(lines):
        with monkeypatch.context() as scoped:
            scoped.setattr(w, 'get_warehouse_stock_quantities', broken_balance)
            return original_hint(lines)
    monkeypatch.setattr(w, '_opening_stock_negative_hint', failing_hint)
    if mode == 'doc':
        response = document_post(audit_scene['client'], f'/opening_stock/{doc_id}/delete')
    elif mode == 'lines':
        response = document_post(audit_scene['client'], f'/opening_stock/{doc_id}/lines/delete', json={'line_ids': [line_id]})
    else:
        from routes.opening_stock import OPENING_STOCK_PURGE_PHRASE
        response = document_post(audit_scene['client'], '/opening_stock/delete_all',
                                 json={'confirm': True, 'confirm_phrase': OPENING_STOCK_PURGE_PHRASE})
    assert calls, 'A real driver failure must run inside the post-reversal hint savepoint'
    assert response.status_code == 200 and response.get_json()['status'] == 'success', response.get_json()
    assert '暂时无法核验' in response.get_json()['msg']
    assert w.db.session.get(w.OpeningStock, line_id) is None
    assert w.db.session.get(w.Material, material_id).stock == 0
    assert w.StockTransaction.query.filter_by(reference_type='opening_stock', reference_id=line_id).count() == 0
    assert w.db.session.execute(text('SELECT 23')).scalar() == 23


def test_native_scan_after_review_requires_new_confirmation_and_only_creates_draft(audit_scene):
    scene = audit_scene
    a, material = scene['a'], scene['material']
    material.stock = 10
    check = w.InventoryCheck(check_no='SYN-CK', warehouse=a.name, status='pending',
                             frozen_at=datetime.now() - timedelta(minutes=1))
    w.db.session.add(check)
    w.db.session.flush()
    w.db.session.add(w.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
        system_stock=10, actual_stock=10, difference=0))
    w.db.session.add(w.StockTransaction(material_id=material.id, warehouse_id=a.id, quantity=10,
        transaction_type='in', created_at=datetime.now() - timedelta(hours=1)))
    w.db.session.commit()
    check_id, material_id = check.id, material.id
    path = f'/check/{check_id}/complete'
    reviewed = document_post(scene['client'], path, json={}).get_json()
    assert reviewed['status'] == 'confirm' and reviewed['risks']['uncounted'] == 1
    login = scene['client'].post('/api/login', json={
        'username': 'audit-synthetic', 'password': 'synthetic-fixture-only'})
    assert login.status_code == 200, login.get_json()
    native = scene['client'].post('/api/stocktake', json={
        'request_id': 'synthetic-audit-stocktake-1', 'warehouse': a.name, 'check_id': check_id,
        'lines': [{'material_code': material.code, 'actual_stock': 8}]},
        headers={'Authorization': 'Bearer ' + login.get_json()['data']['token']})
    assert native.status_code == 200 and native.get_json().get('success'), native.get_json()
    changed = document_post(scene['client'], path, json={
        'force': True, 'confirmation_token': reviewed['confirmation_token']}).get_json()
    assert changed['status'] == 'confirm' and changed['confirmation_token'] != reviewed['confirmation_token']
    assert changed['risks']['uncounted'] == 0
    assert w.db.session.get(w.InventoryCheck, check_id).status == 'pending'
    assert w.AdjustmentOrder.query.filter_by(source_type='check', source_id=check_id).count() == 0
    done = document_post(scene['client'], path, json={
        'force': True, 'confirmation_token': changed['confirmation_token']})
    assert done.status_code == 200 and done.get_json()['status'] == 'success', done.get_json()
    draft = w.AdjustmentOrder.query.filter_by(source_type='check', source_id=check_id).one()
    assert draft.status == 'pending' and draft.adjustment_type == 'loss'
    assert [(row.material_id, row.quantity) for row in draft.items] == [(material_id, -2)]
    assert w.db.session.get(w.Material, material_id).stock == 10
    assert w.StockTransaction.query.count() == 1
