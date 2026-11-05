"""BUG-2026-11-01-029: stale sales previews fail clearly without changing old data."""
import copy
import json

import pytest
from sqlalchemy.exc import IntegrityError

import app as wms
from app import db
from tests.test_document_create_number_conflicts import case, rows  # noqa: F401


@pytest.fixture
def sales_case(case):
    clients, ids = case
    with wms.app.app_context():
        customer = wms.Customer(code='SC-C', name='同号测试客户')
        db.session.add(customer)
        db.session.commit()
        ids['customer'] = customer.id
    return clients, ids


def payload(ids, number=None, second=False):
    data = dict(customer_id=ids['customer'], warehouse_id=ids['a'],
                remark='second' if second else 'first',
                items=[dict(code='DC-M2' if second else 'DC-M1',
                            quantity=7 if second else 1, price=2)])
    if number is not None:
        data['order_no'] = number
    return data


def post(client, data, transport):
    if transport == 'json':
        return client.post('/sales/add', json=data)
    data = copy.deepcopy(data)
    data['items'] = json.dumps(data['items'])
    return client.post('/sales/add', data=data)


def snapshot():
    return {model.__tablename__: rows(model) for model in
            (wms.SalesOrder, wms.SalesOrderItem, wms.Material,
             wms.StockTransaction, wms.LocationInventory)}


@pytest.mark.parametrize('transport', ['json', 'form'])
@pytest.mark.parametrize('state', ['draft', 'confirmed'])
def test_duplicate_sales_number_is_conflict_preserves_original_and_allows_fresh_number(sales_case, transport, state):
    clients, ids = sales_case
    number = 'SO-CONFLICT-'+state
    first = post(clients[0], payload(ids, number), transport)
    assert first.status_code == 200, first.get_json()
    document_id = first.get_json()['id']
    with wms.app.app_context():
        db.session.get(wms.SalesOrder, document_id).status = state
        db.session.commit()
        before = snapshot()
    for _ in range(2):
        response = post(clients[1], payload(ids, number, second=True), transport)
        assert response.status_code == 409, response.get_json()
        assert response.get_json()['status'] == 'error'
        assert '销售订单号已存在' in response.get_json()['msg']
        assert '刷新' in response.get_json()['msg']
        with wms.app.app_context():
            assert snapshot() == before
    fresh = post(clients[1], payload(ids, number+'-NEW', second=True), transport)
    assert fresh.status_code == 200, fresh.get_json()
    assert fresh.get_json()['id'] != document_id
    with wms.app.app_context():
        original = db.session.get(wms.SalesOrder, document_id)
        assert original.remark == 'first'
        assert original.status == state
        assert [(i.material.code, i.quantity) for i in original.items] == [('DC-M1', 1)]
        assert rows(wms.Material) == before['material']
        assert rows(wms.StockTransaction) == before['stock_transaction']
        assert rows(wms.LocationInventory) == before['location_inventory']


@pytest.mark.parametrize('transport', ['json', 'form'])
def test_generated_sales_number_collision_uses_same_conflict_response(sales_case, monkeypatch, transport):
    clients, ids = sales_case
    assert post(clients[0], payload(ids, 'SO-GENERATED'), transport).status_code == 200
    monkeypatch.setattr(wms, 'generate_sales_order_no', lambda: 'SO-GENERATED')
    with wms.app.app_context():
        before = snapshot()
    response = post(clients[1], payload(ids, second=True), transport)
    assert response.status_code == 409, response.get_json()
    with wms.app.app_context():
        assert snapshot() == before


def test_unrelated_integrity_failure_is_not_misreported_as_number_conflict(sales_case, monkeypatch):
    clients, ids = sales_case
    with wms.app.app_context():
        before = snapshot()

    def fail_totals(order):
        raise IntegrityError('fixture unrelated constraint', {}, Exception('unrelated'))

    monkeypatch.setattr(wms, 'recalculate_sales_order', fail_totals)
    response = post(clients[0], payload(ids, 'SO-UNRELATED'), 'json')
    assert response.status_code == 500
    assert response.get_json() == {'status': 'error', 'msg': '保存失败，请稍后重试'}
    with wms.app.app_context():
        assert snapshot() == before


def test_explicit_id_edit_still_updates_only_its_own_sales_draft(sales_case):
    clients, ids = sales_case
    first = post(clients[0], payload(ids, 'SO-EDIT-ONE'), 'json')
    second = post(clients[1], payload(ids, 'SO-EDIT-TWO'), 'json')
    assert first.status_code == second.status_code == 200
    with wms.app.app_context():
        other = rows(wms.SalesOrderItem)[1]
        stocks = rows(wms.Material)
    response = clients[0].post('/sales/'+str(first.get_json()['id'])+'/edit',
                               json=payload(ids, second=True))
    assert response.status_code == 200, response.get_json()
    with wms.app.app_context():
        assert [row for row in rows(wms.SalesOrderItem)
                if row[1] == second.get_json()['id']] == [other]
        assert rows(wms.Material) == stocks
        assert wms.SalesOrder.query.count() == 2
