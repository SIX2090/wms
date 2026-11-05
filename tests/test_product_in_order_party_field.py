"""Product receipts do not ask an assembly business to choose one supplier."""
import re
from datetime import date

import pytest
import app as w
from tests.test_web_document_idempotency import receipt_case
from tests.test_document_edit_conflicts import revision


def test_new_product_receipt_has_no_party_picker_and_saves(receipt_case):
    client, payload = receipt_case
    response = client.get('/in_order/add?type=product')
    assert response.status_code == 200
    assert 'id="supplierSearch"' not in response.text
    field = re.search(r'<input\b[^>]*name="supplier_id"[^>]*>', response.text)
    assert field and 'type="hidden"' in field.group() and 'value=""' in field.group()
    saved = client.post('/in_order/add', json=payload)
    assert saved.status_code == 200, saved.json
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, saved.json['id'])
        assert order.business_type == '产品入库' and order.supplier_id is None
        assert order.items[0].quantity == 1
        assert w.Material.query.one().stock == 0


@pytest.mark.parametrize('path,label', [
    ('/in_order/add', '供应商'),
    ('/other_in_order/add', '客户'),
    ('/in_order/add?type=sales_return', '退货客户'),
])
def test_other_receipt_party_pickers_remain(receipt_case, path, label):
    client, _ = receipt_case
    response = client.get(path)
    assert response.status_code == 200
    assert 'id="supplierSearch"' in response.text
    assert f'搜索{label}...' in response.text
    assert 'const supplierRequired = true;' in response.text


def test_product_edit_keeps_historical_supplier_and_items(receipt_case):
    client, payload = receipt_case
    with w.app.app_context():
        supplier = w.Supplier(code='ASSEMBLY-OLD', name='历史来源单位')
        w.db.session.add(supplier)
        w.db.session.commit()
        sid = supplier.id
    saved = client.post('/in_order/add', json=dict(payload, supplier_id=sid))
    assert saved.status_code == 200, saved.json
    oid = saved.json['id']
    path = f'/in_order/add?order_id={oid}'
    page = client.get(path)
    assert page.status_code == 200 and 'id="supplierSearch"' not in page.text
    field = re.search(r'<input\b[^>]*name="supplier_id"[^>]*>', page.text)
    assert field and 'type="hidden"' in field.group() and f'value="{sid}"' in field.group()
    edited = dict(payload, order_id=oid, supplier_id=sid, remark='正常编辑')
    result = client.post('/in_order/add', json=edited,
                         headers={'X-WMS-Document-Revision': revision(client, path)})
    assert result.status_code == 200, result.json
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        assert order.supplier_id == sid and order.remark == '正常编辑'
        assert len(order.items) == 1 and order.items[0].quantity == 1
        assert w.Material.query.one().stock == 0


def test_product_detail_hides_party_and_preserves_header_save(receipt_case):
    client, payload = receipt_case
    saved = client.post('/in_order/add', json=payload)
    assert saved.status_code == 200, saved.json
    oid = saved.json['id']
    path = f'/in_order/{oid}'
    page = client.get(path)
    assert page.status_code == 200
    assert '供应商/生产来源</span>' not in page.text
    field = re.search(r'<div\b[^>]*id="editPartyField"[^>]*>', page.text)
    assert field and 'hidden' in field.group()
    result = client.post(f'/in_order/{oid}/update', json={
        'date': date.today().isoformat(), 'business_type': '产品入库',
        'supplier_id': '', 'warehouse_id': payload['warehouse_id'], 'remark': '修改表头',
    }, headers={'X-WMS-Document-Revision': revision(client, path)})
    assert result.status_code == 200, result.json
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        assert order.supplier_id is None and order.remark == '修改表头'
        assert len(order.items) == 1 and order.items[0].quantity == 1
