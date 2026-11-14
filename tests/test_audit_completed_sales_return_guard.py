"""BUG-2026-09-22-006: completed-edit and mobile-confirm consumer regressions.

Prepared only. Run through the repository's verified isolated test runtime;
this module never supplies an isolation bypass or selects a file database.
"""
import math
import re
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from threading import Barrier
from uuid import uuid4

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from flask import g  # noqa: E402
from flask_login import login_user  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.pool import QueuePool  # noqa: E402
import app as w  # noqa: E402


@pytest.fixture(params=[False, True], ids=['locations-off', 'locations-on'])
def return_case(monkeypatch, request):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        assert all(not row[2] for row in w.db.session.execute(text('PRAGMA database_list')))
        w.db.session.rollback()
        # A unique named *memory* database gives independent connections to the
        # real concurrent HTTP test. No production or temporary file is opened.
        engine = create_engine(
            f'sqlite:///file:synthetic-return-{uuid4().hex}?mode=memory&cache=shared&uri=true',
            connect_args={'check_same_thread': False, 'timeout': 1}, poolclass=QueuePool,
        )
        original = w.db.engines[None]
        w.db.engines[None] = engine
        try:
            with engine.connect() as connection:
                assert all(not row[2] for row in connection.execute(text('PRAGMA database_list')))
            w.db.create_all()
            def fresh_user():
                g.pop('_login_user', None)
                # The fixture keeps one app context across several real clients.
                # Flask-WTF normally gets fresh g caches with each request's app
                # context; do not reuse another client's signed CSRF token here.
                g.pop(w.app.config.get('WTF_CSRF_FIELD_NAME', 'csrf_token'), None)
                g.pop('csrf_valid', None)
            hooks = dict(w.app.before_request_funcs)
            hooks[None] = [fresh_user, *hooks.get(None, [])]
            monkeypatch.setattr(w.app, 'before_request_funcs', hooks)
            user = w.User(username='synthetic-return-warehouse', role='warehouse',
                          password_hash='synthetic-no-login', must_change_password=False)
            a = w.Warehouse(code='SYN-RA', name='合成退货甲仓', status='active', is_default=True)
            b = w.Warehouse(code='SYN-RB', name='合成退货乙仓', status='active')
            customer = w.Customer(code='SYN-RC', name='合成退货客户')
            material = w.Material(code='SYN-RM', name='合成退货料', stock=0, price=2)
            w.db.session.add_all([user, a, b, customer, material])
            w.db.session.flush()
            sale = w.SalesOrder(order_no='SYN-RETURN-SOURCE', customer_id=customer.id,
                                warehouse=a.name, warehouse_id=a.id, status='confirmed')
            w.db.session.add(sale)
            w.db.session.flush()
            source = w.SalesOrderItem(sales_order_id=sale.id, material_id=material.id,
                                      quantity=10, shipped_quantity=10, price=2, amount=20)
            w.db.session.add(source)
            w.set_system_setting('location_management_enabled', '1' if request.param else '0')
            w.set_system_setting('allow_negative_stock', '0')
            w.set_system_setting('allow_negative_location_stock', '0')
            w.db.session.commit()
            case = dict(user=user.id, a=a.id, b=b.id, customer=customer.id,
                        material=material.id, sale=sale.id, source=source.id,
                        location_on=request.param)
            # Stock is established through the same service as the product.
            from services.warehouse_stock_service import apply_stock_delta
            with w.app.test_request_context('/synthetic-return-seed'):
                login_user(user)
                for warehouse in (a, b):
                    ok, message = apply_stock_delta(material, 20, transaction_type='opening',
                        reference_type='material_initial', reference_id=material.id,
                        warehouse=warehouse.name, location='SAME')
                    assert ok, message
                w.db.session.commit()
            yield case
        finally:
            w.db.session.remove()
            w.db.engines[None] = original
            engine.dispose()


def _client(case):
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'], session['_fresh'] = str(case['user']), True
    return client


