"""Purchase history/identity persistence; existing owned private-memory fixture only."""
from datetime import date

import pytest

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


def history(case, amount=4.02, quantity=1.2345, price=3.56789):
    w = case.w
    supplier = w.Supplier(code='S-PO-HISTORY', name='合成历史供应商')
    request = w.PurchaseRequest(request_no='PR-SYN-HISTORY', date=date.today(), status='approved',
                                applicant='合成申请人', total_amount=amount or 0)
    w.db.session.add_all([supplier, request])
    w.db.session.flush()
    source = w.PurchaseRequestItem(purchase_request_id=request.id, material_id=case.ids['material'],
                                    quantity=quantity, estimated_price=price or 0, estimated_amount=amount or 0)
    w.db.session.add(source)
    w.db.session.flush()
    order = w.PurchaseOrder(order_no='PO-SYN-HISTORY', date=date.today(), supplier_id=supplier.id,
                            purchase_request_id=request.id, status='pending', total_amount=9.99,
                            operator_id=case.ids['user'], remark='original header')
    w.db.session.add(order)
    w.db.session.flush()
    line = w.PurchaseOrderItem(purchase_order_id=order.id, purchase_request_item_id=source.id,
                                material_id=case.ids['material'], quantity=quantity, received_quantity=0,
                                price=price or 0, amount=amount or 0, remark='original line')
    w.db.session.add(line)
    w.db.session.flush()
    line.price = price
    line.amount = amount
    w.db.session.commit()
    payload = dict(order_id=order.id, date=date.today().isoformat(), supplier_id=supplier.id,
                   remark='only header changed', items=[dict(line_id=line.id, material_id=case.ids['material'],
                    material_code='B-M', quantity=str(quantity), price='' if price is None else str(price),
                    remark='original line')])
    return order.id, line.id, source.id, payload


def snapshot(case, oid):
    w = case.w
    w.db.session.expire_all()
    order = w.db.session.get(w.PurchaseOrder, oid)
    return order.total_amount, order.purchase_request_id, tuple(sorted(
        (line.id, line.material_id, line.quantity, line.price, line.amount, line.received_quantity,
         line.purchase_request_item_id) for line in order.items))


@pytest.mark.parametrize('amount', [0, 4.02, 7.77])
@pytest.mark.parametrize('quantity', [1.2345, .0001])
def test_only_remarks_preserve_recorded_amount_precision_and_request_source(money_case, amount, quantity):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c, amount, quantity)
    before = snapshot(c, oid)
    page = c.client.get(f'/purchase_order/{oid}/edit')
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    assert f'line_id: {iid},' in text and 'price: 3.56789,' in text
    payload['items'][0].update(remark='line note changed', saved_amount=999, amount=888)
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert snapshot(c, oid) == before
    line = w.db.session.get(w.PurchaseOrderItem, iid)
    assert line.purchase_request_item_id == source_id and line.remark == 'line note changed'
    assert w.db.session.get(w.PurchaseOrder, oid).remark == 'only header changed'
    unchanged_inventory(c)


@pytest.mark.parametrize('field,value,quantity,price,amount', [
    ('quantity', '2', 2, 3.56789, 7.14),
    ('quantity', '1.23', 1.23, 3.56789, 4.39),
    ('price', '0', 1.2345, 0, 0),
])
def test_explicit_financial_change_preserves_other_component_and_source(money_case, field, value, quantity, price, amount):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c)
    payload['items'][0][field] = value
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.PurchaseOrderItem, iid)
    assert (line.quantity, line.price, line.amount, line.purchase_request_item_id) == (quantity, price, amount, source_id)
    assert w.db.session.get(w.PurchaseOrder, oid).total_amount == amount
    unchanged_inventory(c)


def test_none_amount_is_backfilled_without_overwriting_known_header(money_case):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c, amount=None, quantity=1.15, price=3.5)
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.PurchaseOrderItem, iid)
    assert (line.quantity, line.price, line.amount, line.purchase_request_item_id) == (1.15, 3.5, 4.03, source_id)
    assert w.db.session.get(w.PurchaseOrder, oid).total_amount == 9.99
    unchanged_inventory(c)


def test_missing_price_remains_missing_until_operator_enters_price(money_case):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c, amount=7.77, price=None)
    before = snapshot(c, oid)
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200, response.json
    assert snapshot(c, oid) == before
    payload['items'][0]['price'] = '3.5'
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.PurchaseOrderItem, iid)
    assert (line.price, line.amount, line.purchase_request_item_id) == (3.5, 4.32, source_id)
    unchanged_inventory(c)


@pytest.mark.parametrize('variant', ['foreign', 'duplicate', 'zero', 'bool', 'float'])
def test_invalid_or_foreign_identity_cannot_match_another_same_material_line(money_case, variant):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c)
    other = w.PurchaseOrder(order_no='PO-SYN-OTHER', status='pending', total_amount=99)
    w.db.session.add(other)
    w.db.session.flush()
    foreign = w.PurchaseOrderItem(purchase_order_id=other.id, material_id=c.ids['material'],
                                   quantity=2, price=5, amount=99)
    w.db.session.add(foreign)
    w.db.session.commit()
    other_id, foreign_id = other.id, foreign.id
    before, other_before = snapshot(c, oid), snapshot(c, other_id)
    if variant == 'duplicate':
        payload['items'].append(dict(payload['items'][0]))
    else:
        payload['items'][0]['line_id'] = {'foreign': foreign_id, 'zero': 0, 'bool': True, 'float': float(iid)}[variant]
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 400, response.json
    assert snapshot(c, oid) == before and snapshot(c, other_id) == other_before
    unchanged_inventory(c)


