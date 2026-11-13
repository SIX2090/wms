"""Actual Excel import and persisted tax values; owned private-memory fixture only."""
from decimal import Decimal
from io import BytesIO

import pytest

from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


@pytest.mark.parametrize('tax_value,has_column,expected_rate', [
    (0, True, 0), ('0', True, 0), ('0.00', True, 0),
    (.13, True, .13), ('0.13', True, .13), (.06, True, .06),
    (None, True, .13), ('', True, .13), (' ', True, .13),
    (0, False, .13), (-.13, True, .13), ('-0.13', True, .13),
    ('bad', True, .13), ('NaN', True, .13), ('Infinity', True, .13),
])
def test_sales_import_preserves_zero_tax_and_existing_fallbacks(money_case, tax_value, has_column, expected_rate):
    from openpyxl import Workbook
    c = money_case
    w = c.w
    workbook = Workbook()
    sheet = workbook.active
    columns = ['销售订单号', '客户名称', '发货仓库', '物料编码', '数量', '含税单价']
    row = ['SO-SYN-ZERO-TAX', '合成金额客户', c.warehouse, 'B-M', 1.15, 3.5]
    if has_column:
        columns.append('税率')
        row.append(tax_value)
    sheet.append(columns)
    sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    response = c.client.post('/sales/import', data={'file': (stream, 'synthetic-zero-tax.xlsx')})
    assert response.status_code == 200, response.json
    assert response.json['count'] == response.json['item_count'] == 1, response.json
    w.db.session.remove()
    order = w.SalesOrder.query.filter_by(order_no='SO-SYN-ZERO-TAX').one()
    assert (order.status, order.shipment_status, order.total_amount) == ('draft', 'pending', Decimal('4.03'))
    assert len(order.items) == 1
    line = order.items[0]
    assert line.tax_rate == expected_rate
    assert (line.quantity, line.price, line.amount, line.tax_included_amount) == (
        1.15, 3.5, Decimal('4.03'), Decimal('4.03'))
    expected_untaxed, expected_tax = {0: ('4.03', '0'), .13: ('3.57', '.46'), .06: ('3.80', '.23')}[expected_rate]
    assert (line.untaxed_amount, line.tax_amount) == (Decimal(expected_untaxed), Decimal(expected_tax))
    assert (order.untaxed_amount, order.tax_amount) == (Decimal(expected_untaxed), Decimal(expected_tax))
    assert w.OutOrder.query.count() == 0
    unchanged_inventory(c)
