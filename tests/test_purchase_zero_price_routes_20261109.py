"""Real zero-price purchase flows on the owned synthetic-memory fixture."""
from datetime import date
import pytest
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


@pytest.mark.parametrize('split', [False, True])
@pytest.mark.parametrize('price', [0, None])
def test_request_push_keeps_zero_and_only_defaults_a_missing_estimate(money_case, split, price):
    c = money_case;w = c.w
    assert w.db.session.get(w.Material, c.ids['material']).price == .5
    request = w.PurchaseRequest(request_no='S-ZERO-PR', date=date.today(), status='approved', applicant='合成申请')
    suppliers = [w.Supplier(code='S-ZERO-S'+str(i), name='合成供应商'+str(i)) for i in range(2 if split else 1)]
    w.db.session.add_all([request, *suppliers]);w.db.session.flush()
    rows = [w.PurchaseRequestItem(purchase_request_id=request.id, material_id=c.ids['material'],
                                 material_code='B-M', material_name='合成物料', quantity=2,
                                 estimated_price=price, estimated_amount=0, supplier_id=supplier.id)
            for supplier in suppliers]
    w.db.session.add_all(rows);w.db.session.flush()
    for row in rows:
        row.estimated_price = price
    w.db.session.commit();rid=request.id
    response = c.client.post('/purchase_request/'+str(rid)+'/create_purchase_order', json={})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.remove()
    orders = w.PurchaseOrder.query.filter_by(purchase_request_id=rid).all()
    assert len(orders) == len(suppliers)
    for order in orders:
        assert order.status == 'pending' and len(order.items) == 1
        assert order.items[0].price == (0 if price == 0 else .5)
        assert order.items[0].amount == order.total_amount == (0 if price == 0 else 1)
    assert [row.estimated_price for row in w.PurchaseRequestItem.query.order_by(w.PurchaseRequestItem.id)] == [price]*len(rows)
    unchanged_inventory(c)


def purchase(case, price):
    w = case.w
    order = w.PurchaseOrder(order_no='S-ZERO-PO', date=date.today(), status='pending', total_amount=0)
    w.db.session.add(order);w.db.session.flush()
    item = w.PurchaseOrderItem(purchase_order_id=order.id, material_id=case.ids['material'],
                               quantity=2, received_quantity=0, price=price, amount=0)
    w.db.session.add(item);w.db.session.flush();item.price=price
    w.db.session.commit()
    return order.id, item.id


@pytest.mark.parametrize('selection', [False, True])
@pytest.mark.parametrize('price', [0, None])
def test_receipt_draft_preserves_zero_price_in_both_purchase_paths(money_case, selection, price):
    c = money_case;w = c.w
    w.set_system_setting('purchase_order_to_in_order_enabled', '1')
    oid, iid = purchase(c, price)
    if selection:
        endpoint = '/purchase_order/create_in_order_from_selection'
        body = {'warehouse_id': c.wh1, 'items': [{'purchase_order_item_id': iid, 'quantity': 2}]}
    else:
        endpoint = '/purchase_order/'+str(oid)+'/create_in_order'
        body = {'warehouse': c.warehouse}
    response = c.client.post(endpoint, json=body)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.remove()
    draft = w.db.session.get(w.InOrder, response.json['id'])
    assert draft.status == 'pending' and draft.warehouse == c.warehouse
    assert len(draft.items) == 1 and draft.items[0].source_purchase_order_item_id == iid
    assert draft.items[0].price == (0 if price == 0 else .5)
    assert draft.items[0].amount == draft.total_amount == (0 if price == 0 else 1)
    assert w.db.session.get(w.PurchaseOrderItem, iid).price == price
    unchanged_inventory(c)


@pytest.mark.parametrize('price', [0, .5])
def test_copy_accepts_a_valid_zero_total_without_changing_its_source(money_case, price):
    c = money_case;w = c.w
    oid, iid = purchase(c, price)
    response = c.client.post('/purchase_order/'+str(oid)+'/copy', json={})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.remove()
    assert response.json['id'] != oid
    copy = w.db.session.get(w.PurchaseOrder, response.json['id'])
    assert copy.status == 'pending' and len(copy.items) == 1
    assert copy.items[0].quantity == 2 and copy.items[0].price == price
    assert copy.items[0].amount == copy.total_amount == 2*price
    original = w.db.session.get(w.PurchaseOrderItem, iid)
    assert (original.quantity, original.price, original.amount) == (2, price, 0)
    unchanged_inventory(c)


def test_copy_keeps_existing_negative_total_rejection(money_case):
    c = money_case;w = c.w
    oid, iid = purchase(c, -.5)
    before = w.PurchaseOrder.query.count()
    response = c.client.post('/purchase_order/'+str(oid)+'/copy', json={})
    assert response.status_code == 400 and response.json['status'] == 'error', response.json
    w.db.session.remove()
    assert w.PurchaseOrder.query.count() == before
    original = w.db.session.get(w.PurchaseOrderItem, iid)
    assert (original.quantity, original.price, original.amount) == (2, -.5, 0)
    unchanged_inventory(c)
