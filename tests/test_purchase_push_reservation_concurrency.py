"""两个独立 HTTP 会话竞争最后五件采购余量，使用专属临时 SQLite。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier, BrokenBarrierError

import pytest
import app as w
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


@pytest.fixture
def purchase_race(tmp_path, monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove()
        original = w.db.engines[None]
        engine = create_engine(URL.create('sqlite', database=str(tmp_path / 'purchase-race.db')),
                               connect_args={'timeout': 5})
        w.db.engines[None] = engine
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql('PRAGMA journal_mode=WAL')
            w.db.create_all()
            users = [w.User(username=name, role='warehouse', password_hash='synthetic',
                            must_change_password=False) for name in ('receiver-a', 'receiver-b')]
            wh = w.Warehouse(code='PUSH', name='采购并发仓', is_default=True, status='active')
            material = w.Material(code='PUR', name='合成收货物料', stock=0)
            w.db.session.add_all([*users, wh, material])
            w.db.session.flush()
            orders = [w.PurchaseOrder(order_no=name, date=date.today(), status='pending')
                      for name in ('PO-FIRST', 'PO-SECOND')]
            w.db.session.add_all(orders)
            w.db.session.flush()
            items = [w.PurchaseOrderItem(purchase_order_id=order.id, material_id=material.id,
                                         quantity=5, received_quantity=0, price=1) for order in orders]
            w.db.session.add_all(items)
            w.db.session.commit()
            ids = ([u.id for u in users], wh.id, orders[0].id, [i.id for i in items])
            w.db.session.remove()
            yield ids
        finally:
            w.db.session.remove()
            w.db.engines[None] = original
            engine.dispose()


@pytest.mark.parametrize('selection', [False, True])
@pytest.mark.parametrize('keys', ['no-key', 'different', 'same-intent'])
def test_purchase_push_last_five(purchase_race, monkeypatch, selection, keys):
    users, wh, order, items = purchase_race
    start = Barrier(2)
    checked = Barrier(2)
    validate = w.validate_purchase_receive_quantity
    def overlap_checks(*args, **kwargs):
        result = validate(*args, **kwargs)
        if result[0] and args[0].id == items[0]:
            try:
                checked.wait(timeout=0.75)
            except BrokenBarrierError:
                pass
        return result
    monkeypatch.setattr(w, 'validate_purchase_receive_quantity', overlap_checks)
    def push(worker, concurrent=True):
        client = w.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(users[0 if keys == 'same-intent' else worker])
            session['_fresh'] = True
        header = {} if keys == 'no-key' else {'X-Idempotency-Key': 'same' if keys == 'same-intent' else str(worker)}
        if selection:
            url = '/purchase_order/create_in_order_from_selection'
            lines = [{'purchase_order_item_id': item, 'quantity': 5} for item in items]
        else:
            url = f'/purchase_order/{order}/create_in_order'
            lines = [{'item_id': items[0], 'quantity': 5}]
        if concurrent:
            start.wait(timeout=10)
        response = client.post(url, json={'warehouse_id': wh, 'items': lines}, headers=header)
        return response.status_code, response.get_json()
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(push, [0, 1]))
    w.db.session.remove()
    docs = w.InOrder.query.all()
    assert len(docs) == 1, results
    assert all(status in (200, 400, 409, 503) for status, _ in results), results
    assert any(body and body['status'] == 'success' for _, body in results), results
    if keys == 'same-intent':
        status, replay = push(0, concurrent=False)
        assert status == 200 and replay['id'] == docs[0].id
        assert w.InOrder.query.count() == 1
    for item_id in (items if selection else items[:1]):
        qty = sum(row.quantity for row in docs[0].items if row.source_purchase_order_item_id == item_id)
        assert qty == w.db.session.get(w.PurchaseOrderItem, item_id).received_quantity == 5


def test_purchase_push_allows_two_distinct_partial_receipts(purchase_race):
    users, wh, order, items = purchase_race
    client = w.app.test_client()
    url = f'/purchase_order/{order}/create_in_order'
    for user, qty in zip(users, (2, 3)):
        with client.session_transaction() as session:
            session['_user_id'], session['_fresh'] = str(user), True
        result = client.post(url, json={'warehouse_id': wh, 'items': [{'item_id': items[0], 'quantity': qty}]})
        assert result.status_code == 200 and result.json['status'] == 'success', result.json
    w.db.session.remove()
    rows = w.InOrderItem.query.filter_by(source_purchase_order_item_id=items[0]).order_by(w.InOrderItem.id).all()
    assert [row.quantity for row in rows] == [2, 3]
    assert w.db.session.get(w.PurchaseOrderItem, items[0]).received_quantity == 5
