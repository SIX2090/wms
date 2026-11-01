"""BUG-2026-11-01-025: receipt displays use facts; selection uses reservations."""
from datetime import date
from html import unescape
from io import BytesIO
import re

import pytest
from openpyxl import load_workbook
import app as wms
from app import db
from tests.test_document_create_number_conflicts import case  # noqa: F401


@pytest.fixture
def purchase_case(case, monkeypatch, tmp_path):
    clients, ids = case
    # Excel built-in template generation must stay outside the repository.
    monkeypatch.setattr(wms.app, 'static_folder', str(tmp_path))
    with wms.app.app_context():
        supplier = wms.Supplier(code='DISPLAY-S', name='显示口径供应商')
        db.session.add(supplier)
        db.session.flush()
        order = wms.PurchaseOrder(order_no='PO-DISPLAY', date=date.today(),
                                  supplier_id=supplier.id, status='partial')
        db.session.add(order)
        db.session.flush()
        item = wms.PurchaseOrderItem(purchase_order_id=order.id, material_id=ids['mats'][0],
                                     quantity=10, received_quantity=8, price=2, amount=20)
        db.session.add(item)
        db.session.flush()
        for index, (quantity, status) in enumerate([(4, 'completed'), (4, 'pending')]):
            receipt = wms.InOrder(order_no='IN-DISPLAY-'+str(index), date=date.today(),
                                  supplier_id=supplier.id, business_type='采购入库',
                                  warehouse=ids['names'][0], status=status,
                                  source_purchase_order_id=order.id)
            db.session.add(receipt)
            db.session.flush()
            db.session.add(wms.InOrderItem(in_order_id=receipt.id, material_id=ids['mats'][0],
                                           source_purchase_order_item_id=item.id,
                                           quantity=quantity, price=2, amount=quantity*2))
        db.session.commit()
        ids = dict(ids, order=order.id, item=item.id)
    return clients[0], ids


def cell_text(value):
    return unescape(re.sub(r'<[^>]+>', '', value)).strip()


@pytest.mark.parametrize('draft_status,expected', [('pending', 4), ('completed', 8)])
@pytest.mark.parametrize('output', ['html', 'export', 'print_excel'])
def test_print_and_export_received_quantities_do_not_include_drafts(purchase_case, draft_status, expected, output):
    client, ids = purchase_case
    with wms.app.app_context():
        wms.InOrder.query.filter_by(order_no='IN-DISPLAY-1').one().status = draft_status
        db.session.commit()
    urls = dict(html=f'/purchase_order/{ids["order"]}/print',
                export='/purchase_order/export', print_excel=f'/purchase_order/{ids["order"]}/print_excel')
    response = client.get(urls[output])
    assert response.status_code == 200
    if output == 'html':
        html = response.get_data(as_text=True)
        table = next(t for t in re.findall(r'<table\b[\s\S]*?</table>', html)
                     if '已入库' in t and '物料编码' in t)
        headers = [cell_text(t) for t in re.findall(r'<th\b[^>]*>([\s\S]*?)</th>', table)]
        row = next(r for r in re.findall(r'<tr\b[\s\S]*?</tr>', table) if 'DC-M1' in r)
        cells = [cell_text(t) for t in re.findall(r'<td\b[^>]*>([\s\S]*?)</td>', row)]
        result = dict(zip(headers, cells))
        assert float(result['已入库']) == expected
        assert float(result['未入库']) == 10-expected
    else:
        workbook = load_workbook(BytesIO(response.data), data_only=True)
        rows = list(workbook.active.values)
        headers = next(r for r in rows if '已入库' in r)
        row = next(r for r in rows if 'DC-M1' in r)
        assert row[headers.index('已入库')] == expected
        if output == 'export':
            assert row[headers.index('未入库')] == 10-expected
    with wms.app.app_context():
        assert db.session.get(wms.PurchaseOrderItem, ids['item']).received_quantity == 8
        assert wms.Material.query.filter_by(code='DC-M1').one().stock == 30


def test_selection_labels_describe_pushed_counter_and_remaining_capacity(purchase_case):
    client, _ = purchase_case
    html = client.get('/in_order/add').get_data(as_text=True)
    modal = html[html.index('function showPurchaseOrderSelectModal('):html.index('function loadPurchaseOrderSelectable(')]
    assert re.search(r'<th\b[^>]*>已下推</th>', modal)
    assert re.search(r'<th\b[^>]*>未下推</th>', modal)
    assert not re.search(r'<th\b[^>]*>已入库</th>', modal)


def test_detail_still_distinguishes_completed_pending_and_unpushed(purchase_case):
    client, ids = purchase_case
    html = client.get(f'/purchase_order/{ids["order"]}').get_data(as_text=True)
    for field, value in [('pushed-quantity', 8), ('completed-quantity', 4),
                         ('pending-receive-quantity', 4), ('remaining-to-push', 2)]:
        assert f'data-{field}="{value:.2f}"' in html


def test_excel_print_custom_template_retains_other_item_attributes(purchase_case, monkeypatch):
    from doc_print_excel import render_doc_excel_print
    import doc_print_excel
    _, ids = purchase_case
    captured = {}
    def fill(path, order, **kwargs):
        captured.update(kwargs)
        return BytesIO(b'fixture')
    monkeypatch.setattr(doc_print_excel, '_template_path_or_builtin', lambda *args: 'fixture.xlsx')
    monkeypatch.setattr('print_fill.build_filled_print_excel', fill)
    with wms.app.app_context():
        order = db.session.get(wms.PurchaseOrder, ids['order'])
        render_doc_excel_print('purchase_order', order)
        row = list(captured['items'])[0]
        assert row.received_quantity == 4
        assert row.material.code == 'DC-M1'
        assert row.purchase_order.order_no == order.order_no
        assert row.quantity == 10 and row.price == 2
        assert order.items[0].received_quantity == 8
