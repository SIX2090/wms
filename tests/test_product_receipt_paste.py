"""Product clipboard rows resolve masters atomically when the receipt is saved."""
from copy import deepcopy

import pytest
import app as w

from tests.test_web_document_idempotency import receipt_case
from tests.test_document_edit_conflicts import revision


def _row(**changes):
    return dict(code='', name='配电柜', spec='800*675*2345', unit='台',
                box_no='PA03-1F-LP02', quantity=1, price=0, **changes)


def _unit():
    with w.app.app_context():
        w.db.session.add(w.Unit(code='TAI', name='台'))
        w.db.session.commit()


def test_product_save_allocates_and_reuses_without_merging_boxes(receipt_case):
    client, payload = receipt_case
    _unit()
    first = _row()
    second = dict(first, box_no='PA03-1F-LP03', quantity=2)
    third = dict(first, spec='1000*675*2345', box_no='003')
    payload['items'] = [first, second, third]
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 200, response.json
    with w.app.app_context():
        materials = w.Material.query.filter(w.Material.code.like('4%')).order_by(w.Material.code).all()
        assert [(m.code, m.name, m.spec, m.unit.name) for m in materials] == [
            ('400001', '配电柜', '800*675*2345', '台'), ('400002', '配电柜', '1000*675*2345', '台')]
        order = w.db.session.get(w.InOrder, response.json['id'])
        assert [i.box_no for i in order.items] == ['PA03-1F-LP02', 'PA03-1F-LP03', '003']
        assert [i.quantity for i in order.items] == [1, 2, 1]
        assert order.items[0].material_id == order.items[1].material_id
        assert w.StockTransaction.query.count() == 0
        assert all(m.stock == 0 for m in materials)


def test_product_matching_queries_entire_master_and_skips_used_numbers(receipt_case):
    client, payload = receipt_case
    _unit()
    with w.app.app_context():
        uid = w.Unit.query.one().id
        w.db.session.add_all([w.Material(code='400009', name='其他产品', spec='X', unit_id=uid),
                             w.Material(code='ZZ-LAST', name='配电柜', spec='800*675*2345', unit_id=uid)])
        w.db.session.commit()
    payload['items'] = [_row(), dict(_row(), spec='NEW')]
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 200, response.json
    with w.app.app_context():
        order = w.db.session.get(w.InOrder, response.json['id'])
        assert [i.material.code for i in order.items] == ['ZZ-LAST', '400010']


@pytest.mark.parametrize('changes,fragment', [
    ({'unit': '个'}, '单位'), ({'name': ''}, '名称'), ({'name': 'x'*101}, '名称'),
    ({'spec': 'x'*101}, '规格'), ({'code': 'MISSING'}, '编码'),
    ({'quantity': 0}, '数量'), ({'box_no': 'x'*101}, '箱体编号'),
])
def test_product_invalid_batch_has_no_partial_master_or_document(receipt_case, changes, fragment):
    client, payload = receipt_case
    _unit()
    payload['items'] = [_row(), dict(_row(), spec='OTHER', **changes)] if 'spec' not in changes else [_row(), dict(_row(), **changes)]
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 400, response.json
    assert fragment in response.json['msg']
    with w.app.app_context():
        assert w.Material.query.count() == 1 and w.InOrder.query.count() == 0
        assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('kind', ['mismatch', 'inactive', 'ambiguous'])
def test_product_conflicting_master_is_not_silently_changed(receipt_case, kind):
    client, payload = receipt_case
    _unit()
    with w.app.app_context():
        material = w.Material.query.one()
        material.name, material.spec, material.unit_id = '配电柜', '800*675*2345', w.Unit.query.one().id
        if kind == 'inactive': material.status = 'inactive'
        if kind == 'ambiguous':
            w.db.session.add(w.Material(code='OTHER', name=material.name, spec=material.spec, brand='另一品牌', unit_id=material.unit_id))
        w.db.session.commit()
    payload['items'] = [dict(_row(), code='RETRY', spec='WRONG') if kind == 'mismatch' else _row()]
    response = client.post('/in_order/add', json=payload)
    assert response.status_code == 400, response.json
    with w.app.app_context():
        assert w.Material.query.filter_by(code='RETRY').one().spec == '800*675*2345'
        assert w.InOrder.query.count() == 0


