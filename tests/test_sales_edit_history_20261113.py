"""Real sales edit persistence/ownership: existing owned private-memory profile only."""
from datetime import date
from decimal import Decimal
import json
import re

import pytest

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory

FINANCE = ('amount', 'tax_included_amount', 'untaxed_amount', 'tax_amount', 'untaxed_price')


def history(case, amount=Decimal('4.02'), quantity=1.2345):
    w = case.w
    order = w.SalesOrder(order_no='SO-SYN-HISTORY-EDIT', date=date.today(), status='draft',
                         customer_id=case.customer, warehouse=case.warehouse, warehouse_id=case.wh1,
                         remark='original header', total_amount=Decimal('9.99'),
                         untaxed_amount=Decimal('3.50'), tax_amount=Decimal('.52'))
    w.db.session.add(order)
    w.db.session.flush()
    line = w.SalesOrderItem(sales_order_id=order.id, material_id=case.ids['material'],
                            quantity=quantity, price=3.56789, tax_rate=.13, amount=amount,
                            tax_included_amount=amount, untaxed_amount=Decimal('3.50'),
                            tax_amount=Decimal('.52'), untaxed_price=3.0435, remark='old line')
    w.db.session.add(line)
    w.db.session.commit()
    payload = dict(customer_id=case.customer, warehouse_id=case.wh1, date=date.today().isoformat(),
                   remark='only header changed', items=[dict(line_id=line.id, code='B-M', quantity=str(quantity),
                    price='3.56789', tax_rate='.13', remark='old line')])
    return order.id, line.id, payload


def snapshot(case, oid):
    w = case.w
    w.db.session.expire_all()
    order = w.db.session.get(w.SalesOrder, oid)
    return (order.total_amount, order.untaxed_amount, order.tax_amount,
            tuple(sorted((line.id, line.material_id, line.quantity, line.price, line.tax_rate,
                          *(getattr(line, key) for key in FINANCE)) for line in order.items)))


@pytest.mark.parametrize('amount', [Decimal('0'), Decimal('4.02'), Decimal('7.77')])
@pytest.mark.parametrize('quantity', [1.2345, .0001])
def test_only_remarks_preserve_history_identity_and_exact_components(money_case, amount, quantity):
    c = money_case
    w = c.w
    oid, iid, payload = history(c, amount, quantity)
    before = snapshot(c, oid)
    payload['items'][0].update(remark='line remark changed', saved_amount=999, amount=888)
    page = c.client.get(f'/sales/{oid}/edit')
    assert page.status_code == 200
    match = re.search(r'var existingItems = (.*);', page.get_data(as_text=True))
    assert match
    shown, = json.loads(match.group(1))
    assert (shown['line_id'], shown['quantity'], shown['price']) == (iid, quantity, 3.56789)
    assert Decimal(str(shown['amount'])) == amount
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert snapshot(c, oid) == before
    assert w.db.session.get(w.SalesOrderItem, iid).remark == 'line remark changed'
    assert w.db.session.get(w.SalesOrder, oid).remark == 'only header changed'
    unchanged_inventory(c)


@pytest.mark.parametrize('field,value,quantity,price,amount,tax', [
    ('quantity', '1.23', 1.23, 3.56789, '4.39', '.51'),
    ('price', '0', 1.2345, 0, '0', '0'),
    ('tax_rate', '0', 1.2345, 3.56789, '4.40', '0'),
])
def test_explicit_financial_change_updates_only_changed_components(money_case, field, value, quantity, price, amount, tax):
    c = money_case
    w = c.w
    oid, iid, payload = history(c)
    payload['items'][0][field] = value
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.SalesOrderItem, iid)
    assert (line.quantity, line.price, line.amount, line.tax_amount) == (
        quantity, price, Decimal(amount), Decimal(tax))
    assert w.db.session.get(w.SalesOrder, oid).total_amount == Decimal(amount)
    unchanged_inventory(c)


@pytest.mark.parametrize('variant', ['foreign', 'duplicate', 'zero', 'bool', 'float'])
def test_unowned_duplicate_or_invalid_line_identity_is_atomic(money_case, variant):
    c = money_case
    oid, iid, payload = history(c)
    before = snapshot(c, oid)
    if variant == 'duplicate':
        payload['items'].append(dict(payload['items'][0]))
    else:
        payload['items'][0]['line_id'] = {'foreign': iid + 999, 'zero': 0, 'bool': True, 'float': float(iid)}[variant]
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 400, response.json
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_modern_remove_add_and_same_material_reorder_use_owned_ids(money_case):
    c = money_case
    w = c.w
    oid, iid, payload = history(c)
    second = w.SalesOrderItem(sales_order_id=oid, material_id=c.ids['material'], quantity=2.2222,
                              price=9.87654, tax_rate=0, amount=Decimal('7.77'),
                              tax_included_amount=Decimal('7.77'), untaxed_amount=Decimal('7.77'),
                              tax_amount=0, untaxed_price=9.87654)
    w.db.session.add(second)
    w.db.session.commit()
    second_id = second.id
    payload['items'].insert(0, dict(line_id=second_id, code='B-M', quantity='2.2222', price='9.87654', tax_rate='0'))
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200, response.json
    assert w.db.session.get(w.SalesOrderItem, iid).amount == Decimal('4.02')
    assert w.db.session.get(w.SalesOrderItem, second_id).amount == Decimal('7.77')
    payload['items'] = [payload['items'][1], dict(line_id=None, code='B-M', quantity='2', price='3', tax_rate='0')]
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    order = w.db.session.get(w.SalesOrder, oid)
    assert len(order.items) == 2 and order.total_amount == Decimal('10.02')
    assert w.db.session.get(w.SalesOrderItem, iid).amount == Decimal('4.02')
    assert sorted((line.quantity, line.amount) for line in order.items) == [(1.2345, Decimal('4.02')), (2, Decimal('6'))]
    unchanged_inventory(c)


