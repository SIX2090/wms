"""Transfer HTTP history/precision; only the standard isolated Linux CI may import WMS."""
import math
from datetime import date

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from sqlalchemy import event  # noqa: E402
import app as w  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402
from tests.test_opening_reference_ownership_runtime_20261113 import source_scene  # noqa: E402,F401


def _pair(order, material, source, target, quantity, source_bin='SAME', target_bin='SAME'):
    rows=[]
    for warehouse,place,value,kind in ((source,source_bin,-quantity,'transfer_out'),
                                       (target,target_bin,quantity,'transfer_in')):
        row=w.StockTransaction(material_id=material.id,warehouse_id=warehouse.id,location=place,
            quantity=value,transaction_type=kind,reference_type='transfer',reference_id=order.id)
        w.db.session.add(row);rows.append(row)
    w.db.session.flush()
    return rows


def _scene(scene,location_on,mode):
    client,a,b=scene
    w.set_system_setting('location_management_enabled','1' if location_on else '0')
    w.set_system_setting('allow_negative_stock','0')
    w.set_system_setting('allow_negative_location_stock','0')
    material=w.Material(code='SYN-TRANSFER',name='合成调拨历史',stock=20)
    target=a if mode=='same_warehouse' else b
    source_bin='LEFT' if mode=='same_warehouse' else 'SAME'
    target_bin='RIGHT' if mode=='same_warehouse' else 'SAME'
    order=w.TransferOrder(transfer_no='SYN-TRANSFER',from_warehouse=a.name,to_warehouse=target.name,
        from_location=source_bin,to_location=target_bin,status='completed',remark='合成原备注')
    w.db.session.add_all([material,order]);w.db.session.flush()
    quantities=[1.005,0.335] if mode in ('duplicates','normalized_perline') else [1.005]
    recorded=[1.01,0.34] if mode=='normalized_perline' else ([1.01] if mode in ('normalized','closed_proven') else quantities)
    if mode=='ordinary':quantities,recorded=[2.25],[2.25]
    for quantity in quantities:
        w.db.session.add(w.TransferOrderItem(transfer_order_id=order.id,material_id=material.id,
            quantity=quantity,price=3.56789,amount=12.34567,remark='合成原行备注'))
    for warehouse in (a,target):
        w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=warehouse.id,
            location=warehouse.name,quantity=10,transaction_type='opening',
            reference_type='material_initial',reference_id=material.id))
    if mode.startswith('closed_'):
        if mode=='closed_per_line_residue':
            _pair(order,material,a,target,1.005,source_bin,target_bin)
            before=_pair(order,material,a,target,1.005,source_bin,target_bin)
            after=_pair(order,material,target,a,2.01,target_bin,source_bin)
        else:
            before=_pair(order,material,a,target,0.335,source_bin,target_bin)
            after=_pair(order,material,target,a,0.34 if mode=='closed_residue' else 0.335,target_bin,source_bin)
        if mode=='closed_missing_bin':before[0].location=''
        if mode=='closed_other_bin':after[0].location='OLD-BIN'
    rows=[]
    for quantity in recorded:
        rows.extend(_pair(order,material,a,target,quantity,source_bin,target_bin))
    if location_on:
        w.db.session.add_all([w.LocationInventory(material_id=material.id,warehouse_id=a.id,
            location=source_bin,quantity=10-math.fsum(recorded)),
            w.LocationInventory(material_id=material.id,warehouse_id=target.id,
            location=target_bin,quantity=10+math.fsum(recorded))])
    if mode=='unknown':rows[0].warehouse_id=None
    if mode=='missing_bin':rows[0].location=''
    if mode=='different_bin':rows[-1].location='OTHER'
    if mode=='missing_leg':w.db.session.delete(rows[-1])
    if mode=='bad_type':rows[0].transaction_type='revert_transfer'
    if mode=='different_pair':rows[-1].quantity+=0.001
    if mode=='physical_normalized':
        w.LocationInventory.query.filter_by(warehouse_id=a.id).one().quantity=8.99
        w.LocationInventory.query.filter_by(warehouse_id=b.id).one().quantity=11.01
    w.db.session.commit()
    return client,a,target,material,order


