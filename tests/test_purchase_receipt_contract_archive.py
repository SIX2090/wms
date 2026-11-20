import pytest

import app as w
from tests.document_revision_client import document_post
from tests.test_web_document_idempotency import receipt_case


@pytest.fixture
def purchase(receipt_case):
    client, payload = receipt_case
    with w.app.app_context():
        w.db.session.add(w.Contract(contract_no='HD261103', project_name='原工程'))
        w.db.session.commit()
    payload['business_type'] = '采购入库'
    return client, payload


@pytest.mark.parametrize('number', ['HD261103', '1103'])
def test_resolve_purchase_receipt_contract(purchase, number):
    client, payload = purchase
    item = payload['items'][0]
    payload['items'] = [dict(item, contract_no=number),
                        dict(item, contract_no=' HD261120 ', project_name=' 深圳第二园区 '),
                        dict(item, contract_no='HD261120'), item]
    headers = {'X-Idempotency-Key': 'save-contract'}
    for _ in range(2):
        result = client.post('/in_order/add', json=payload, headers=headers)
        assert result.status_code == 200, result.json
    with w.app.app_context():
        old, new = w.Contract.query.order_by(w.Contract.id).all()
        assert [(x.contract_id, x.contract_no, x.project_name)
                for x in w.InOrderItem.query.order_by(w.InOrderItem.id)] == [
                    (old.id, 'HD261103', '原工程'), (new.id, 'HD261120', '深圳第二园区'),
                    (new.id, 'HD261120', '深圳第二园区'), (None, None, None)]
    assert '深圳第二园区' in client.get('/contract?search=HD261120').text


@pytest.mark.parametrize('number,name,message', [
    ('HD-NEW', '', '工程名称'), ('', '新工程', '合同编号'),
    ('1103', '', '多个'), ('HD261103', '另一工程', '原工程'),
    ('HD-FIRST', '冲突工程', '新工程'),
])
def test_invalid_later_contract_rolls_back_receipt_and_archive(purchase, number, name, message):
    client, payload = purchase
    with w.app.app_context():
        w.db.session.add(w.Contract(contract_no='WX1103', project_name='另一档案'))
        w.db.session.commit()
    first = payload['items'][0]
    payload['items'] = [dict(first, contract_no='HD-FIRST', project_name='新工程'),
                        dict(first, contract_no=number, project_name=name)]
    result = client.post('/in_order/add', json=payload)
    assert result.status_code == 400, result.json
    assert '第 2 行' in result.json['msg'] and message in result.json['msg']
    with w.app.app_context():
        assert w.Contract.query.count() == 2
        assert w.InOrder.query.count() == w.InOrderItem.query.count() == 0


def test_full_numeric_contract_wins_over_suffix(purchase):
    client, payload = purchase
    with w.app.app_context():
        w.db.session.add(w.Contract(contract_no='1103', project_name='数字合同'))
        w.db.session.commit()
    payload['items'][0]['contract_no'] = '1103'
    assert client.post('/in_order/add', json=payload).status_code == 200
    with w.app.app_context():
        assert w.InOrderItem.query.one().project_name == '数字合同'


def test_purchase_grid_has_archive_and_uses_it_on_draft_edit(purchase):
    client, payload = purchase
    created = client.post('/in_order/add', json=payload)
    oid = created.json['id']
    page = client.get(f'/in_order/add?order_id={oid}')
    assert 'WMS.purchaseReceiptContracts =' in page.text and 'HD261103' in page.text
    assert 'WMS.purchaseReceiptContracts =' not in client.get('/in_order/add?type=product').text
    payload.update(order_id=oid)
    payload['items'][0]['contract_no'] = '1103'
    assert document_post(client, '/in_order/add', json=payload).status_code == 200
    result = document_post(client, f'/in_order/{oid}/item/add', data={
        'material_code': 'RETRY', 'quantity': 1, 'contract_no': 'HD-NEW', 'project_name': '新增工程'})
    assert result.status_code == 200, result.json
    with w.app.app_context():
        assert [(r.contract_no, r.project_name) for r in w.InOrderItem.query.order_by(w.InOrderItem.id)] == [
            ('HD261103', '原工程'), ('HD-NEW', '新增工程')]
        assert w.Contract.query.count() == 2
