"""Real sales ORM/routes: only the existing owned, private-memory profile may run."""
from datetime import date
from decimal import Decimal

import pytest

from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory

LINE_FIELDS = ('amount', 'tax_included_amount', 'untaxed_amount', 'tax_amount', 'untaxed_price')
HEADER_FIELDS = ('total_amount', 'untaxed_amount', 'tax_amount')


def history(case, amount, shipped=0, total=None):
    w = case.w
    order = w.SalesOrder(order_no='S-SALES-HISTORY', date=date.today(), status='confirmed',
                         customer_id=case.customer, warehouse=case.warehouse, warehouse_id=case.wh1,
                         total_amount=amount if total is None else total,
                         untaxed_amount=Decimal('3.50'), tax_amount=Decimal('.52'))
    w.db.session.add(order)
    w.db.session.flush()
    line = w.SalesOrderItem(sales_order_id=order.id, material_id=case.ids['material'],
                            quantity=1.15, price=3.5, shipped_quantity=shipped, tax_rate=.13,
                            amount=amount, tax_included_amount=amount, untaxed_amount=Decimal('3.50'),
                            tax_amount=Decimal('.52'), untaxed_price=3.0435)
    w.db.session.add(line)
    w.db.session.commit()
    return order.id, line.id


def financials(w, oid, iid):
    w.db.session.expire_all()
    order = w.db.session.get(w.SalesOrder, oid)
    line = w.db.session.get(w.SalesOrderItem, iid)
    return tuple(getattr(order, key) for key in HEADER_FIELDS), tuple(getattr(line, key) for key in LINE_FIELDS)


@pytest.mark.parametrize('amount', [Decimal('0'), Decimal('4.02'), Decimal('7.77')])
def test_complete_and_revert_routes_keep_historical_financials(money_case, amount):
    from tests.document_revision_client import document_post
    c = money_case
    w = c.w
    oid, iid = history(c, amount)
    outbound = w.OutOrder(order_no='S-SALES-HISTORY-OUT', date=date.today(), status='pending',
                           business_type='销售出库', warehouse=c.warehouse,
                           customer='合成金额客户', source_sales_order_id=oid,
                           purpose='来源销售订单 S-SALES-HISTORY', operator_id=c.ids['user'])
    w.db.session.add(outbound)
    w.db.session.flush()
    w.db.session.add(w.OutOrderItem(out_order_id=outbound.id, source_sales_order_item_id=iid,
                                    material_id=c.ids['material'], quantity=.5, price=3.5, amount=1.75))
    w.db.session.commit()
    out_id = outbound.id
    before = financials(w, oid, iid)
    response = document_post(c.client, f'/out_order/{out_id}/complete', json={})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert financials(w, oid, iid) == before
    order = w.db.session.get(w.SalesOrder, oid)
    assert (order.status, order.shipment_status, order.shipped_amount) == ('confirmed', 'partial', Decimal('1.75'))
    assert order.remaining_amount == amount - Decimal('1.75')
    assert w.db.session.get(w.Material, c.ids['material']).stock == 9.5
    response = document_post(c.client, f'/out_order/{out_id}/revert', json={})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert financials(w, oid, iid) == before
    order = w.db.session.get(w.SalesOrder, oid)
    assert (order.status, order.shipment_status, order.shipped_amount, order.remaining_amount) == (
        'confirmed', 'pending', Decimal('0'), amount)
    assert w.db.session.get(w.Material, c.ids['material']).stock == 10
    assert w.LocationInventory.query.order_by(w.LocationInventory.warehouse_id).with_entities(
        w.LocationInventory.warehouse_id, w.LocationInventory.quantity).all() == [(c.wh1, 5), (c.wh2, 5)]
    assert w.StockTransaction.query.count() == 4


def test_completed_downpush_keeps_existing_header_and_line_financials(money_case):
    c = money_case
    w = c.w
    oid, iid = history(c, Decimal('4.02'), shipped=1.15, total=Decimal('7.77'))
    before = financials(w, oid, iid)
    order = w.db.session.get(w.SalesOrder, oid)
    assert w.build_sales_outbound_draft(order) == (None, 'completed')
    w.db.session.commit()
    assert financials(w, oid, iid) == before
    order = w.db.session.get(w.SalesOrder, oid)
    assert (order.status, order.shipment_status, order.shipped_amount, order.remaining_amount) == (
        'closed', 'shipped', Decimal('4.03'), Decimal('3.74'))
    assert w.OutOrder.query.count() == 0
    unchanged_inventory(c)


def test_progress_refresh_fills_only_missing_fields_and_preserves_zero(money_case):
    c = money_case
    w = c.w
    oid, iid = history(c, Decimal('7.77'), total=Decimal('9.99'))
    order = w.db.session.get(w.SalesOrder, oid)
    line = w.db.session.get(w.SalesOrderItem, iid)
    line.amount = line.untaxed_price = None
    line.untaxed_amount = Decimal('0')
    order.tax_amount = None
    w.db.session.commit()
    w.recalculate_sales_order(order, recalculate_amounts=False)
    w.db.session.commit()
    w.db.session.expire_all()
    line = w.db.session.get(w.SalesOrderItem, iid)
    order = w.db.session.get(w.SalesOrder, oid)
    assert (line.amount, line.tax_included_amount, line.untaxed_amount, line.tax_amount) == (
        Decimal('7.77'), Decimal('7.77'), Decimal('0'), Decimal('.52'))
    # Persisted primary 7.77 must supply the missing compatibility amount.
    assert (line.quantity, line.price) == (1.15, 3.5)
    assert line.untaxed_price == 3.0973
    assert (order.total_amount, order.untaxed_amount, order.tax_amount, order.remaining_amount) == (
        Decimal('9.99'), Decimal('3.50'), Decimal('.52'), Decimal('9.99'))
    unchanged_inventory(c)


def test_missing_header_uses_preserved_tax_included_lines(money_case):
    c = money_case
    w = c.w
    oid, iid = history(c, Decimal('7.77'))
    order = w.db.session.get(w.SalesOrder, oid)
    order.total_amount = order.untaxed_amount = order.tax_amount = None
    w.db.session.commit()
    w.recalculate_sales_order(order, recalculate_amounts=False)
    w.db.session.commit()
    assert financials(w, oid, iid)[0] == (Decimal('7.77'), Decimal('3.50'), Decimal('.52'))
    unchanged_inventory(c)


@pytest.mark.parametrize('tax_rate,untaxed,tax', [(0, '4.03', '0'), (.13, '3.57', '.46')])
def test_recalculate_sales_order(money_case, tax_rate, untaxed, tax):
    c = money_case
    w = c.w
    oid, iid = history(c, Decimal('7.77'))
    order = w.db.session.get(w.SalesOrder, oid)
    line = w.db.session.get(w.SalesOrderItem, iid)
    line.tax_rate = tax_rate
    w.recalculate_sales_order(order)
    w.db.session.commit()
    w.db.session.expire_all()
    assert financials(w, oid, iid)[0] == (Decimal('4.03'), Decimal(untaxed), Decimal(tax))
    assert w.db.session.get(w.SalesOrderItem, iid).amount == Decimal('4.03')
    unchanged_inventory(c)