def _state(material):
    w.db.session.expire_all()
    return (material.stock,
        [(row.id,row.quantity,row.warehouse_id,row.location,row.transaction_type)
         for row in w.StockTransaction.query.order_by(w.StockTransaction.id)],
        [(row.id,row.quantity,row.warehouse_id,row.location)
         for row in w.LocationInventory.query.order_by(w.LocationInventory.id)],
        [(row.id,row.status,row.from_warehouse,row.to_warehouse,row.from_location,row.to_location,row.remark)
         for row in w.TransferOrder.query.order_by(w.TransferOrder.id)],
        [(row.id,row.material_id,row.quantity,row.price,row.amount,row.remark)
         for row in w.TransferOrderItem.query.order_by(w.TransferOrderItem.id)],
        [[tuple(getattr(row,column.name) for column in getattr(w,name).__table__.columns)
          for row in getattr(w,name).query.order_by(getattr(w,name).id)]
         for name in ('Material','StockTransaction','LocationInventory','TransferOrder',
                      'TransferOrderItem','OperationLog','OperationAudit')])


def _post(client,order,action):
    return document_post(client,f'/transfer/{order.id}/{action}')


def _assert_restored(material,order,location_on):
    w.db.session.expire_all()
    assert material.stock==20
    assert math.fsum(row.quantity for row in w.StockTransaction.query)==pytest.approx(20,rel=0,abs=1e-12)
    grouped={}
    for row in w.StockTransaction.query.filter_by(reference_type='transfer',reference_id=order.id):
        key=(row.material_id,row.warehouse_id,row.location if location_on else '')
        grouped.setdefault(key,[]).append(row.quantity)
    for key,values in grouped.items():
        assert math.fsum(values)==pytest.approx(0,rel=0,abs=1e-12),key
    if location_on:
        for row in w.LocationInventory.query:assert row.quantity==pytest.approx(10,rel=0,abs=1e-12)


def _assert_monthly_ending(material,warehouse,expected):
    _,rows,_=w._build_warehouse_monthly_report(dict(warehouse_id=warehouse.id,warehouse=warehouse.name,
        start_month=date.today().strftime('%Y-%m'),end_month=date.today().strftime('%Y-%m'),
        material_code=material.code,hide_zero=False))
    assert len(rows)==1
    assert rows[0]['ending_quantity']==pytest.approx(expected,rel=0,abs=1e-12)


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['raw','normalized','normalized_perline','duplicates','ordinary','closed_proven'])
def test_actual_transfer_history_then_normalized_complete_revert(source_scene,location_on,mode):
    client,a,b,material,order=_scene(source_scene,location_on,mode)
    financial=[(row.id,row.quantity,row.price,row.amount,row.remark) for row in order.items]
    if location_on and mode in ('raw','duplicates'):
        before=_state(material)
        response=_post(client,order,'revert')
        assert response.get_json()['status']=='error',response.get_json()
        assert '逐库位原数量落账证明' in response.get_json()['msg']
        assert _state(material)==before
        assert order.status=='completed'
        return
    response=_post(client,order,'revert')
    assert response.status_code==200 and response.get_json()['status']=='success',response.get_json()
    assert order.status=='pending'
    _assert_restored(material,order,location_on)
    before=_state(material)
    assert _post(client,order,'revert').get_json()['status']=='error'
    assert _state(material)==before
    for _ in range(2):
        response=_post(client,order,'complete')
        assert response.status_code==200 and response.get_json()['status']=='success',response.get_json()
        expected=math.fsum(w.normalize_stock_quantity(row.quantity) for row in order.items)
        assert w.get_warehouse_stock_quantities(a)[material.id]==pytest.approx(10-expected,rel=0,abs=1e-12)
        assert w.get_warehouse_stock_quantities(b)[material.id]==pytest.approx(10+expected,rel=0,abs=1e-12)
        assert _post(client,order,'revert').get_json()['status']=='success'
        _assert_restored(material,order,location_on)
    assert [(row.id,row.quantity,row.price,row.amount,row.remark) for row in order.items]==financial
    _assert_monthly_ending(material,a,10)
    _assert_monthly_ending(material,b,10)


