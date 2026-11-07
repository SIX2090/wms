"""Sales selectors and writes share the existing active-material policy."""
from io import BytesIO

from flask import template_rendered
from openpyxl import Workbook
import pytest

import app as w
from tests.document_revision_client import document_post
from tests.test_sales_collection_boundary_runtime import sales_case  # noqa: F401


@pytest.fixture
def policy_case(sales_case):
    client, ids, _ = sales_case
    original = w.db.session.get(w.Material, ids['material'])
    inactive = w.Material(code='OFF', name='停用料', spec='历史规格', status='inactive',
                          stock=7, unit_id=original.unit_id, price=3)
    w.db.session.add(inactive)
    w.db.session.commit()
    ids['inactive'] = inactive.id
    return client, ids


def snapshot():
    return {
        'orders': [(x.id, x.order_no, x.remark, x.total_amount) for x in w.SalesOrder.query.order_by(w.SalesOrder.id)],
        'items': [(x.id, x.sales_order_id, x.material_id, x.quantity, x.price)
                  for x in w.SalesOrderItem.query.order_by(w.SalesOrderItem.id)],
        'stock': [(x.id, x.stock) for x in w.Material.query.order_by(w.Material.id)],
        'ledger': w.StockTransaction.query.count(),
        'locations': w.LocationInventory.query.count(),
        'customers': w.Customer.query.count(),
    }


def payload(ids, codes):
    return dict(customer_id=ids['customer'], warehouse_id=ids['warehouse'],
                date='2026-11-08', remark='candidate edit',
                items=[dict(code=code, quantity=2, price=0, tax_rate=0) for code in codes])


@pytest.mark.parametrize('page', ['add', 'edit'])
def test_sales_initial_candidates_exclude_inactive(page, policy_case):
    client, ids = policy_case
    contexts = []
    def capture(sender, template, context, **unused):
        contexts.append(context)
    with template_rendered.connected_to(capture, w.app):
        response = client.get('/sales/add' if page == 'add' else f"/sales/{ids['order']}/edit")
    assert response.status_code == 200
    candidates = contexts[-1]['materials'] if page == 'add' else contexts[-1]['material_list']
    assert any(x['code'] == 'FREE' for x in candidates)
    assert all(x['code'] != 'OFF' for x in candidates)


@pytest.mark.parametrize('page', ['add', 'edit'])
def test_new_inactive_sales_lines_fail_atomically(page, policy_case):
    client, ids = policy_case
    before = snapshot()
    response = document_post(client, '/sales/add' if page == 'add' else f"/sales/{ids['order']}/edit",
                             json=payload(ids, ['OFF']))
    assert response.status_code == 400, response.json
    assert '停用' in response.json['msg']
    w.db.session.expire_all()
    assert snapshot() == before


def test_existing_inactive_sales_row_remains_editable(policy_case):
    client, ids = policy_case
    material = w.db.session.get(w.Material, ids['material'])
    material.status = 'inactive'
    w.db.session.commit()
    response = document_post(client, f"/sales/{ids['order']}/edit", json=payload(ids, ['FREE']))
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    order = w.db.session.get(w.SalesOrder, ids['order'])
    assert len(order.items) == 1 and order.items[0].material_id == ids['material']
    assert order.items[0].quantity == 2 and order.items[0].price == 0
    assert material.stock == 100 and w.StockTransaction.query.count() == 0


def test_new_inactive_row_cannot_borrow_an_existing_association(policy_case):
    client, ids = policy_case
    w.db.session.get(w.Material, ids['material']).status = 'inactive'
    w.db.session.commit()
    before = snapshot()
    response = document_post(client, f"/sales/{ids['order']}/edit", json=payload(ids, ['FREE', 'FREE']))
    assert response.status_code == 400, response.json
    assert '停用' in response.json['msg']
    w.db.session.expire_all()
    assert snapshot() == before


def test_historical_inactive_display_is_separate_from_new_choices(policy_case):
    client, ids = policy_case
    material = w.db.session.get(w.Material, ids['material'])
    material.status = 'inactive'
    w.db.session.commit()
    contexts = []
    def capture(sender, template, context, **unused):
        contexts.append(context)
    with template_rendered.connected_to(capture, w.app):
        response = client.get(f"/sales/{ids['order']}/edit")
    assert response.status_code == 200
    context = contexts[-1]
    assert all(x['code'] != 'FREE' for x in context['material_list'])
    history = context['existing_items'][0]
    assert history['code'] == 'FREE'
    assert history['material']['name'] == material.name
    assert history['material']['unit']['name'] == 'PCS'


@pytest.mark.parametrize('status', [None, ''])
def test_legacy_empty_material_status_remains_selectable(status, policy_case):
    client, ids = policy_case
    w.db.session.get(w.Material, ids['material']).status = status
    w.db.session.commit()
    response = document_post(client, '/sales/add', json=payload(ids, ['FREE']))
    assert response.status_code == 200, response.json
    order = w.db.session.get(w.SalesOrder, response.json['id'])
    assert order.items[0].material_id == ids['material']
    assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('code', ['OFF', 'FREE'])
def test_sales_excel_obeys_same_policy_without_empty_inactive_draft(code, policy_case):
    client, ids = policy_case
    before = snapshot()
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['销售订单号', '客户名称', '发货仓库', '物料编码', '数量'])
    sheet.append(['SO-POLICY-IMPORT', 'Collection fixture customer',
                  'Collection fixture warehouse', code, 2])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    response = client.post('/sales/import', data={'file': (stream, 'synthetic.xlsx')})
    assert response.status_code == 200, response.json
    if code == 'OFF':
        assert response.json['count'] == 0 and response.json['item_count'] == 0
        assert '停用' in response.json['warnings']
        assert snapshot() == before
    else:
        assert response.json['count'] == 1 and response.json['item_count'] == 1
        order = w.SalesOrder.query.filter_by(order_no='SO-POLICY-IMPORT').one()
        assert len(order.items) == 1 and order.items[0].material_id == ids['material']
        assert snapshot()['stock'] == before['stock']
        assert w.StockTransaction.query.count() == before['ledger']
