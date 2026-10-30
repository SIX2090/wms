"""BUG-2026-10-30-005: floating tails must not block exact stock depletion."""
from datetime import date

import pytest
from sqlalchemy import func

import app as wms
from app import (app, db, LocationInventory, Material, OutOrder, OutOrderItem,
                 StockTransaction, User, Warehouse, set_system_setting)
from services.warehouse_stock_service import apply_stock_delta


@pytest.fixture()
def stock_case(monkeypatch):
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    with app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove(); db.drop_all(); db.create_all()
        a = Warehouse(code='TAIL-A', name='尾差甲仓', is_default=True, status='active')
        b = Warehouse(code='TAIL-B', name='尾差乙仓', status='active')
        user = User(username='tail-fixture', role='admin', password_hash='unused', must_change_password=False)
        db.session.add_all([a, b, user]); db.session.flush()
        for key in ('location_management_enabled', 'allow_negative_stock', 'allow_negative_location_stock'):
            set_system_setting(key, '0')
        db.session.commit()
        yield a, b, user
        db.session.remove(); db.drop_all()


def deduct(material, warehouse, location=None):
    with app.test_request_context('/'):
        return apply_stock_delta(material, -.4, transaction_type='out', warehouse=warehouse, location=location)


def material_case(a, b, total, warehouse_qty, legacy=False, location_on=False):
    material = Material(code='207005', name='白锌螺母', stock=total)
    db.session.add(material); db.session.flush()
    for warehouse, quantity in [(a, warehouse_qty), (b, total - warehouse_qty)]:
        db.session.add(StockTransaction(material_id=material.id, transaction_type='in', quantity=quantity,
                                       warehouse_id=None if legacy else warehouse.id, location=warehouse.name))
        if location_on:
            db.session.add(LocationInventory(material_id=material.id, warehouse_id=warehouse.id,
                                             location='共用库位', quantity=quantity))
    db.session.commit()
    return material


@pytest.mark.parametrize('total,warehouse_qty', [
    (1.2-.3-.5, .4), (10.4, 1.2-.3-.5), (1.2-.3-.5, 1.2-.3-.5),
])
@pytest.mark.parametrize('legacy', [False, True])
def test_atomic_global_and_warehouse_guards_accept_only_float_tail(stock_case, total, warehouse_qty, legacy):
    a, b, _ = stock_case
    material = material_case(a, b, total, warehouse_qty, legacy)
    before_other = wms.get_warehouse_stock_quantities(b)[material.id]
    ok, error = deduct(material, a)
    assert ok, error
    db.session.commit()
    assert material.stock == (0 if total < 1 else 10)
    assert abs(wms.get_warehouse_stock_quantities(a).get(material.id, 0)) < 1e-6
    assert wms.get_warehouse_stock_quantities(b).get(material.id, 0) == before_other
    assert StockTransaction.query.filter_by(material_id=material.id, transaction_type='out').one().quantity == -.4
    assert abs(material.stock - db.session.query(func.sum(StockTransaction.quantity)).scalar()) < 1e-6


@pytest.mark.parametrize('total,warehouse_qty', [(.3999,.3999), (10.3999,.3999), (.39,.39), (10,0)])
def test_real_shortage_is_still_rejected_and_writes_nothing(stock_case, total, warehouse_qty):
    a, b, _ = stock_case
    material = material_case(a, b, total, warehouse_qty)
    ok, _ = deduct(material, a)
    assert not ok
    db.session.rollback()
    assert material.stock == total
    assert StockTransaction.query.count() == 2