@pytest.mark.parametrize('mode',['raw','normalized'])
def test_actual_same_warehouse_two_bins_keep_each_source_net_zero(source_scene,mode):
    client,a,b,material,order=_scene(source_scene,True,'same_warehouse')
    if mode=='normalized':
        rows=w.StockTransaction.query.filter_by(reference_type='transfer',reference_id=order.id).all()
        for row in rows:row.quantity=1.01 if row.quantity>0 else -1.01
        w.LocationInventory.query.filter_by(location='LEFT').one().quantity=8.99
        w.LocationInventory.query.filter_by(location='RIGHT').one().quantity=11.01
        w.db.session.commit()
    else:
        before=_state(material)
        response=_post(client,order,'revert')
        assert response.get_json()['status']=='error'
        assert '逐库位原数量落账证明' in response.get_json()['msg']
        assert _state(material)==before
        return
    for cycle in range(3):
        assert _post(client,order,'revert').get_json()['status']=='success'
        _assert_restored(material,order,True)
        if cycle<2:assert _post(client,order,'complete').get_json()['status']=='success'
    _assert_monthly_ending(material,a,20)


REFUSALS=[(mode,on) for mode in ('closed_residue','unknown','missing_leg','bad_type','different_pair') for on in (False,True)]
REFUSALS += [(mode,True) for mode in ('missing_bin','different_bin','physical_normalized','closed_missing_bin','closed_other_bin','closed_per_line_residue')]
assert REFUSALS and len(REFUSALS)==16


@pytest.mark.parametrize('mode,location_on',REFUSALS)
def test_actual_transfer_unproven_history_refuses_without_mutation(source_scene,mode,location_on):
    client,a,b,material,order=_scene(source_scene,location_on,mode)
    before=_state(material)
    response=_post(client,order,'revert')
    assert response.get_json()['status']=='error',response.get_json()
    assert _state(material)==before
    assert order.status=='completed'


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('change',['ambiguous','other_bin','other_warehouse'])
def test_actual_completion_checks_only_unprovable_cycle_boundary(source_scene,location_on,change):
    client,a,b,material,order=_scene(source_scene,location_on,'closed_proven' if location_on else 'raw')
    assert _post(client,order,'revert').get_json()['status']=='success'
    if change=='ambiguous':
        order.from_warehouse,order.to_warehouse=order.to_warehouse,order.from_warehouse
        order.from_location,order.to_location=order.to_location,order.from_location
    elif change=='other_bin':
        order.to_location='OTHER'
        if location_on:
            w.db.session.add(w.LocationInventory(material_id=material.id,warehouse_id=b.id,location='OTHER',quantity=0))
    else:
        c=w.Warehouse(code='SYN-C',name='合成丙仓',status='active')
        w.db.session.add(c);w.db.session.flush()
        w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=c.id,location=c.name,
            quantity=10,transaction_type='opening',reference_type='material_initial',reference_id=material.id))
        material.stock=30;order.to_warehouse=c.name
        if location_on:
            w.db.session.add(w.LocationInventory(material_id=material.id,warehouse_id=c.id,location='SAME',quantity=10))
    w.db.session.commit()
    before=_state(material)
    response=_post(client,order,'complete')
    if change=='ambiguous':
        assert response.get_json()['status']=='error'
        assert '无法区分' in response.get_json()['msg']
        assert _state(material)==before
    else:
        assert response.get_json()['status']=='success',response.get_json()
        assert _post(client,order,'revert').get_json()['status']=='success'
        assert _state(material)[0]==before[0]
        assert _state(material)[2]==before[2]


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('quantity',[1.005,1.004,0.004])
def test_actual_new_pending_rows_keep_zero_and_rounded_inventory_cycles(source_scene,location_on,quantity):
    client,a,b,material,order=_scene(source_scene,location_on,'raw')
    w.StockTransaction.query.filter_by(reference_type='transfer',reference_id=order.id).delete()
    order.status='pending';order.items[0].quantity=quantity
    if location_on:
        for row in w.LocationInventory.query:row.quantity=10
    w.db.session.commit()
    for _ in range(2):
        assert _post(client,order,'complete').get_json()['status']=='success'
        expected=w.normalize_stock_quantity(quantity)
        assert w.get_warehouse_stock_quantities(a)[material.id]==pytest.approx(10-expected,rel=0,abs=1e-12)
        assert _post(client,order,'revert').get_json()['status']=='success'
        _assert_restored(material,order,location_on)


