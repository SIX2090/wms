"""Product receipt auto-created masters belong to category 400 atomically."""
import json

import pytest
import app as w

from tests.test_web_document_idempotency import receipt_case
from tests.test_document_edit_conflicts import revision
from tests.test_product_receipt_paste import _row


@pytest.fixture
def product_category_case(receipt_case):
    client, payload = receipt_case
    with w.app.app_context():
        other = w.MaterialCategory(code='100', name='原材料')
        target = w.MaterialCategory(code='400', name='设备成品')
        unit = w.Unit(code='TAI', name='台')
        w.db.session.add_all([other, target, unit])
        w.db.session.commit()
        ids = {'other': other.id, 'target': target.id, 'unit': unit.id}
    return client, payload, ids


@pytest.mark.parametrize('transport', ['json', 'form'])
def test_new_product_masters_are_visible_in_finished_equipment_category(product_category_case, transport):
    client, payload, ids = product_category_case
    payload['items'] = [_row(), dict(_row(), box_no='SECOND'), dict(_row(), spec='OTHER')]
    if transport == 'json':
        response = client.post('/in_order/add', json=payload)
    else:
        form = dict(payload, items_json=json.dumps(payload['items'], ensure_ascii=False))
        form.pop('items')
        form.pop('order_id')
        response = client.post('/in_order/add', data=form)
    assert response.status_code == 200, response.json
    with w.app.app_context():
        masters = w.Material.query.filter(w.Material.code.in_(['400001', '400002'])).order_by(w.Material.code).all()
        assert [(m.code, m.category_id, m.category.code if m.category else None) for m in masters] == [
            ('400001', ids['target'], '400'), ('400002', ids['target'], '400')]
        order = w.db.session.get(w.InOrder, response.json['id'])
        assert len(order.items) == 3
        assert order.items[0].material_id == order.items[1].material_id
        assert w.StockTransaction.query.count() == 0
    result = client.get('/material', query_string={'category_id': ids['target']})
    assert result.status_code == 200
    body = result.get_data(as_text=True).split('<tbody>', 1)[1].split('</tbody>', 1)[0]
    assert '400001' in body and '400002' in body and '设备成品' in body
    assert 'RETRY' not in body


@pytest.mark.parametrize('explicit_code', [False, True])
@pytest.mark.parametrize('classified', [False, True])
def test_reused_product_master_keeps_original_category_without_target(product_category_case, explicit_code, classified):
    client, payload, ids = product_category_case
    with w.app.app_context():
        material = w.Material.query.one()
        material.name, material.spec, material.unit_id = '配电柜', '800*675*2345', ids['unit']
        material.category_id = ids['other'] if classified else None
        w.db.session.delete(w.db.session.get(w.MaterialCategory, ids['target']))
        w.db.session.commit()
    payload['items'] = [dict(_row(), code='RETRY' if explicit_code else '')]
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 200, response.json
    with w.app.app_context():
        assert w.Material.query.count() == 1
        assert w.Material.query.one().category_id == (ids['other'] if classified else None)
        assert w.db.session.get(w.InOrder, response.json['id']).items[0].material.code == 'RETRY'


def test_missing_product_category_rejects_atomically_and_retry_succeeds(product_category_case):
    client, payload, ids = product_category_case
    with w.app.app_context():
        w.db.session.delete(w.db.session.get(w.MaterialCategory, ids['target']))
        w.db.session.commit()
    payload['items'] = [_row()]
    headers = {'X-Idempotency-Key': 'missing-category-retry'}
    response = client.post('/in_order/add', json=payload, headers=headers)
    assert response.status_code == 400, response.json
    assert '400' in response.json['msg'] and '分类' in response.json['msg']
    with w.app.app_context():
        assert w.Material.query.count() == 1 and w.InOrder.query.count() == 0
        assert w.StockTransaction.query.count() == 0
        w.db.session.add(w.MaterialCategory(code='400', name='设备成品'))
        w.db.session.commit()
    retry = client.post('/in_order/add', json=payload, headers=headers)
    assert retry.status_code == 200, retry.json
    with w.app.app_context():
        assert w.Material.query.filter_by(code='400001').one().category.code == '400'


def test_later_row_failure_rolls_back_new_classified_master(product_category_case):
    client, payload, ids = product_category_case
    payload['items'] = [_row(), dict(_row(), spec='OTHER', unit='未知单位')]
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 400, response.json
    with w.app.app_context():
        assert w.Material.query.count() == 1 and w.InOrder.query.count() == 0
        assert w.MaterialCategory.query.filter_by(code='400').one().id == ids['target']
        assert w.StockTransaction.query.count() == 0


def test_product_edit_creates_only_new_master_in_finished_equipment_category(product_category_case):
    client, payload, ids = product_category_case
    first = client.post('/in_order/add', json=payload)
    assert first.status_code == 200, first.json
    oid = first.json['id']
    payload.update(order_id=oid, items=[{'code': 'RETRY', 'quantity': 1, 'price': 0}, _row()])
    response = client.post('/in_order/add', json=payload, headers={
        'X-WMS-Document-Revision': revision(client, f'/in_order/add?order_id={oid}')})
    assert response.status_code == 200, response.json
    with w.app.app_context():
        assert w.Material.query.filter_by(code='400001').one().category_id == ids['target']
        assert w.Material.query.filter_by(code='RETRY').one().category_id is None
        assert len(w.db.session.get(w.InOrder, oid).items) == 2
        assert w.StockTransaction.query.count() == 0