def _return(case, quantities=(1,), *, status='completed', linked=True):
    from services.warehouse_stock_service import apply_stock_delta
    with w.app.test_request_context('/synthetic-return-seed'):
        login_user(w.db.session.get(w.User, case['user']))
        warehouse = w.db.session.get(w.Warehouse, case['a'])
        order = w.InOrder(order_no='SYN-R-' + uuid4().hex, status=status,
                          business_type='销售退货入库', warehouse=warehouse.name, location='SAME',
                          customer_id=case['customer'], source_sales_order_id=case['sale'] if linked else None,
                          source_sales_order_no='SYN-RETURN-SOURCE' if linked else None,
                          total_amount=sum(quantities) * 2)
        w.db.session.add(order)
        w.db.session.flush()
        rows = []
        for quantity in quantities:
            row = w.InOrderItem(in_order_id=order.id, material_id=case['material'], quantity=quantity,
                price=2, amount=quantity * 2, source_sales_order_item_id=case['source'] if linked else None,
                contract_no='SYN-CONTRACT', remark='合成原备注')
            w.db.session.add(row)
            rows.append(row)
            if status == 'completed':
                ok, message = apply_stock_delta(w.db.session.get(w.Material, case['material']), quantity,
                    transaction_type='in', reference_type='in_order', reference_id=order.id,
                    warehouse=warehouse.name, location='SAME')
                assert ok, message
        w.db.session.commit()
        return order.id, [row.id for row in rows]


def _headers(client, oid):
    page = client.get(f'/in_order/{oid}')
    assert page.status_code == 200, page.get_data(as_text=True)[:300]
    html = page.get_data(as_text=True)
    values = {}
    for name in ('csrf-token', 'document-revision'):
        match = re.search(r'<meta name="' + name + r'" content="([^"]+)"', html)
        assert match, name
        values[name] = unescape(match.group(1))
    return {'X-CSRFToken': values['csrf-token'],
            'X-WMS-Document-Revision': values['document-revision']}


def _edit(client, oid, rows, *, headers=None, deleted=()):
    return client.post(f'/in_order/{oid}/update_completed', headers=headers or _headers(client, oid),
        json={'items': rows, 'deleted_items': list(deleted), 'reason': '合成退货上限验证'})


def _state():
    w.db.session.expire_all()
    result = []
    for model in (w.Material, w.LocationInventory, w.StockTransaction, w.InOrder, w.InOrderItem,
                  w.SalesOrder, w.SalesOrderItem, w.DocumentPushLine, w.OperationAudit,
                  w.OperationLog, w.MobileApiRequest):
        columns = list(inspect(model).columns)
        rows = model.query.order_by(*inspect(model).primary_key).all()
        result.append(tuple(tuple(getattr(row, column.key) for column in columns) for row in rows))
    return tuple(result)


def _assert_ledgers(case):
    w.db.session.expire_all()
    material = w.db.session.get(w.Material, case['material'])
    assert material.stock == pytest.approx(math.fsum(row.quantity for row in
        w.StockTransaction.query.filter_by(material_id=material.id)), abs=1e-10, rel=0)
    if case['location_on']:
        assert material.stock == pytest.approx(math.fsum(row.quantity for row in
            w.LocationInventory.query.filter_by(material_id=material.id)), abs=1e-10, rel=0)
    assert math.fsum(row.quantity for row in w.StockTransaction.query.filter_by(
        material_id=material.id, warehouse_id=case['b'])) == 20
    assert w.db.session.get(w.SalesOrderItem, case['source']).shipped_quantity == 10


def test_completed_sales_return_check(return_case):
    case = return_case
    oid, rows = _return(case)
    client = _client(case)
    headers = _headers(client, oid)
    before = _state()
    response = _edit(client, oid, [{'id': rows[0], 'quantity': 11, 'price': 7,
                                  'remark': '应整体回滚'}], headers=headers)
    assert response.status_code == 400, response.get_json()
    assert '退货' in response.get_json()['msg']
    assert _state() == before
    # An ordinary later commit must not resurrect a rejected request's changes.
    w.db.session.commit()
    assert _state() == before
    _assert_ledgers(case)