def test_actual_second_location_failure_rolls_back_both_legs_and_status(source_scene):
    client,a,b,material,order=_scene(source_scene,True,'normalized')
    before=_state(material);hits=[]
    def fail_second(_connection,_cursor,statement,_parameters,_context,_executemany):
        if statement.lstrip().upper().startswith('UPDATE LOCATION_INVENTORY'):
            hits.append(True)
            if len(hits)==2:raise RuntimeError('owned synthetic transfer second-leg DML failure')
    event.listen(w.db.engine,'before_cursor_execute',fail_second)
    try:response=_post(client,order,'revert')
    finally:event.remove(w.db.engine,'before_cursor_execute',fail_second)
    assert hits==[True,True]
    assert response.get_json()['status']=='error'
    assert _state(material)==before


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('allowed',[False,True])
def test_actual_transfer_reversal_preserves_existing_negative_stock_policy(source_scene,location_on,allowed):
    client,a,b,material,order=_scene(source_scene,location_on,'normalized' if location_on else 'raw')
    w.set_system_setting('allow_negative_stock','1' if allowed else '0')
    w.set_system_setting('allow_negative_location_stock','1' if allowed else '0')
    w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=b.id,
        quantity=-11,transaction_type='out',reference_type='synthetic-used',reference_id=0))
    material.stock=9
    if location_on:w.LocationInventory.query.filter_by(warehouse_id=b.id).one().quantity=0.01
    w.db.session.commit()
    before=_state(material)
    response=_post(client,order,'revert')
    if location_on and allowed:
        assert response.get_json()['status']=='success',response.get_json()
        assert material.stock==9
        assert w.LocationInventory.query.filter_by(warehouse_id=b.id).one().quantity==pytest.approx(-1,rel=0,abs=1e-12)
        assert w.get_warehouse_stock_quantities(b)[material.id]==pytest.approx(-1,rel=0,abs=1e-12)
    else:
        # 既有关库位调拨反提交无条件检查调入仓余额；本项不改该政策。
        assert response.get_json()['status']=='error',response.get_json()
        assert _state(material)==before


COMPENSATIONS=[(quantity,reverse) for quantity in (1.005,0.335) for reverse in (False,True)]
assert len(COMPENSATIONS)==4 and len(set(COMPENSATIONS))==4


@pytest.mark.parametrize('quantity,reverse',COMPENSATIONS)
def test_actual_cross_bin_raw_normalization_compensation_refuses_without_mutation(source_scene,quantity,reverse):
    client,a,b,material,order=_scene(source_scene,True,'raw')
    source,target=(b,a) if reverse else (a,b)
    order.from_warehouse,order.to_warehouse=source.name,target.name
    order.items[0].quantity=quantity
    rows=w.StockTransaction.query.filter_by(reference_type='transfer',reference_id=order.id).order_by(w.StockTransaction.id).all()
    for row,warehouse,value in ((rows[0],source,-quantity),(rows[1],target,quantity)):
        row.warehouse_id,row.quantity=warehouse.id,value
    other=w.TransferOrder(transfer_no='SYN-OTHER',from_warehouse=target.name,to_warehouse=source.name,
        from_location='OTHER',to_location='OTHER',status='completed',remark='另一旧单')
    w.db.session.add(other);w.db.session.flush()
    w.db.session.add(w.TransferOrderItem(transfer_order_id=other.id,material_id=material.id,
        quantity=quantity,price=3.56789,amount=12.34567,remark='原行备注'))
    _pair(other,material,target,source,quantity,'OTHER','OTHER')
    normalized=w.normalize_stock_quantity(quantity)
    for warehouse,value in ((source,10-normalized),(target,10+normalized)):
        w.LocationInventory.query.filter_by(warehouse_id=warehouse.id,location='SAME').one().quantity=value
    for warehouse,value in ((source,10+normalized),(target,10-normalized)):
        w.db.session.add(w.LocationInventory(material_id=material.id,warehouse_id=warehouse.id,
            location='OTHER',quantity=value))
        w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=warehouse.id,
            location='',quantity=10,transaction_type='opening',reference_type='material_initial',reference_id=material.id))
    material.stock=40;w.db.session.commit()
    for warehouse in (source,target):
        assert math.fsum(row.quantity for row in w.LocationInventory.query.filter_by(warehouse_id=warehouse.id))==20
        assert math.fsum(row.quantity for row in w.StockTransaction.query.filter_by(warehouse_id=warehouse.id))==20
    before=_state(material)
    response=_post(client,order,'revert')
    assert response.get_json()['status']=='error',response.get_json()
    assert '逐库位原数量落账证明' in response.get_json()['msg']
    assert _state(material)==before
    assert order.status=='completed'
