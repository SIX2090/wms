"""Computer stock transitions share their transaction with the audit record."""
import json
from contextlib import contextmanager

import pytest
from sqlalchemy import event

import app as w
from tests.test_document_create_number_conflicts import case, rows, snapshot


@pytest.fixture
def posting_actors(case):
    clients, ids = case
    with w.app.app_context():
        operator = w.User(username='web-stock-poster', role='warehouse',
                          password_hash='synthetic-unused', must_change_password=False)
        w.db.session.add(operator)
        w.db.session.flush()
        ids['poster'] = operator.id
        w.db.session.commit()
    second = w.app.test_client()
    with second.session_transaction() as session:
        session['_user_id'] = str(ids['poster'])
        session['_fresh'] = True
    return clients[0], second, ids


MODELS = {
    'in_order': (w.InOrder, w.InOrderItem, 'order_no', 'in_order_id', {'business_type': '采购入库'}),
    'out_order': (w.OutOrder, w.OutOrderItem, 'order_no', 'out_order_id', {'business_type': '领料单'}),
    'adjustment': (w.AdjustmentOrder, w.AdjustmentOrderItem, 'adjustment_no', 'adjustment_order_id',
                   {'adjustment_type': 'surplus', 'source_type': 'manual'}),
}


def draft(kind, ids, number, row=0, **options):
    model, item_model, number_key, foreign_key, fields = MODELS[kind]
    with w.app.app_context():
        order = model(**{number_key: number}, warehouse=ids['names'][0], status='pending',
                      operator_id=ids['user'], **fields, **options)
        w.db.session.add(order)
        w.db.session.flush()
        pricing = {} if kind == 'adjustment' else {'price': 1, 'amount': 3}
        w.db.session.add(item_model(**{foreign_key: order.id}, material_id=ids['mats'][row], quantity=3, **pricing))
        w.db.session.commit()
        return order.id


@contextmanager
def fail_audit(operation, ident=None):
    attempted = []

    def reject(_mapper, _connection, audit):
        if audit.operation == operation and (ident is None or audit.target_id == ident):
            attempted.append(audit.target_id)
            raise RuntimeError('synthetic audit write failure')

    event.listen(w.OperationAudit, 'before_insert', reject)
    try:
        yield attempted
    finally:
        event.remove(w.OperationAudit, 'before_insert', reject)


def request_transition(client, kind, action, order_id, batch):
    if batch:
        return client.post(f'/{kind}/batch_{action}', json={'ids': [order_id]})
    return client.post(f'/{kind}/{order_id}/{action}?force=1')


@pytest.mark.parametrize('kind, action, batch', [
    ('in_order', 'complete', False), ('in_order', 'complete', True),
    ('in_order', 'revert', False), ('in_order', 'revert', True),
    ('out_order', 'complete', False), ('out_order', 'complete', True),
    ('out_order', 'revert', False),
    ('adjustment', 'complete', False), ('adjustment', 'revert', False),
])
def test_stock_document_audit_checkpoint(posting_actors, kind, action, batch):
    creator, poster, ids = posting_actors
    number = 'AUDIT-POST-DRAFT'
    order_id = draft(kind, ids, number)
    if action == 'revert':
        prepared = request_transition(creator, kind, 'complete', order_id, False)
        assert prepared.json['status'] == 'success', prepared.json

    model = MODELS[kind][0]
    operation = f'{action}_{kind}'
    with w.app.app_context():
        before = snapshot(model), rows(w.OperationAudit), rows(w.OperationLog)
    with fail_audit(operation, order_id) as attempted:
        failed = request_transition(poster, kind, action, order_id, batch)
    if batch and action == 'revert':
        assert failed.json['reverted'] == 0, failed.json
    else:
        assert failed.json['status'] == 'error', failed.json
    assert attempted == [order_id]
    with w.app.app_context():
        assert (snapshot(model), rows(w.OperationAudit), rows(w.OperationLog)) == before

    saved = request_transition(poster, kind, action, order_id, batch)
    assert saved.json['status'] == 'success', saved.json
    if batch:
        count_key = 'reverted' if action == 'revert' else 'completed'
        assert saved.json[count_key] == 1, saved.json
    with w.app.app_context():
        order = w.db.session.get(model, order_id)
        assert order.operator_id == ids['user']
        audit = w.OperationAudit.query.filter_by(operation=operation, target_type=kind, target_id=order_id).one()
        assert audit.user_id == ids['poster'] and audit.username == 'web-stock-poster'
        assert audit.target_name == number
        old, new = json.loads(audit.old_data), json.loads(audit.new_data)
        assert old['status'] == ('completed' if action == 'revert' else 'pending')
        assert new['status'] == order.status == ('pending' if action == 'revert' else 'completed')
        assert new['items'][0]['quantity'] == 3
        assert new['warehouse'] == ids['names'][0]
        assert len(new['movements']) == 1
        movement = new['movements'][0]
        delta = -3 if kind == 'out_order' else 3
        assert movement['quantity'] == (-delta if action == 'revert' else delta)
        assert movement['warehouse_id'] == ids['a'] and movement['operator_id'] == ids['poster']
        assert w.db.session.get(w.StockTransaction, movement['id']).quantity == movement['quantity']
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == (30 if action == 'revert' else 30 + delta)


def test_batch_write_failure_isolated_to_its_document(posting_actors):
    _, poster, ids = posting_actors
    refused = draft('in_order', ids, 'AUDIT-FAIL-FIRST')
    accepted = draft('in_order', ids, 'AUDIT-SAVE-SECOND', row=1)

    with fail_audit('complete_in_order', refused) as attempted:
        response = poster.post('/in_order/batch_complete', json={'ids': [refused, accepted]})
    assert attempted == [refused]
    assert response.json['status'] == 'success' and response.json['completed'] == 1, response.json
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, refused).status == 'pending'
        assert w.db.session.get(w.InOrder, accepted).status == 'completed'
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 30
        assert w.db.session.get(w.Material, ids['mats'][1]).stock == 33
        assert w.OperationAudit.query.filter_by(operation='complete_in_order').one().target_id == accepted


def test_linked_stock_posting_rolls_back_both_documents(posting_actors):
    _, poster, ids = posting_actors
    order_id = draft('in_order', ids, 'AUDIT-AUTO-OUT', auto_push_requisition=True)
    with w.app.app_context():
        before = snapshot(w.InOrder), rows(w.DocumentPushLine)
    with fail_audit('complete_out_order') as attempted:
        failed = request_transition(poster, 'in_order', 'complete', order_id, False)
    assert failed.json['status'] == 'error', failed.json
    assert len(attempted) == 1
    with w.app.app_context():
        assert (snapshot(w.InOrder), rows(w.DocumentPushLine)) == before
        assert w.OutOrder.query.count() == w.OperationAudit.query.count() == 0

    success = request_transition(poster, 'in_order', 'complete', order_id, False)
    assert success.json['status'] == 'success', success.json
    with w.app.app_context():
        linked = w.OutOrder.query.one()
        assert linked.id == success.json['auto_requisition_id']
        audit = w.OperationAudit.query.filter_by(operation='complete_out_order', target_id=linked.id).one()
        assert audit.user_id == ids['poster'] and audit.old_data is None
        assert [row['quantity'] for row in json.loads(audit.new_data)['movements']] == [-3]
        assert w.OperationAudit.query.filter_by(operation='complete_in_order', target_id=order_id).count() == 1
        assert w.db.session.get(w.Material, ids['mats'][0]).stock == 30