def test_product_edit_and_idempotent_retry_do_not_create_more_masters(receipt_case):
    client, payload = receipt_case
    _unit()
    payload['items'] = [_row()]
    headers = {'X-Idempotency-Key': 'product-paste'}
    first = client.post('/in_order/add', json=payload, headers=headers)
    again = client.post('/in_order/add', json=payload, headers=headers)
    assert first.status_code == again.status_code == 200
    assert first.json == again.json
    oid = first.json['id']
    changed = deepcopy(payload)
    changed['order_id'] = oid
    changed['items'].append(dict(_row(), box_no='SECOND'))
    result = client.post('/in_order/add', json=changed, headers={
        'X-WMS-Document-Revision': revision(client, f'/in_order/add?order_id={oid}')})
    assert result.status_code == 200, result.json
    with w.app.app_context():
        assert w.Material.query.count() == 2
        assert len(w.db.session.get(w.InOrder, oid).items) == 2


def test_non_product_still_requires_existing_code(receipt_case):
    client, payload = receipt_case
    payload.update(business_type='采购入库', items=[_row()])
    assert client.post('/in_order/add', json=payload).status_code == 400
    with w.app.app_context():
        assert w.Material.query.count() == 1


def test_product_form_json_accepts_uncoded_rows(receipt_case):
    import json
    client, payload = receipt_case
    _unit()
    data = dict(payload, items_json=json.dumps([_row()], ensure_ascii=False))
    data.pop('items')
    result = client.post('/in_order/add', data=data)
    assert result.status_code == 200, result.json


def test_product_sequence_continues_after_400999(receipt_case):
    client, payload = receipt_case
    _unit()
    with w.app.app_context():
        w.db.session.add(w.Material(code='400999', name='历史产品'))
        w.db.session.commit()
    payload['items'] = [_row()]
    result = client.post('/in_order/add', json=payload)
    assert result.status_code == 200, result.json
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, result.json['id']).items[0].material.code == '401000'


@pytest.mark.parametrize('same_material', [True, False])
def test_resolve_product_receipt_materials(receipt_case, tmp_path, monkeypatch, same_material):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine
    client, payload = receipt_case
    engine = create_engine('sqlite:///' + (tmp_path/'parallel-products.db').as_posix(), connect_args={'timeout': 30})
    with w.app.app_context():
        monkeypatch.setitem(w.db.engines, None, engine)
        w.db.create_all()
        users = [w.User(username='operator-' + str(i), role='warehouse', password_hash='unused', must_change_password=False) for i in range(2)]
        warehouse = w.Warehouse(code='P-W', name='并发仓', status='active')
        w.db.session.add_all(users + [warehouse, w.Unit(code='TAI', name='台')])
        w.db.session.commit()
        ids, wid = [u.id for u in users], warehouse.id
        w.db.session.remove()

    def send(index):
        c = w.app.test_client()
        with c.session_transaction() as session:
            session['_user_id'], session['_fresh'] = str(ids[index]), True
        item = dict(_row(), spec='same' if same_material else str(index), box_no='BOX-' + str(index))
        return c.post('/in_order/add', json=dict(payload, order_no='PAR-' + str(index), warehouse_id=wid, items=[item]))
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(send, range(2)))
        assert [r.status_code for r in results] == [200, 200], [r.json for r in results]
        with w.app.app_context():
            assert w.Material.query.count() == (1 if same_material else 2)
            assert {m.code for m in w.Material.query.all()} == ({'400001'} if same_material else {'400001', '400002'})
            assert {o.operator_id for o in w.InOrder.query.all()} == set(ids)
            assert w.InOrderItem.query.count() == 2 and w.StockTransaction.query.count() == 0
            w.db.session.remove()
    finally:
        engine.dispose()