@pytest.mark.parametrize('target', [10, 0.5])
def test_completed_sales_return_counts_current_once_and_accepts_upper_bound_or_decrease(return_case, target):
    case = return_case
    oid, rows = _return(case)
    _return(case, (100,), status='pending')
    response = _edit(_client(case), oid, [{'id': rows[0], 'quantity': target, 'price': 2}])
    assert response.status_code == 200 and response.get_json()['status'] == 'success', response.get_json()
    assert w.db.session.get(w.InOrderItem, rows[0]).quantity == target
    assert w.db.session.get(w.InOrder, oid).total_amount == target * 2
    _assert_ledgers(case)


@pytest.mark.parametrize('target,allowed', [(6, True), (6.01, False)])
def test_completed_sales_return_sums_siblings_and_other_completed_orders(return_case, target, allowed):
    case = return_case
    oid, rows = _return(case, (1, 2))
    _return(case, (2,))
    _return(case, (100,), status='pending')
    client = _client(case)
    headers = _headers(client, oid)
    before = _state()
    response = _edit(client, oid, [{'id': rows[0], 'quantity': target, 'price': 2}], headers=headers)
    assert response.status_code == (200 if allowed else 400), response.get_json()
    if not allowed:
        assert _state() == before
    _assert_ledgers(case)


def test_completed_sales_return_uses_actual_post_delete_rows_and_rolls_back_mixed_batch(return_case):
    case = return_case
    oid, rows = _return(case, (1, 2))
    client = _client(case)
    response = _edit(client, oid, [{'id': rows[0], 'quantity': 10, 'price': 2}], deleted=[rows[1]])
    assert response.status_code == 200, response.get_json()
    assert w.db.session.get(w.InOrderItem, rows[1]) is None
    assert w.db.session.get(w.InOrder, oid).total_amount == 20
    # A no-source insertion followed by a sourced over-limit edit is one atomic request.
    headers = _headers(client, oid)
    before = _state()
    response = _edit(client, oid, [{'is_new': True, 'code': 'SYN-RM', 'quantity': 3, 'price': 8},
        {'id': rows[0], 'quantity': 11, 'price': 2}], headers=headers)
    assert response.status_code == 400, response.get_json()
    assert _state() == before
    _assert_ledgers(case)


def test_completed_sales_return_no_source_and_historical_precision_keep_existing_rules(return_case):
    case = return_case
    oid, rows = _return(case, linked=False)
    response = _edit(_client(case), oid, [{'id': rows[0], 'quantity': 11, 'price': 2}])
    assert response.status_code == 200, response.get_json()
    historical, history_rows = _return(case, (1.005,))
    client = _client(case)
    response = _edit(client, historical, [{'id': history_rows[0], 'quantity': 1.005,
                                         'price': 2, 'remark': '只改备注'}])
    assert response.status_code == 200, response.get_json()
    assert w.db.session.get(w.InOrderItem, history_rows[0]).quantity == 1.005
    headers = _headers(client, historical)
    before = _state()
    response = _edit(client, historical, [{'id': history_rows[0], 'quantity': 2, 'price': 2}], headers=headers)
    assert response.status_code == 400 and '历史' in response.get_json()['msg']
    assert _state() == before
    _assert_ledgers(case)


def test_completed_sales_return_retry_reuses_no_inventory_delta_and_stale_page_conflicts(return_case):
    case = return_case
    oid, rows = _return(case)
    client = _client(case)
    headers = _headers(client, oid)
    payload = [{'id': rows[0], 'quantity': 10, 'price': 2}]
    first = _edit(client, oid, payload, headers=headers)
    assert first.status_code == 200, first.get_json()
    before = _state()
    replay = _edit(client, oid, payload, headers=headers)
    assert replay.status_code == 409, replay.get_json()
    assert _state() == before
    repeat = _edit(client, oid, payload)
    assert repeat.status_code == 200, repeat.get_json()
    assert _state() == before
    _assert_ledgers(case)


@pytest.mark.parametrize('receipt', [False, True])
def test_mobile_confirmation_applies_existing_sales_return_gate(return_case, receipt):
    case = return_case
    oid, _ = _return(case, (11,), status='pending')
    client = _client(case)
    headers = _headers(client, oid)
    if receipt:
        headers['X-Idempotency-Key'] = 'synthetic-mobile-return-' + uuid4().hex
    before = _state()
    response = client.post(f'/mobile/api/scan_draft_confirm/{oid}', headers=headers,
                           json={'order_type': 'in'})
    assert response.status_code == 400, response.get_json()
    assert '退货' in response.get_json()['msg']
    assert _state() == before
    _assert_ledgers(case)


