"""Unknown historical price: only existing owned private-memory fixture may run."""
from decimal import Decimal

import pytest

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory
from tests.test_sales_edit_history_20261113 import history, snapshot


@pytest.mark.parametrize('field,value', [('quantity', '2'), ('tax_rate', '0')])
def test_blank_unknown_price_rejects_financial_change_atomically(money_case, field, value):
    c = money_case
    w = c.w
    oid, iid, payload = history(c, amount=Decimal('7.77'))
    w.db.session.get(w.SalesOrderItem, iid).price = None
    w.db.session.commit()
    payload['items'][0].update(price='', **{field: value})
    before = snapshot(c, oid)
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 400 and response.json['status'] == 'error', response.json
    assert '单价' in response.json['msg']
    assert snapshot(c, oid) == before
    assert w.db.session.get(w.SalesOrder, oid).remark == 'original header'
    assert w.db.session.get(w.SalesOrderItem, iid).price is None
    unchanged_inventory(c)


@pytest.mark.parametrize('price,amount', [('0', Decimal('0')), ('3.5', Decimal('7'))])
def test_explicit_zero_or_positive_price_allows_financial_change(money_case, price, amount):
    c = money_case
    w = c.w
    oid, iid, payload = history(c, amount=Decimal('7.77'))
    w.db.session.get(w.SalesOrderItem, iid).price = None
    w.db.session.commit()
    payload['items'][0].update(quantity='2', price=price)
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.SalesOrderItem, iid)
    assert (line.quantity, line.price, line.amount) == (2, float(price), amount)
    assert w.db.session.get(w.SalesOrder, oid).total_amount == amount
    unchanged_inventory(c)
