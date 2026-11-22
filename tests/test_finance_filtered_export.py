"""The visible export link on each stock list carries its current filters."""
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from openpyxl import load_workbook
import pytest

import app as w
from tests.test_document_print_flow import print_case
from tests.test_purchase_order_read_permissions import sign_in


@pytest.mark.parametrize('kind', ['in_order', 'out_order'])
def test_finance_filtered_export(print_case, kind):
    client, docs, _ = print_case
    sign_in(client, 'finance')
    model = w.InOrder if kind == 'in_order' else w.OutOrder
    with w.app.app_context():
        order = w.db.session.get(model, docs[kind])
        number = order.order_no
        other = model(order_no='OTHER-WH-ORDER', warehouse='打印乙仓', date=order.date,
                      operator_id=1, business_type=order.business_type, status=order.status)
        w.db.session.add(other)
        w.db.session.flush()
        item_model = w.InOrderItem if kind == 'in_order' else w.OutOrderItem
        w.db.session.add(item_model(**{kind + '_id': other.id}, material_id=1, quantity=3,
                                    price=2, amount=6))
        w.db.session.commit()
    for wh, included, excluded in [(1, number, 'OTHER-WH-ORDER'), (2, 'OTHER-WH-ORDER', number)]:
        page = client.get('/' + kind, query_string={'warehouse_id': wh})
        assert page.status_code == 200
        dom = BeautifulSoup(page.data, 'html.parser')
        link = dom.select_one(f'a[href^="/{kind}/export?"]')
        assert link and parse_qs(urlsplit(link['href']).query)['warehouse_id'] == [str(wh)]
        assert included in dom.table.get_text() and excluded not in dom.table.get_text()
        assert not dom.select('[data-document-list-action$="batch-delete"], [data-document-list-action$="batch-complete"]')
        export = client.get(link['href'])
        assert export.status_code == 200
        workbook = load_workbook(BytesIO(export.data), read_only=True)
        try:
            cells = {str(cell) for row in workbook.active.values for cell in row}
            assert included in cells and excluded not in cells
        finally:
            workbook.close()