@pytest.mark.parametrize('kind', ['header_pending', 'header_completed', 'line_pending', 'line_completed', 'orphan_received'])
def test_existing_downstream_and_received_guards_preserve_history(money_case, kind):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c)
    if kind == 'orphan_received':
        w.db.session.get(w.PurchaseOrderItem, iid).received_quantity = .5
    else:
        inbound = w.InOrder(order_no='IN-SYN-HISTORY', date=date.today(), warehouse=c.warehouse,
                            business_type='采购入库', status='completed' if kind.endswith('completed') else 'pending',
                            source_purchase_order_id=oid if kind.startswith('header') else None)
        w.db.session.add(inbound)
        w.db.session.flush()
        if kind.startswith('line'):
            w.db.session.add(w.InOrderItem(in_order_id=inbound.id, material_id=c.ids['material'],
                quantity=.1, price=1, amount=.1, source_purchase_order_item_id=iid))
    w.db.session.commit()
    before = snapshot(c, oid)
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 400, response.json
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_stale_signed_revision_is_not_bypassed_by_existing_write_lock(money_case):
    from tests.test_document_edit_conflicts import revision
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c)
    token = revision(c.client, f'/purchase_order/{oid}')
    w.db.session.get(w.PurchaseOrderItem, iid).remark = 'other synthetic edit'
    w.db.session.commit()
    before = snapshot(c, oid)
    response = c.client.post('/purchase_order/save', json=payload, headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 409, response.json
    assert snapshot(c, oid) == before
    assert w.db.session.get(w.PurchaseOrderItem, iid).remark == 'other synthetic edit'
    unchanged_inventory(c)


def test_missing_signed_revision_cannot_use_server_owned_line_id(money_case):
    c = money_case
    oid, iid, source_id, payload = history(c)
    before = snapshot(c, oid)
    response = c.client.post('/purchase_order/save', json=payload)
    assert response.status_code == 409, response.json
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_new_zero_quantity_rolls_back_all_header_and_line_changes(money_case):
    c = money_case
    oid, iid, source_id, payload = history(c)
    before = snapshot(c, oid)
    payload['items'].append(dict(line_id=None, material_id=c.ids['material'], quantity='0', price='3'))
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 400, response.json
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_retained_removed_and_new_rows_keep_only_owned_sources(money_case):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c)
    removed = w.PurchaseOrderItem(purchase_order_id=oid, material_id=c.ids['material'], quantity=2,
                                   price=5, amount=7.77)
    w.db.session.add(removed)
    w.db.session.commit()
    payload['items'].append(dict(line_id=None, material_id=c.ids['material'], quantity='2', price='3'))
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    order = w.db.session.get(w.PurchaseOrder, oid)
    assert len(order.items) == 2 and order.total_amount == 10.02
    assert w.db.session.get(w.PurchaseOrderItem, iid).purchase_request_item_id == source_id
    added, = [line for line in order.items if line.id != iid]
    assert (added.quantity, added.amount, added.purchase_request_item_id) == (2, 6, None)
    unchanged_inventory(c)


def test_material_replacement_is_explicit_new_row_without_old_request_link(money_case):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c)
    second = w.Material(code='PO-SYN-NEW', name='合成另一物料', stock=0, price=3, unit_id=c.ids['unit'])
    w.db.session.add(second)
    w.db.session.commit()
    second_id = second.id
    before = snapshot(c, oid)
    payload['items'][0].update(material_id=second_id, material_code='PO-SYN-NEW')
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 400, response.json
    assert snapshot(c, oid) == before
    payload['items'][0]['line_id'] = None
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200, response.json
    w.db.session.expire_all()
    line, = w.db.session.get(w.PurchaseOrder, oid).items
    assert line.material_id == second_id and line.purchase_request_item_id is None
    assert w.db.session.get(w.Material, second_id).stock == 0
    unchanged_inventory(c)


def test_new_document_cannot_carry_an_existing_line_identity(money_case):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c)
    before = snapshot(c, oid)
    payload['order_id'] = None
    response = c.client.post('/purchase_order/save', json=payload)
    assert response.status_code == 400, response.json
    w.db.session.expire_all()
    assert w.PurchaseOrder.query.count() == 1 and w.PurchaseOrderItem.query.count() == 1
    assert snapshot(c, oid) == before
    unchanged_inventory(c)


def test_unknown_blank_price_rejects_quantity_change_without_clearing_money(money_case):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c, amount=7.77, price=None)
    payload['items'][0].update(quantity='2', price='')
    before = snapshot(c, oid)
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 400 and '单价' in response.json['msg'], response.json
    assert snapshot(c, oid) == before
    assert w.db.session.get(w.PurchaseOrder, oid).remark == 'original header'
    assert w.db.session.get(w.PurchaseOrderItem, iid).price is None
    unchanged_inventory(c)


@pytest.mark.parametrize('price,amount', [('0', 0), ('3.5', 7)])
def test_explicit_price_allows_quantity_change_for_missing_historical_price(money_case, price, amount):
    c = money_case
    w = c.w
    oid, iid, source_id, payload = history(c, amount=7.77, price=None)
    payload['items'][0].update(quantity='2', price=price)
    response = document_post(c.client, '/purchase_order/save', json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.PurchaseOrderItem, iid)
    assert (line.quantity, line.price, line.amount, line.purchase_request_item_id) == (2, float(price), amount, source_id)
    assert w.db.session.get(w.PurchaseOrder, oid).total_amount == amount
    unchanged_inventory(c)