def test_legacy_without_ids_keeps_explicit_replace_policy(money_case):
    c = money_case
    w = c.w
    oid, iid, payload = history(c)
    payload['items'][0].pop('line_id')
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    line, = w.db.session.get(w.SalesOrder, oid).items
    assert (line.quantity, line.price, line.amount) == (1.23, 3.57, Decimal('4.39'))
    unchanged_inventory(c)


@pytest.mark.parametrize('kind', ['out_header', 'out_line', 'in_header', 'in_line', 'shipped'])
def test_draft_with_downstream_or_shipped_history_cannot_be_rebuilt(money_case, kind):
    c = money_case
    w = c.w
    oid, iid, payload = history(c)
    if kind == 'shipped':
        w.db.session.get(w.SalesOrderItem, iid).shipped_quantity = .5
    elif kind.startswith('out'):
        target = w.OutOrder(order_no='S-SALES-EDIT-LINK', warehouse=c.warehouse, status='pending',
                             business_type='销售出库', source_sales_order_id=oid if kind == 'out_header' else None)
        w.db.session.add(target)
        w.db.session.flush()
        if kind == 'out_line':
            w.db.session.add(w.OutOrderItem(out_order_id=target.id, material_id=c.ids['material'],
                quantity=.1, price=1, amount=.1, source_sales_order_item_id=iid))
    else:
        target = w.InOrder(order_no='S-SALES-EDIT-LINK', warehouse=c.warehouse, status='pending',
                            business_type='销售退货入库', source_sales_order_id=oid if kind == 'in_header' else None)
        w.db.session.add(target)
        w.db.session.flush()
        if kind == 'in_line':
            w.db.session.add(w.InOrderItem(in_order_id=target.id, material_id=c.ids['material'],
                quantity=.1, price=1, amount=.1, source_sales_order_item_id=iid))
    w.db.session.commit()
    before = snapshot(c, oid)
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 409, response.json
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_new_zero_row_is_rejected_and_original_history_rolls_back(money_case):
    c = money_case
    oid, iid, payload = history(c)
    before = snapshot(c, oid)
    payload['items'].append(dict(line_id=None, code='B-M', quantity='0', price='3', tax_rate='0'))
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 400, response.json
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_missing_signed_revision_is_rejected_without_changes(money_case):
    c = money_case
    oid, iid, payload = history(c)
    before = snapshot(c, oid)
    response = c.client.post(f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 409, response.json
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_foreign_existing_line_cannot_be_edited_through_this_order(money_case):
    c = money_case
    w = c.w
    oid, iid, payload = history(c)
    other = w.SalesOrder(order_no='SO-SYN-FOREIGN', status='draft', customer_id=c.customer,
                         warehouse=c.warehouse, warehouse_id=c.wh1, total_amount=99)
    w.db.session.add(other)
    w.db.session.flush()
    foreign = w.SalesOrderItem(sales_order_id=other.id, material_id=c.ids['material'], quantity=2,
                                price=5, amount=99, tax_included_amount=99)
    w.db.session.add(foreign)
    w.db.session.commit()
    foreign_id = foreign.id
    before = snapshot(c, oid)
    other_before = snapshot(c, other.id)
    payload['items'][0]['line_id'] = foreign_id
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 400, response.json
    assert snapshot(c, oid) == before and snapshot(c, other.id) == other_before
    unchanged_inventory(c)


def test_missing_price_preserves_history_until_operator_enters_a_price(money_case):
    c = money_case
    w = c.w
    oid, iid, payload = history(c)
    w.db.session.get(w.SalesOrderItem, iid).price = None
    w.db.session.commit()
    payload['items'][0]['price'] = ''
    before = snapshot(c, oid)
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200, response.json
    assert snapshot(c, oid) == before
    payload['items'][0]['price'] = '3.5'
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.SalesOrderItem, iid)
    assert (line.price, line.amount) == (3.5, Decimal('4.32'))
    unchanged_inventory(c)