@pytest.mark.parametrize('location_qty,accepted', [(1.2-.3-.5,True), (.3999,False), (.39,False)])
def test_location_atomic_guard_preserves_warehouse_isolation(stock_case, location_qty, accepted):
    a, b, _ = stock_case
    set_system_setting('location_management_enabled', '1')
    material = material_case(a, b, 10.4, location_qty, location_on=True)
    before_other = LocationInventory.query.filter_by(warehouse_id=b.id).one().quantity
    ok, error = deduct(material, a, '共用库位')
    assert ok is accepted, error
    if accepted:
        db.session.commit()
        assert LocationInventory.query.filter_by(warehouse_id=a.id).one().quantity == 0
        assert material.stock == 10
        assert StockTransaction.query.filter_by(transaction_type='out').count() == 1
    else:
        db.session.rollback()
        assert material.stock == 10.4
        assert StockTransaction.query.count() == 2
    assert LocationInventory.query.filter_by(warehouse_id=b.id).one().quantity == before_other


def test_four_decimal_remainder_is_not_rounded_away(stock_case):
    a, b, _ = stock_case
    material = material_case(a,b,1.2345,1.2345)
    ok,error=deduct(material,a)
    assert ok,error
    db.session.commit()
    assert material.stock == pytest.approx(.8345, abs=1e-12)


@pytest.mark.parametrize('offset,accepted', [(-.0000005,True),(.0000005,True),(-.000002,False)])
def test_tolerance_boundary_never_leaves_a_negative_balance(stock_case,offset,accepted):
    a,b,_=stock_case
    material=material_case(a,b,.4+offset,.4+offset)
    ok,error=deduct(material,a)
    assert ok is accepted,error
    if accepted:
        db.session.commit()
        assert material.stock==0
    else:
        db.session.rollback()
        assert material.stock==.4+offset


def test_explicit_negative_stock_policy_still_allows_real_negative_balance(stock_case):
    a,b,_=stock_case
    set_system_setting('allow_negative_stock','1')
    material=material_case(a,b,.3,.3)
    ok,error=deduct(material,a)
    assert ok,error
    db.session.commit()
    assert material.stock==pytest.approx(-.1,abs=1e-12)


@pytest.mark.parametrize('second_stock,accepted', [(1.2-.3-.5,True),(.3999,False)])
def test_real_issue_completion_is_atomic_and_retry_safe(stock_case, second_stock, accepted):
    a,b,user=stock_case
    material=material_case(a,b,second_stock,second_stock)
    first=Material(code='207003',name='螺丝',stock=.36)
    db.session.add(first);db.session.flush()
    db.session.add(StockTransaction(material_id=first.id,transaction_type='in',quantity=.36,warehouse_id=a.id))
    order=OutOrder(order_no='TAIL-ISSUE',date=date.today(),business_type='领料单',warehouse=a.name,status='pending',operator_id=user.id)
    db.session.add(order);db.session.flush()
    lines=[(first,.36),(material,.4)]
    for index,qty in enumerate([.44,.47,10,10,10,10]):
        extra=Material(code=f'TAIL-{index}',name='整单验证物料',stock=qty)
        db.session.add(extra);db.session.flush()
        db.session.add(StockTransaction(material_id=extra.id,transaction_type='in',quantity=qty,warehouse_id=a.id))
        lines.append((extra,qty))
    for mat,qty in lines:
        db.session.add(OutOrderItem(out_order_id=order.id,material_id=mat.id,quantity=qty,price=0,amount=0))
    db.session.commit()
    client=app.test_client()
    with client.session_transaction() as session:
        session['_user_id'],session['_fresh']=str(user.id),True
    response=client.post(f'/out_order/{order.id}/complete?force=true')
    assert response.json['status']==('success' if accepted else 'error'),response.json
    db.session.expire_all()
    assert order.status==('completed' if accepted else 'pending')
    assert first.stock==(0 if accepted else .36)
    assert material.stock==(0 if accepted else second_stock)
    assert StockTransaction.query.filter_by(transaction_type='out').count()==(8 if accepted else 0)
    for mat,qty in lines:
        assert mat.stock==(0 if accepted else (second_stock if mat.id==material.id else qty))
    if accepted:
        retry=client.post(f'/out_order/{order.id}/complete?force=true')
        assert retry.json['status']=='error'
        assert StockTransaction.query.filter_by(transaction_type='out').count()==8
