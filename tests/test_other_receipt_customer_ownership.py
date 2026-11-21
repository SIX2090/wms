"""Other receipt ownership must survive entry, editing and posting."""
from datetime import date
import json
import re

from bs4 import BeautifulSoup
import pytest

import app as w
from tests.document_revision_client import document_post
from tests.test_web_document_idempotency import receipt_case


@pytest.mark.parametrize('as_form', [False, True])
@pytest.mark.parametrize('supplied', [False, True])
def test_other_receipt_customer_is_required_only_for_supplied_lines(receipt_case, as_form, supplied):
    client, payload = receipt_case
    items = [dict(code='RETRY', quantity=2, price=1, is_customer_supplied=supplied)]
    data = dict(business_type='其他入库', warehouse_id=payload['warehouse_id'], date=date.today().isoformat())
    if as_form:
        result = client.post('/in_order/add', data=dict(data, items_json=json.dumps(items)))
    else:
        result = client.post('/in_order/add', json=dict(data, items=items))
    assert result.status_code == (400 if supplied else 200), result.json
    if supplied:
        assert '客户' in result.json['msg']
    with w.app.app_context():
        assert w.InOrder.query.count() == (0 if supplied else 1)
        assert w.InOrderItem.query.count() == (0 if supplied else 1)
        assert w.Material.query.one().stock == 0
    if not supplied:
        oid = result.json['id']
        assert client.post(f'/in_order/{oid}/complete?force=1').json['status'] == 'success'
        with w.app.app_context():
            assert w.Material.query.one().stock == 2
        assert client.post(f'/in_order/{oid}/revert').json['status'] == 'success'
        with w.app.app_context():
            assert w.Material.query.one().stock == 0


def test_supplied_draft_keeps_customer_on_header_edit_and_rechecks_before_posting(receipt_case):
    client, payload = receipt_case
    with w.app.app_context():
        customer = w.Customer(code='OWNER', name='客供方')
        w.db.session.add(customer)
        w.db.session.commit()
        customer_id = customer.id
    payload.update(business_type='其他入库', customer_id=customer_id)
    payload['items'][0]['is_customer_supplied'] = True
    oid = client.post('/in_order/add', json=payload).json['id']
    page = client.get('/other_in_order/add', query_string={'order_id': oid})
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert json.loads(re.search(r'const editItems = (.*?);', html)[1])[0]['is_customer_supplied'] is True
    assert '编辑其他入库单' in BeautifulSoup(html, 'html.parser').title.get_text()
    assert '有客供料时必填' in BeautifulSoup(html, 'html.parser').get_text()
    path = f'/in_order/{oid}'
    header = dict(warehouse_id=payload['warehouse_id'], date=date.today().isoformat(), customer_id='')
    assert document_post(client, path + '/update', json=header).status_code == 400
    assert document_post(client, path + '/update', json=dict(header, customer_id=customer_id, business_type='采购入库')).status_code == 400
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, oid)
        assert order.customer_id == customer_id and order.business_type == '其他入库'
        order.customer_id = None
        w.db.session.commit()
    assert client.post(path + '/complete?force=1').status_code == 400
    batch = client.post('/in_order/batch_complete', json=dict(ids=[oid]))
    assert batch.json['status'] == 'error' and batch.json['completed'] == 0
    with w.app.app_context():
        assert w.Material.query.one().stock == 0 and w.db.session.get(w.InOrder, oid).status == 'pending'
