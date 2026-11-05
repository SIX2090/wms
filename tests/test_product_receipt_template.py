"""Product receipt header, cabinet identity and the supplied 20-line form."""
from copy import deepcopy
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

import app as w
from tests.test_web_document_idempotency import receipt_case
from tests.test_document_edit_conflicts import revision


def _save(client, payload):
    with w.app.app_context():
        customer = w.Customer(code='PR-C', name='产品测试客户')
        material = w.Material.query.one()
        material.name, material.spec = '低压配电柜', 'GGD-001'
        w.db.session.add(customer)
        w.db.session.commit()
        customer_id = customer.id
    data = deepcopy(payload)
    data.update(customer_id=customer_id, contract_no='HT-2026-产品', project_name='产品测试工程')
    data['items'][0].update(box_no='001-A', quantity=2, price=12.34, remark='行备注')
    result = client.post('/in_order/add', json=data)
    assert result.status_code == 200, result.json
    return result.json['id'], data


def test_product_header_box_roundtrip_copy_and_stock(receipt_case):
    client, payload = receipt_case
    oid, data = _save(client, payload)
    path = f'/in_order/add?order_id={oid}'
    page = client.get(path)
    assert page.status_code == 200
    assert '客户名称' in page.text and 'name="customer_id"' in page.text
    assert 'name="project_name"' in page.text and '箱体编号' in page.text
    assert '001-A' in page.text
    data.update(order_id=oid, project_name='修改工程')
    data['items'][0]['box_no'] = '002-B'
    result = client.post('/in_order/add', json=data,
                         headers={'X-WMS-Document-Revision': revision(client, path)})
    assert result.status_code == 200, result.json
    detail = client.get(f'/in_order/{oid}')
    assert '产品测试客户' in detail.text and '修改工程' in detail.text and '002-B' in detail.text
    copied = client.post(f'/in_order/{oid}/copy',
                         headers={'X-WMS-Document-Revision': revision(client, f'/in_order/{oid}')})
    assert copied.status_code == 200, copied.json
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, copied.json['id'])
        assert order.customer.name == '产品测试客户'
        assert order.project_name == '修改工程' and order.items[0].box_no == '002-B'
        assert w.Material.query.one().stock == 0
        assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('value', [123, ['cabinet'], 'x' * 101])
def test_box_number_rejects_wrong_type_or_length_atomically(receipt_case, value):
    client, payload = receipt_case
    payload['items'][0]['box_no'] = value
    result = client.post('/in_order/add', json=payload)
    assert result.status_code == 400, result.json
    assert '箱体编号' in result.json['msg']
    with w.app.app_context():
        assert w.InOrder.query.count() == 0 and w.Material.query.one().stock == 0


def test_build_product_receipt_excel(receipt_case):
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    page = client.get(f'/in_order/{oid}/print')
    assert page.status_code == 200
    for text in ('广东惠电科技发展有限公司', '产品入库单', '设备名称', '型号规格',
                 '箱体编号', 'HT-2026-产品', '产品测试客户', '产品测试工程', '001-A', '低压配电柜', 'GGD-001'):
        assert text in page.text
    assert page.text.count('class="product-detail-row"') == 20
    result = client.get(f'/in_order/{oid}/print_excel')
    assert result.status_code == 200
    wb = load_workbook(BytesIO(result.data), data_only=False)
    ws = wb.active
    assert ws['G5'].value == 'NO：HT-2026-产品'
    assert ws['B8'].value == '001-A' and ws['C8'].value == '低压配电柜'
    assert ws['D8'].value == 'GGD-001' and ws['F8'].value == 2
    assert ws['G8'].value == 12.34 and ws['H8'].value == 24.68
    assert ws['H28'].value == 24.68
    assert '贰拾肆元陆角捌分' in ws['C29'].value
    assert ws.print_area and ws.page_setup.orientation == 'portrait'
    assert ws.max_row >= 31
    wb.close()


def test_product_receipt_pages(receipt_case):
    from services.product_receipt_print import product_receipt_pages, build_product_receipt_excel
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        # Historical warehouse text does not turn descriptive printing into a stock lookup.
        order.warehouse = '历史仓库编码'
        pages = product_receipt_pages(order)
        assert len(pages) == 1 and len(pages[0].rows) == 20
        assert pages[0].rows[0].box_no == '001-A' and pages[0].rows[-1].box_no == ''
        assert pages[0].quantity == 2 and pages[0].header.total_amount == 24.68
        assert build_product_receipt_excel(order).getvalue().startswith(b'PK')
        assert order.status == 'pending' and w.Material.query.one().stock == 0
        assert w.StockTransaction.query.count() == 0


