"""Actual Node copy payload persisted through owned private-memory ORM routes.

Run only through the repository's authenticated Linux isolation launcher. The
existing money_case fixture supplies synthetic objects; this is never a host probe.
"""
from decimal import Decimal

import pytest

from tests.document_revision_client import document_post
from tests.test_document_copy_money_contract_20261113 import CASES, capture_copy, rounded
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory
from tests.test_purchase_edit_history_20261113 import history as purchase_history
from tests.test_sales_edit_history_20261113 import history as sales_history


@pytest.mark.parametrize('kind,path', [('purchase', 'previous'), ('purchase', 'after'), ('sales', 'previous'), ('sales', 'template')])
@pytest.mark.parametrize('quantity,price,default_price', CASES)
def test_copy_display_payload_and_persisted_money_agree(money_case, kind, path, quantity, price, default_price):
    c = money_case
    w = c.w
    if kind == 'purchase':
        oid, iid, source_id, payload = purchase_history(c, quantity=quantity, price=price)
        line_model, order_model = w.PurchaseOrderItem, w.PurchaseOrder
        url = '/purchase_order/save'
    else:
        oid, iid, payload = sales_history(c, quantity=quantity)
        line_model, order_model = w.SalesOrderItem, w.SalesOrder
        w.db.session.get(line_model, iid).price = price
        url = f'/sales/{oid}/edit'
    w.db.session.get(w.Material, c.ids['material']).price = default_price
    w.db.session.commit()
    original = w.db.session.get(line_model, iid)
    shown = capture_copy(kind, path, quantity, price, default_price)
    for row in shown['items']:
        row['line_id'] = iid if row['line_id'] is not None else None
        if kind == 'purchase':
            row['material_id'] = c.ids['material']
    payload['items'] = shown['items']
    response = document_post(c.client, url, json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    order = w.db.session.get(order_model, oid)
    if path == 'template':
        # SQLite may reuse a deleted maximum PK. Prove object replacement, not PK novelty.
        new, = order.items
        assert new is not original
    else:
        old = w.db.session.get(line_model, iid)
        new, = (row for row in order.items if row.id != iid)
        assert (old.quantity, old.price, float(old.amount)) == (quantity, price, 4.02)
    expected_qty = rounded(quantity)
    expected_price = rounded(default_price if price is None else price)
    expected_amount = rounded(Decimal(str(expected_qty)) * Decimal(str(expected_price)))
    assert (new.quantity, new.price, float(new.amount)) == (expected_qty, expected_price, expected_amount)
    assert Decimal(str(shown['items'][-1]['quantity'])) == Decimal(str(new.quantity))
    assert Decimal(str(shown['items'][-1]['price'])) == Decimal(str(new.price))
    assert Decimal(shown['copied']['amount']) == Decimal(str(new.amount))
    assert Decimal(shown['total'].lstrip('¥')) == Decimal(str(order.total_amount))
    if kind == 'purchase':
        assert old.purchase_request_item_id == source_id and new.purchase_request_item_id is None
    unchanged_inventory(c)
