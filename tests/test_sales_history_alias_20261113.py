"""Actual sales alias persistence: only existing owned private-memory fixture may run."""
from decimal import Decimal

import pytest

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory
from tests.test_sales_edit_history_20261113 import history

ALIASES = [
    (Decimal('7.77'), None, '7.77', '7.77', '7.77'),
    (None, Decimal('7.77'), '7.77', '7.77', '7.77'),
    (Decimal('0'), None, '0', '0', '0'),
    (None, Decimal('0'), '0', '0', '0'),
    (None, None, '4.03', '4.03', '4.03'),
    (Decimal('0'), Decimal('4.02'), '0', '4.02', '4.02'),
    (Decimal('7.77'), Decimal('0'), '7.77', '0', '7.77'),
    (Decimal('4.02'), Decimal('7.77'), '4.02', '7.77', '7.77'),
]


@pytest.mark.parametrize('amount,primary,expected_amount,expected_primary,effective', ALIASES)
@pytest.mark.parametrize('path', ['progress', 'edit'])
def test_missing_aliases_copy_recorded_synonyms_and_keep_known_differences(money_case, amount, primary, expected_amount, expected_primary, effective, path):
    c = money_case
    w = c.w
    oid, iid, payload = history(c)
    line = w.db.session.get(w.SalesOrderItem, iid)
    line.quantity = 1.15
    line.price = 3.5
    line.amount = amount
    line.tax_included_amount = primary
    w.db.session.get(w.SalesOrder, oid).total_amount = None if path == 'progress' else Decimal('9.99')
    w.db.session.commit()
    payload['items'][0].update(quantity='1.15', price='3.5')
    if path == 'progress':
        w.recalculate_sales_order(w.db.session.get(w.SalesOrder, oid), recalculate_amounts=False)
        w.db.session.commit()
    else:
        response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
        assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.SalesOrderItem, iid)
    order = w.db.session.get(w.SalesOrder, oid)
    assert (line.amount, line.tax_included_amount) == (Decimal(expected_amount), Decimal(expected_primary))
    assert order.total_amount == (Decimal(effective) if path == 'progress' else Decimal('9.99'))
    assert (line.quantity, line.price, line.tax_amount) == (1.15, 3.5, Decimal('.52'))
    if amount is not None:
        assert line.amount == amount
    if primary is not None:
        assert line.tax_included_amount == primary
    unchanged_inventory(c)


@pytest.mark.parametrize('amount,primary,total', [(Decimal('0'), Decimal('4.02'), '8.02'),
                                               (Decimal('7.77'), Decimal('0'), '11.77')])
def test_mixed_edit_total_matches_existing_primary_and_legacy_read_contract(money_case, amount, primary, total):
    c = money_case
    w = c.w
    oid, iid, payload = history(c, amount=amount)
    original = w.db.session.get(w.SalesOrderItem, iid)
    original.tax_included_amount = primary
    second = w.SalesOrderItem(sales_order_id=oid, material_id=c.ids['material'], quantity=1, price=2,
                              tax_rate=0, amount=2, tax_included_amount=2, untaxed_amount=2,
                              tax_amount=0, untaxed_price=2)
    w.db.session.add(second)
    w.db.session.commit()
    second_id = second.id
    payload['items'].append(dict(line_id=second_id, code='B-M', quantity='2', price='2', tax_rate='0'))
    response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    original = w.db.session.get(w.SalesOrderItem, iid)
    assert (original.amount, original.tax_included_amount) == (amount, primary)
    assert w.db.session.get(w.SalesOrder, oid).total_amount == Decimal(total)
    assert w.db.session.get(w.SalesOrderItem, second_id).amount == Decimal('4')
    unchanged_inventory(c)


@pytest.mark.parametrize('path', ['progress', 'edit'])
def test_missing_tax_fields_derive_from_recorded_amount_and_keep_header(money_case, path):
    c = money_case
    w = c.w
    oid, iid, payload = history(c, amount=Decimal('7.77'))
    line = w.db.session.get(w.SalesOrderItem, iid)
    line.quantity = 1.15
    line.price = 3.5
    line.tax_included_amount = line.untaxed_amount = line.tax_amount = None
    w.db.session.commit()
    payload['items'][0].update(quantity='1.15', price='3.5')
    if path == 'progress':
        w.recalculate_sales_order(w.db.session.get(w.SalesOrder, oid), recalculate_amounts=False)
        w.db.session.commit()
    else:
        response = document_post(c.client, f'/sales/{oid}/edit', json=payload)
        assert response.status_code == 200 and response.json['status'] == 'success', response.json
    w.db.session.expire_all()
    line = w.db.session.get(w.SalesOrderItem, iid)
    assert (line.amount, line.tax_included_amount, line.untaxed_amount, line.tax_amount) == (
        Decimal('7.77'), Decimal('7.77'), Decimal('6.88'), Decimal('.89'))
    assert (line.quantity, line.price) == (1.15, 3.5)
    assert w.db.session.get(w.SalesOrder, oid).total_amount == Decimal('9.99')
    unchanged_inventory(c)