def test_product_print_all_rows_paginates_without_dropping_final_row(receipt_case):
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        mid = order.items[0].material_id
        for index in range(2, 22):
            w.db.session.add(w.InOrderItem(in_order_id=oid, material_id=mid, quantity=1,
                                           price=1, amount=1, box_no=f'BOX-{index}'))
        order.total_amount = 44.68
        w.db.session.commit()
    html = client.get(f'/in_order/{oid}/print').text
    assert html.count('class="product-detail-row"') == 40
    assert 'BOX-21' in html and '第 2 / 2 页' in html
    result = client.get(f'/in_order/{oid}/print_excel')
    wb = load_workbook(BytesIO(result.data))
    assert len(wb.worksheets) == 2
    assert wb.worksheets[1]['B8'].value == 'BOX-21'
    assert sum(Decimal(str(sheet['H28'].value)) for sheet in wb.worksheets) == Decimal('44.68')
    wb.close()


def test_product_print_keeps_text_literal(receipt_case):
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        order.items[0].box_no = '=001-A'
        order.items[0].remark = '=请核对'
        w.db.session.commit()
    result = client.get(f'/in_order/{oid}/print_excel')
    wb = load_workbook(BytesIO(result.data))
    assert wb.active['B8'].value == '=001-A' and wb.active['B8'].data_type == 's'
    assert wb.active['I8'].value == '=请核对' and wb.active['I8'].data_type == 's'
    wb.close()


@pytest.mark.parametrize('amount,expected', [
    ('0', '零元整'), ('10.01', '壹拾元零壹分'), ('10001.00', '壹万零壹元整'),
    ('100000001.05', '壹亿零壹元零伍分'), ('-12.30', '负壹拾贰元叁角'),
])
def test_amount_in_words(amount, expected):
    from services.product_receipt_print import amount_in_words
    assert amount_in_words(amount) == expected


def test_box_number_distinguishes_duplicate_receipts(receipt_case):
    from services.document_duplicate import documents_match_for_duplicate_warning
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        from types import SimpleNamespace
        other = SimpleNamespace(**{column.key:getattr(order, column.key) for column in w.InOrder.__table__.columns})
        other.customer = order.customer
        other.items = [SimpleNamespace(**{column.key:getattr(order.items[0], column.key) for column in w.InOrderItem.__table__.columns})]
        assert documents_match_for_duplicate_warning(order, other)
        other.items[0].box_no = 'DIFFERENT'
        assert not documents_match_for_duplicate_warning(order, other)


def test_inline_box_edit_preserves_remark_and_rejects_stale_revision(receipt_case):
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    path = f'/in_order/{oid}'
    token = revision(client, path)
    with w.app.app_context():
        item_id = w.db.session.get(w.InOrder, oid).items[0].id
    result = client.post('/in_order/item/update', data={'id':item_id, 'box_no':'0003-C'},
                         headers={'X-WMS-Document-Revision':token})
    assert result.status_code == 200, result.json
    assert client.post('/in_order/item/update', data={'id':item_id, 'box_no':'old'},
                       headers={'X-WMS-Document-Revision':token}).status_code == 409
    with w.app.app_context():
        item = w.db.session.get(w.InOrderItem, item_id)
        assert item.box_no == '0003-C' and item.remark == '行备注'
        assert item.quantity == 2 and item.price == 12.34


def test_product_detail_export_carries_header_and_box(receipt_case):
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    result = client.get(f'/in_order/{oid}/export')
    wb = load_workbook(BytesIO(result.data))
    row = dict(zip(next(wb.active.values), list(wb.active.values)[1]))
    assert row['箱体编号'] == '001-A' and row['客户名称'] == '产品测试客户'
    assert row['工程名称'] == '产品测试工程'
    wb.close()


def test_schema_upgrade_adds_nullable_box_without_rewriting_history(receipt_case, tmp_path):
    import sqlite3
    from schema_upgrade import plan_schema_upgrade
    client, payload = receipt_case
    oid, _ = _save(client, payload)
    with w.app.app_context():
        raw = w.db.engine.raw_connection()
        target = sqlite3.connect(tmp_path/'legacy.db')
        raw.driver_connection.backup(target)
        raw.close()
    try:
        target.execute('ALTER TABLE in_order_item DROP COLUMN box_no')
        target.commit()
        before = target.execute('SELECT in_order_id, quantity, amount, remark FROM in_order_item').fetchall()
        plan = plan_schema_upgrade(target, w.db.metadata)
        assert not plan['blocked']
        box_ddl = [statement for statement in plan['statements'] if '"box_no"' in statement]
        assert len(box_ddl) == 1 and 'ADD COLUMN' in box_ddl[0]
        target.execute(box_ddl[0])
        target.commit()
        assert target.execute('SELECT in_order_id, quantity, amount, remark FROM in_order_item').fetchall() == before
        assert target.execute('SELECT box_no FROM in_order_item').fetchone() == (None,)
        repeated = plan_schema_upgrade(target, w.db.metadata)
        assert repeated['statements'] == [] and repeated['blocked'] == []
    finally:
        target.close()
