"""The product receipt detail and its downloadable list show the same business data."""
from io import BytesIO

from bs4 import BeautifulSoup
from openpyxl import load_workbook
import pytest

import app as w
from tests.test_web_document_idempotency import receipt_case
from tests.test_document_edit_conflicts import revision
from tests.test_product_receipt_sales_conversion import convert, product_sale_case


@pytest.fixture
def product_document(receipt_case):
    client, payload = receipt_case
    with w.app.app_context():
        customer = w.Customer(code='CAB-C', name='成套柜客户')
        w.db.session.add_all([customer, w.Material(code='CAB-B', name='第二台柜')])
        w.db.session.commit()
        payload.update(customer_id=customer.id, purpose='成套完工', remark='核对箱体')
    payload['items'] = [
        dict(code='RETRY', contract_no='FIRST', box_no='A01', quantity=2, price=10),
        dict(code='CAB-B', contract_no='SECOND', box_no='B02', quantity=1, price=3),
    ]
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 200, response.json
    return client, response.json['id'], payload['warehouse_id']


def test_product_header_summary_displays_registered_customer(product_document):
    client, oid, _ = product_document
    page = client.get(f'/in_order/{oid}')
    assert page.status_code == 200
    assert '成套柜客户' in BeautifulSoup(page.data, 'html.parser').select_one('.order-meta').get_text()


@pytest.mark.parametrize('filters,expected', [
    ({'contract_no': 'SECOND'}, ['CAB-B']),
    ({'search': 'CAB-B'}, ['CAB-B']),
    ({'sort': 'total_amount', 'order': 'asc'}, ['CAB-B', 'RETRY']),
])
def test_download_matches_visible_product_rows(product_document, filters, expected):
    client, _, warehouse = product_document
    query = dict(type='product_in', warehouse_id=warehouse, **filters)
    page = client.get('/in_order', query_string=query)
    assert page.status_code == 200
    html = BeautifulSoup(page.data, 'html.parser')
    assert [td.get_text(strip=True) for td in html.select('#inOrderTable td[data-column-key="material_code"]')] == expected
    link = html.select_one('a[title="导出当前筛选结果"]')
    response = client.get(link['href'])
    assert response.status_code == 200
    header, *rows = load_workbook(BytesIO(response.data), read_only=True).active.values
    assert [row[header.index('物料编码')] for row in rows] == expected


def test_empty_product_receipt_export_retains_header_columns(product_document):
    client, oid, warehouse = product_document
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        for item in list(order.items):
            w.db.session.delete(item)
        w.db.session.commit()
    response = client.get('/in_order/export', query_string=dict(type='product_in', warehouse_id=warehouse))
    assert response.status_code == 200
    header, row = load_workbook(BytesIO(response.data), read_only=True).active.values
    record = dict(zip(header, row))
    assert [record[key] for key in ('业务类型', '用途', '客户', '仓库', '物料编码', '状态', '备注')] == [
        '产品入库', '成套完工', '成套柜客户', '重试仓', None, '未审核/待完成', '核对箱体']


def test_corrections_keep_sales_quantities_and_protect_linked_boxes(product_sale_case):
    client, oid, _ = product_sale_case
    path = f'/in_order/{oid}'
    pushed = convert(client, oid)
    assert pushed.status_code == 200
    with w.app.app_context():
        source = w.db.session.get(w.InOrder, oid)
        line = next(i for i in source.items if i.box_no == '002-B')
        line_id, price = line.id, line.price
        initial = w.Material.query.one().stock

    def correct(**changes):
        return client.post(path + '/update_completed', json=dict(reason='复核盘点纸', **changes),
                           headers={'X-WMS-Document-Revision': revision(client, path)})

    for quantity in (4, 1):
        response = correct(items=[dict(id=line_id, quantity=quantity)])
        assert response.status_code == 200, response.json
        notice = BeautifulSoup(client.get(path).data, 'html.parser').select_one('[data-sales-quantity-difference]')
        assert notice and '002-B' in notice.get_text() and '原转单 2.0' in notice.get_text()
        with w.app.app_context():
            row = w.db.session.get(w.InOrderItem, line_id)
            assert (row.quantity, row.price, row.amount) == (quantity, price, quantity * price)
            assert w.Material.query.one().stock == initial + quantity - 2
            assert [i.quantity for i in w.OutOrder.query.one().items] == [1, 2]
    assert correct(deleted_items=[line_id]).status_code == 409
    assert correct(items=[dict(is_new=True, code='RETRY', box_no='003-C', quantity=3, price=5)]).status_code == 200
    with w.app.app_context():
        added_id = w.InOrderItem.query.filter_by(box_no='003-C').one().id
        assert w.Material.query.one().stock == initial + 2
    assert correct(deleted_items=[added_id]).status_code == 200
    with w.app.app_context():
        assert w.Material.query.one().stock == initial - 1
        assert w.db.session.get(w.InOrderItem, line_id).box_no == '002-B'
        assert [i.quantity for i in w.OutOrder.query.one().items] == [1, 2]
        assert w.DocumentPushLine.query.filter_by(status='active').count() == 2
    assert '销售出库' in response.json['msg']


def test_linked_row_cannot_be_deleted_from_completed_receipt(product_sale_case):
    client, oid, _ = product_sale_case
    assert convert(client, oid).status_code == 200
    path = f'/in_order/{oid}'
    with w.app.app_context():
        line_id = w.db.session.get(w.InOrder, oid).items[0].id
        before = w.Material.query.one().stock
    result = client.post(path + '/update_completed', json={'deleted_items': [line_id], 'reason': '多录了一箱'},
                         headers={'X-WMS-Document-Revision': revision(client, path)})
    assert result.status_code == 409
    with w.app.app_context():
        assert w.Material.query.one().stock == before
        assert w.db.session.get(w.InOrderItem, line_id)


def test_completed_product_receipt_offers_manual_correction(product_sale_case):
    client, oid, _ = product_sale_case
    assert convert(client, oid).status_code == 200
    page = BeautifulSoup(client.get(f'/in_order/{oid}').data, 'html.parser')
    form = page.select_one('#productCorrectionForm')
    assert form and form.select_one('[name=reason][required]')
    assert '核对' in form.get_text() and '销售出库' in form.get_text()
    assert len(form.select('option[data-linked="true"]')) == 2
