"""Actual WMS routes; only an owned Windows LPAC and private memory DB may run."""
from datetime import date
from decimal import Decimal
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import uuid

import pytest


@pytest.fixture
def money_case(request):
    root = Path(__file__).resolve().parents[1]
    guard = runpy.run_path(str(root / 'scripts/verify_db_guard.py'))
    guard['require_owned_test_profile']()
    assert all(os.environ.get(key) == 'sqlite:///:memory:'
               for key in ('DATABASE_URL', 'WMS_DATABASE_URI'))
    client, ids = request.getfixturevalue('bom_case')
    import app as w
    assert str(w.db.engine.url) == 'sqlite:///:memory:'
    assert all(not row[2] for row in w.db.session.connection().exec_driver_sql('PRAGMA database_list'))
    wh1 = w.Warehouse(code='S-MONEY-W1', name='合成金额甲仓', status='active')
    wh2 = w.Warehouse(code='S-MONEY-W2', name='合成金额乙仓', status='active')
    customer = w.Customer(code='S-MONEY-C', name='合成金额客户')
    w.db.session.add_all([wh1, wh2, customer])
    w.db.session.flush()
    material = w.db.session.get(w.Material, ids['material'])
    material.price = .5
    for warehouse in (wh1, wh2):
        w.db.session.add(w.LocationInventory(material_id=material.id, warehouse_id=warehouse.id,
                                             location=warehouse.name, quantity=5))
        w.db.session.add(w.StockTransaction(material_id=material.id, warehouse_id=warehouse.id,
                                            transaction_type='in', quantity=5, location=warehouse.name))
    w.db.session.commit()
    w.set_system_setting('location_management_enabled', '0')
    result = SimpleNamespace(w=w, client=client, ids=ids, wh1=wh1.id, wh2=wh2.id,
                             warehouse=wh1.name, customer=customer.id)
    yield result
    w.db.session.remove()


def money(value):
    return Decimal(str(value))


def unchanged_inventory(case):
    w = case.w
    assert w.db.session.get(w.Material, case.ids['material']).stock == 10
    assert w.LocationInventory.query.order_by(w.LocationInventory.warehouse_id).with_entities(
        w.LocationInventory.warehouse_id, w.LocationInventory.quantity).all() == [(case.wh1, 5), (case.wh2, 5)]
    assert w.StockTransaction.query.count() == 2


def test_inbound_draft_persists_decimal_product_without_stock_changes(money_case):
    c = money_case
    response = c.client.post('/in_order/add', json={
        'date': date.today().isoformat(), 'business_type': '其他入库', 'purpose': '合成金额回归',
        'warehouse_id': c.wh1, 'items': [{'code': 'B-M', 'quantity': 1.15, 'price': 3.5}]})
    assert response.status_code == 200, response.json
    assert response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    order = c.w.db.session.get(c.w.InOrder, response.json['id'])
    assert order.status == 'pending' and order.warehouse == c.warehouse
    assert len(order.items) == 1 and money(order.items[0].amount) == Decimal('4.03')
    assert money(order.total_amount) == Decimal('4.03')
    unchanged_inventory(c)


@pytest.mark.parametrize('target', ['other_out', 'after_sale_out'])
def test_push_rounds_lines_before_header_and_retry_keeps_one_draft(money_case, target):
    c = money_case
    w = c.w
    source = w.InOrder(order_no='S-MONEY-SOURCE', date=date.today(), business_type='其他入库',
                       warehouse=c.warehouse, status='completed', operator_id=c.ids['user'])
    w.db.session.add(source)
    w.db.session.flush()
    rows = [w.InOrderItem(in_order_id=source.id, material_id=c.ids['material'],
                          quantity=.01, price=.5, amount=.01) for _ in range(2)]
    w.db.session.add_all(rows)
    w.db.session.commit()
    source_id = source.id
    payload = {'target_type': target, 'request_id': uuid.uuid4().hex, 'purpose': '合成金额回归',
               'reason': '合成金额回归', 'customer_id': c.customer,
               'items': [{'source_item_id': row.id, 'quantity': .01} for row in rows]}
    response = c.client.post('/in_order/' + str(source_id) + '/push', json=payload)
    assert response.status_code == 200, response.json
    assert response.json['status'] == 'success', response.json
    ident = response.json['id']
    retry = c.client.post('/in_order/' + str(source_id) + '/push', json=payload)
    assert retry.status_code == 200 and retry.json['id'] == ident, retry.json
    w.db.session.remove()
    model = w.OutOrder if target == 'other_out' else w.AfterSaleOutOrder
    draft = w.db.session.get(model, ident)
    assert model.query.count() == 1 and draft.status == 'pending' and draft.warehouse == c.warehouse
    assert [money(row.amount) for row in draft.items] == [Decimal('.01'), Decimal('.01')]
    assert money(draft.total_amount) == sum((money(row.amount) for row in draft.items), Decimal(0)) == Decimal('.02')
    assert w.DocumentPushLine.query.count() == 2
    unchanged_inventory(c)


@pytest.mark.parametrize('quantity,price,expected', [(1.15, 3.5, '4.03'), (.01, .5, '.01')])
def test_purchase_request_stores_each_rounded_line_before_total(money_case, quantity, price, expected):
    c = money_case
    response = c.client.post('/purchase_request/add', json={
        'date': date.today().isoformat(), 'applicant': '合成申请人',
        'items': [{'material_id': c.ids['material'], 'material_code': 'B-M',
                   'quantity': quantity, 'estimated_price': price, 'unit_id': c.ids['unit']}
                  for _ in range(2)]})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    order = c.w.db.session.get(c.w.PurchaseRequest, response.json['id'])
    assert order.status == 'pending' and len(order.items) == 2
    assert all(money(item.estimated_amount) == Decimal(expected) for item in order.items)
    assert money(order.total_amount) == Decimal(expected) * 2
    unchanged_inventory(c)


def test_bom_cost_and_saved_line_agree_for_half_cent(money_case):
    c = money_case
    response = c.client.post('/bom/save_table', json={
        'order_id': c.ids['bom'], 'order_no': 'BOM-AUDIT',
        'header': {'product_code': 'B-P', 'product_name': '审计产品', 'version': 'V1', 'status': 'active'},
        'items': [{'code': 'B-M', 'quantity': 1.15, 'unit_id': c.ids['unit'], 'price': 3.5}]})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    bom = c.w.db.session.get(c.w.BOM, c.ids['bom'])
    assert len(bom.items) == 1 and money(bom.items[0].total_cost) == Decimal('4.03')
    assert money(bom.total_cost) == Decimal('4.03')
    unchanged_inventory(c)


def test_outbound_paste_uses_decimal_product(money_case):
    from tests.document_revision_client import document_post
    c = money_case
    order = c.w.OutOrder(order_no='S-MONEY-PASTE', date=date.today(), business_type='其他出库',
                         warehouse=c.warehouse, status='pending', operator_id=c.ids['user'])
    c.w.db.session.add(order)
    c.w.db.session.commit()
    ident = order.id
    response = document_post(c.client, '/out_order/' + str(ident) + '/batch_add_items',
                             json={'content': 'B-M,1.15,3.5'})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    c.w.db.session.remove()
    order = c.w.db.session.get(c.w.OutOrder, ident)
    assert len(order.items) == 1 and money(order.items[0].amount) == Decimal('4.03')
    assert money(order.total_amount) == Decimal('4.03') and order.status == 'pending'
    unchanged_inventory(c)
