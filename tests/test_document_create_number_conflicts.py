"""BUG-2026-11-01-024: a new request must never take over another draft."""
import copy
import json

import pytest
import app as wms
from app import db
from tests.document_revision_client import document_post


CASES = [
    ('sale', '/out_order/add', 'OutOrder', 'order_no'),
    ('other', '/out_order/add', 'OutOrder', 'order_no'),
    ('requisition', '/out_order/add', 'OutOrder', 'order_no'),
    ('after', '/after_sale_out/add', 'AfterSaleOutOrder', 'order_no'),
    ('transfer', '/transfer/save_table', 'TransferOrder', 'transfer_no'),
    ('check', '/check/save_table', 'InventoryCheck', 'check_no'),
    ('adjustment', '/adjustment/add', 'AdjustmentOrder', 'adjustment_no'),
    ('request', '/purchase_request/add', 'PurchaseRequest', 'request_no'),
]


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove()
        db.drop_all()
        db.create_all()
        a = wms.Warehouse(code='DC-A', name='碰号甲仓', status='active', is_default=True)
        b = wms.Warehouse(code='DC-B', name='碰号乙仓', status='active')
        u = wms.User(username='conflict-fixture', role='admin',
                     password_hash='unused-test-fixture', must_change_password=False)
        unit = wms.Unit(code='DC-U', name='个')
        dep = wms.Department(code='DC-D', name='测试部门')
        db.session.add_all([a, b, u, unit, dep])
        db.session.flush()
        mats = [wms.Material(code='DC-M'+str(i), name='碰号物料'+str(i),
                             unit_id=unit.id, stock=30, price=2) for i in (1, 2)]
        db.session.add_all(mats)
        db.session.flush()
        for mat in mats:
            # Include historical code attribution and two warehouses (R2).
            for wh, qty, historical in [(a, 20, True), (b, 10, False)]:
                db.session.add(wms.StockTransaction(
                    material_id=mat.id, transaction_type='in', quantity=qty,
                    warehouse_id=None if historical else wh.id,
                    location=wh.code if historical else wh.name,
                    reference_type='opening', reference_id=1))
        wms.set_system_setting('location_management_enabled', '0')
        db.session.commit()
        ids = dict(user=u.id, a=a.id, b=b.id, dep=dep.id,
                   mats=[m.id for m in mats], names=[a.name, b.name])
    clients = [wms.app.test_client(), wms.app.test_client()]
    for client in clients:
        with client.session_transaction() as session:
            session['_user_id'] = str(ids['user'])
            session['_fresh'] = True
    yield clients, ids
    with wms.app.app_context():
        db.session.remove()


def payload(kind, ids, number, second=False):
    index = int(second)
    line = dict(material_id=ids['mats'][index], code='DC-M'+str(index+1),
                material_code='DC-M'+str(index+1), quantity=7 if second else 1,
                actual_stock=7 if second else 1, price=2, estimated_price=2)
    header = dict(warehouse_id=ids['a'], from_warehouse=ids['names'][0],
                  to_warehouse=ids['names'][1], remark='second' if second else 'first')
    data = dict(order_no=number, check_no=number, transfer_no=number,
                adjustment_no=number, request_no=number,
                warehouse_id=ids['a'], department_id=ids['dep'],
                customer='隔离客户', adjustment_type='surplus',
                remark=header['remark'], header=header, items=[line])
    if kind in ('sale', 'other', 'requisition'):
        data['business_type'] = {'sale': '销售出库', 'other': '其他出库',
                                 'requisition': '领料单'}[kind]
    return data


def post(client, endpoint, data, transport):
    if transport == 'json':
        return client.post(endpoint, json=data)
    data = copy.deepcopy(data)
    if endpoint == '/adjustment/add':
        line = data.pop('items')[0]
        data.update(material_id=line['material_id'], quantity=line['quantity'])
    else:
        data['items'] = json.dumps(data['items'])
    data.pop('header', None)
    return client.post(endpoint, data=data)


def rows(model):
    columns = list(model.__table__.columns)
    return [tuple(getattr(row, col.name) for col in columns)
            for row in model.query.order_by(model.id).all()]


def snapshot(model):
    return dict(header=rows(model),
                items=[tuple(getattr(item, col.name) for col in item.__table__.columns)
                       for order in model.query.order_by(model.id) for item in order.items],
                materials=rows(wms.Material), transactions=rows(wms.StockTransaction),
                locations=rows(wms.LocationInventory))


TRANSPORT_CASES = [(entry, transport) for entry in CASES for transport in
                   (['json'] if entry[0] in ('transfer', 'check') else ['json', 'form'])]


@pytest.mark.parametrize('entry,transport', TRANSPORT_CASES,
                         ids=[c[0][0]+'-'+c[1] for c in TRANSPORT_CASES])
def test_new_same_number_preserves_original_and_inventory(case, entry, transport):
    clients, ids = case
    kind, endpoint, model_name, number_field = entry
    number = 'CONFLICT-'+kind
    first = post(clients[0], endpoint, payload(kind, ids, number), transport)
    assert first.status_code == 200, first.get_json()
    assert first.get_json()['status'] == 'success', first.get_json()
    model = getattr(wms, model_name)
    with wms.app.app_context():
        before = snapshot(model)
    second = post(clients[1], endpoint, payload(kind, ids, number, True), transport)
    assert second.status_code == 409, second.get_json()
    assert second.get_json()['status'] == 'error'
    assert '单号已存在' in second.get_json()['msg']
    with wms.app.app_context():
        assert snapshot(model) == before
        assert model.query.count() == 1
        assert getattr(model.query.one(), number_field) == number
        assert wms.get_warehouse_stock_quantities(db.session.get(wms.Warehouse, ids['a'])) == {
            material_id: 20 for material_id in ids['mats']}
        assert wms.get_warehouse_stock_quantities(db.session.get(wms.Warehouse, ids['b'])) == {
            material_id: 10 for material_id in ids['mats']}


@pytest.mark.parametrize('entry', CASES, ids=[c[0] for c in CASES])
def test_explicit_id_still_edits_its_draft_and_new_number_creates_separate_document(case, entry):
    clients, ids = case
    kind, endpoint, model_name, _ = entry
    data = payload(kind, ids, 'EDIT-'+kind)
    first = clients[0].post(endpoint, json=data)
    assert first.status_code == 200, first.get_json()
    document_id = first.get_json()['id']
    edit = payload(kind, ids, data['order_no'], True)
    edit['request_id' if kind == 'request' else 'order_id'] = document_id
    response = document_post(clients[0], endpoint, json=edit)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['id'] == document_id
    fresh = clients[1].post(endpoint, json=payload(kind, ids, 'FRESH-'+kind))
    assert fresh.status_code == 200, fresh.get_json()
    assert fresh.get_json()['id'] != document_id
    with wms.app.app_context():
        model = getattr(wms, model_name)
        assert model.query.count() == 2
        document = db.session.get(model, document_id)
        assert document.remark == 'second'
        assert len(document.items) == 1
        assert document.items[0].material_id == ids['mats'][1]
        assert [m.stock for m in wms.Material.query.order_by(wms.Material.id)] == [30, 30]
        assert sum(t.quantity for t in wms.StockTransaction.query.all()) == 60
