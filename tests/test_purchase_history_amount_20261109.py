"""Real purchase status refresh; owned LPAC/private-memory fixture only."""
from datetime import date
import pytest
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


def history(case, amount, completed=False, closed=False):
    w = case.w
    order = w.PurchaseOrder(order_no='S-PO-HISTORY', date=date.today(), status='closed' if closed else 'pending',
                            total_amount=0 if amount is None else amount, operator_id=case.ids['user'])
    other = w.PurchaseOrder(order_no='S-PO-OTHER', date=date.today(), status='pending', total_amount=99)
    w.db.session.add_all([order, other]);w.db.session.flush()
    item = w.PurchaseOrderItem(purchase_order_id=order.id, material_id=case.ids['material'],
                               quantity=1.15, price=3.5, amount=amount, received_quantity=0)
    other_item = w.PurchaseOrderItem(purchase_order_id=other.id, material_id=case.ids['material'],
                                     quantity=2, price=5, amount=99, received_quantity=0)
    w.db.session.add_all([item, other_item]);w.db.session.flush()
    if amount is None:
        item.amount = None
    if completed:
        receipt = w.InOrder(order_no='S-PO-RECEIPT', date=date.today(), status='completed',
                            business_type='采购入库', warehouse=case.warehouse, source_purchase_order_id=order.id)
        w.db.session.add(receipt);w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=receipt.id, source_purchase_order_item_id=item.id,
                                      material_id=case.ids['material'], quantity=.5, price=3.5, amount=1.75))
    w.db.session.commit()
    return order.id, item.id, other.id, other_item.id


@pytest.mark.parametrize('amount', [0, 4.02, 7.77, None])
@pytest.mark.parametrize('completed', [False, True])
def test_status_refresh_keeps_existing_amount_and_uses_completed_receipts_only(money_case, amount, completed):
    c = money_case;w = c.w
    oid, iid, other_id, other_iid = history(c, amount, completed)
    order = w.db.session.get(w.PurchaseOrder, oid)
    w.update_purchase_order_status(order)
    w.db.session.commit();w.db.session.remove()
    line = w.db.session.get(w.PurchaseOrderItem, iid)
    expected = 4.03 if amount is None else amount
    assert (line.quantity, line.price, line.amount) == (1.15, 3.5, expected)
    order = w.db.session.get(w.PurchaseOrder, oid)
    assert order.total_amount == expected
    assert order.status == ('partial' if completed else 'pending')
    assert w.db.session.get(w.PurchaseOrder, other_id).total_amount == 99
    assert w.db.session.get(w.PurchaseOrderItem, other_iid).amount == 99
    unchanged_inventory(c)


def test_closed_order_protection_does_not_change_any_financial_values(money_case):
    c = money_case;w = c.w
    oid, iid, _, _ = history(c, 7.77, completed=True, closed=True)
    order = w.db.session.get(w.PurchaseOrder, oid)
    w.update_purchase_order_status(order);w.db.session.commit()
    assert (order.status, order.total_amount, w.db.session.get(w.PurchaseOrderItem, iid).amount) == ('closed', 7.77, 7.77)
    unchanged_inventory(c)


def test_reopening_only_refreshes_status_and_keeps_historical_money(money_case):
    c = money_case;w = c.w
    oid, iid, _, _ = history(c, 7.77, completed=True, closed=True)
    response = c.client.post('/purchase_order/' + str(oid) + '/reopen', json={})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.remove();order = w.db.session.get(w.PurchaseOrder, oid)
    assert order.status == 'partial'
    assert (order.total_amount, w.db.session.get(w.PurchaseOrderItem, iid).amount) == (7.77, 7.77)
    unchanged_inventory(c)
