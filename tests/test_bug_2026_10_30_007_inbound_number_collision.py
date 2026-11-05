"""Inbound previews must never turn a new save into an edit of an old draft."""
from datetime import datetime
import json

import pytest

import app as wms
from app import (Customer, InOrder, InOrderItem, Material, StockTransaction,
                 SubcontractReceive, Supplier, User, Warehouse, db)


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        user = User(username='collision-test', role='admin', status='normal',
                    password_hash='unused-test-fixture', must_change_password=False)
        warehouses = [Warehouse(code='COL-A', name='碰号甲仓', status='active', is_default=True),
                      Warehouse(code='COL-B', name='碰号乙仓', status='active')]
        material = Material(code='COL-M', name='碰号测试物料', stock=10, price=2)
        customer = Customer(code='COL-C', name='隔离客户')
        supplier = Supplier(code='COL-S', name='隔离供应商')
        db.session.add_all([user, *warehouses, material, customer, supplier])
        db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield client, warehouses, material, customer, supplier
        db.session.remove()


KINDS = [('采购入库', 'IN'), ('产品入库', 'PI'), ('其他入库', 'OI'), ('销售退货入库', 'SR')]


def _payload(case, kind, number, **changes):
    _, warehouses, _, customer, supplier = case
    data = dict(order_no=number, business_type=kind, purpose=kind,
                warehouse_id=warehouses[1].id, customer_id=customer.id,
                supplier_id=supplier.id, remark='new-request',
                items=[dict(code='COL-M', quantity=7, price=3)])
    data.update(changes)
    return data


@pytest.mark.parametrize('kind,prefix', KINDS)
@pytest.mark.parametrize('transport', ['json', 'form'])
def test_new_same_number_cannot_overwrite_draft(case, kind, prefix, transport):
    client, warehouses, material, _, _ = case
    number = prefix + datetime.now().strftime('%y%m') + '0001'
    old = InOrder(order_no=number, business_type=kind, warehouse=warehouses[0].name,
                  remark='original', status='pending', total_amount=2)
    db.session.add(old)
    db.session.flush()
    item = InOrderItem(in_order_id=old.id, material_id=material.id,
                       quantity=1, price=2, amount=2, remark='keep-line')
    db.session.add(item)
    db.session.commit()
    before = (old.id, item.id, old.date, old.operator_id)
    data = _payload(case, kind, number)
    if transport == 'json':
        response = client.post('/in_order/add', json=data)
    else:
        data['items_json'] = json.dumps(data.pop('items'))
        response = client.post('/in_order/add', data=data)
    assert response.status_code == 409, response.get_json()
    assert '单号已存在' in response.get_json()['msg']
    db.session.expire_all()
    assert InOrder.query.count() == 1
    old = db.session.get(InOrder, before[0])
    assert (old.warehouse, old.remark, old.total_amount) == (warehouses[0].name, 'original', 2)
    assert (old.date, old.operator_id) == before[2:]
    assert [(i.id, i.material_id, i.quantity, i.price, i.amount, i.remark) for i in old.items] == [
        (before[1], material.id, 1, 2, 2, 'keep-line')]
    assert db.session.get(Material, material.id).stock == 10
    assert StockTransaction.query.count() == 0


@pytest.mark.parametrize('kind,prefix', KINDS)
def test_missing_number_uses_business_prefix(case, kind, prefix):
    response = case[0].post('/in_order/add', json=_payload(case, kind, ''))
    body = response.get_json()
    assert body['status'] == 'success', body
    assert body['order_no'].startswith(prefix + datetime.now().strftime('%y%m'))


def test_other_inbound_preview_advances_existing_numbers(case):
    number = 'OI' + datetime.now().strftime('%y%m') + '0001'
    db.session.add(InOrder(order_no=number, business_type='其他入库', warehouse=case[1][0].name))
    db.session.commit()
    assert wms.generate_order_no('OI') == number[:-4] + '0002'
    response = case[0].get('/other_in_order/add')
    assert f'value="{number[:-4]}0002"' in response.get_data(as_text=True)


@pytest.mark.parametrize('return_suffix,receive_suffix', [('0002', '0001'), ('0001', '0003')])
def test_sales_return_shared_prefix_accounts_for_both_tables(case, return_suffix, receive_suffix):
    base = 'SR' + datetime.now().strftime('%y%m')
    db.session.add(InOrder(order_no=base + return_suffix, business_type='销售退货入库',
                           warehouse=case[1][0].name))
    db.session.add(SubcontractReceive(receive_no=base + receive_suffix, warehouse=case[1][0].name))
    db.session.commit()
    assert wms.generate_order_no('SR') == base + f'{max(int(return_suffix), int(receive_suffix)) + 1:04d}'


def test_explicit_id_still_edits_only_target(case):
    client, warehouses, material, _, _ = case
    old = InOrder(order_no='COL-EDIT', business_type='其他入库', warehouse=warehouses[0].name,
                  status='pending', remark='old')
    db.session.add(old)
    db.session.commit()
    response = client.post('/in_order/add', json=_payload(case, '其他入库', 'COL-EDIT', order_id=old.id))
    body = response.get_json()
    assert body['status'] == 'success', body
    assert body['id'] == old.id
    db.session.expire_all()
    assert InOrder.query.count() == 1
    assert old.warehouse == warehouses[1].name
    assert [(i.quantity, i.price) for i in old.items] == [(7, 3)]
    assert material.stock == 10
    assert StockTransaction.query.count() == 0


@pytest.mark.parametrize('prefix', ['IN', 'PI', 'OI', 'SR'])
def test_number_uses_highest_suffix_not_last_inserted_row(case, prefix):
    base = prefix + datetime.now().strftime('%y%m')
    for suffix in ('9999', '10000', '0002', '-legacy'):
        db.session.add(InOrder(order_no=base + suffix, business_type='其他入库', warehouse=case[1][0].name))
        db.session.flush()
    db.session.commit()
    assert wms.generate_order_no(prefix) == base + '10001'