@pytest.mark.parametrize('linked,quantity', [(True, 9), (False, 11)])
def test_mobile_confirmation_legal_and_legacy_returns_preserve_atomic_replay(return_case, linked, quantity):
    case = return_case
    _return(case)
    oid, _ = _return(case, (quantity,), status='pending', linked=linked)
    client = _client(case)
    headers = _headers(client, oid)
    headers['X-Idempotency-Key'] = 'synthetic-mobile-legal-' + uuid4().hex
    path = f'/mobile/api/scan_draft_confirm/{oid}'
    response = client.post(path, headers=headers, json={'order_type': 'in'})
    assert response.status_code == 200 and response.get_json()['status'] == 'success', response.get_json()
    assert w.db.session.get(w.InOrder, oid).status == 'completed'
    before = _state()
    replay = client.post(path, headers=headers, json={'order_type': 'in'})
    assert replay.status_code == 200 and replay.get_json() == response.get_json()
    assert _state() == before
    _assert_ledgers(case)


def test_completed_sales_return_distinguishes_same_material_source_line_ids(return_case):
    case = return_case
    _return(case, (10,))
    oid, rows = _return(case)
    source = w.SalesOrderItem(sales_order_id=case['sale'], material_id=case['material'],
                              quantity=10, shipped_quantity=10, price=2, amount=20)
    w.db.session.add(source)
    w.db.session.flush()
    w.db.session.get(w.InOrderItem, rows[0]).source_sales_order_item_id = source.id
    w.db.session.commit()
    response = _edit(_client(case), oid, [{'id': rows[0], 'quantity': 10, 'price': 2}])
    assert response.status_code == 200 and response.get_json()['status'] == 'success', response.get_json()
    assert w.db.session.get(w.InOrderItem, rows[0]).quantity == 10
    _assert_ledgers(case)


def test_completed_sales_return_fixture_exercises_real_csrf_and_revision_guards(return_case):
    case = return_case
    oid, rows = _return(case)
    client = _client(case)
    headers = _headers(client, oid)
    before = _state()
    missing = _edit(client, oid, [{'id': rows[0], 'quantity': 2, 'price': 2}],
                    headers={'X-WMS-Document-Revision': headers['X-WMS-Document-Revision']})
    assert missing.status_code == 400
    assert _state() == before
    forged = _edit(client, oid, [{'id': rows[0], 'quantity': 2, 'price': 2}],
                   headers={'X-CSRFToken': headers['X-CSRFToken'],
                            'X-WMS-Document-Revision': 'synthetic-forgery'})
    assert forged.status_code == 409, forged.get_json()
    assert _state() == before


def test_completed_sales_return_different_orders_share_sqlite_write_fence(return_case):
    case = return_case
    first, a = _return(case)
    second, b = _return(case)
    # Release the main-thread read transaction before independent HTTP threads.
    w.db.session.remove()
    barrier = Barrier(2)
    def write(oid, row):
        client = _client(case)
        headers = _headers(client, oid)
        barrier.wait(timeout=10)
        response = _edit(client, oid, [{'id': row, 'quantity': 6, 'price': 2}], headers=headers)
        return response.status_code, response.get_json()
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(write, first, a[0]), workers.submit(write, second, b[0])]
        results = [future.result(timeout=20) for future in futures]
    assert sum(code == 200 and payload.get('status') == 'success' for code, payload in results) == 1, results
    assert all(code in (200, 400, 503) for code, _ in results), results
    w.db.session.remove()
    completed = w._sales_returned_quantity_by_source_item([case['source']])
    assert completed[case['source']] == 7
    # The losing document has a fresh page and must still be rejected on retry.
    loser, row = (first, a[0]) if w.db.session.get(w.InOrderItem, a[0]).quantity == 1 else (second, b[0])
    response = _edit(_client(case), loser, [{'id': row, 'quantity': 6, 'price': 2}])
    assert response.status_code == 400 and '退货' in response.get_json()['msg'], response.get_json()
    _assert_ledgers(case)
