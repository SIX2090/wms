"""Actual in/out reversal routes; verified isolated memory runtime is required."""
import math

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
import app as w  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402
from tests.test_opening_reference_ownership_runtime_20261113 import source_scene  # noqa: E402,F401


def _scene(scene, route, location_on, mode):
    client,a,b=scene
    kind='out' if route=='out' else 'in'
    sign=1 if kind=='in' else -1
    w.set_system_setting('location_management_enabled','1' if location_on else '0')
    w.set_system_setting('allow_negative_stock','0')
    w.set_system_setting('allow_negative_location_stock','0')
    w.db.session.commit()
    material=w.Material(code='SYN-RECORDED',name='合成历史原量',stock=0)
    w.db.session.add(material)
    w.db.session.flush()
    cls,item_cls,key=(w.InOrder,w.InOrderItem,'in_order_id') if kind=='in' else (
        w.OutOrder,w.OutOrderItem,'out_order_id')
    order=cls(order_no='SYN-RECORDED-'+kind,warehouse=a.name,location='SAME',
              status='completed',total_amount=0)
    w.db.session.add(order)
    w.db.session.flush()
    quantities=[1.005,1.005] if mode in ('aggregate_raw','per_line_normalized') else [1.005]
    for quantity in quantities:
        w.db.session.add(item_cls(**{key:order.id,'material_id':material.id,
            'quantity':quantity,'price':0,'amount':0}))
    values=[sign*value for value in quantities]
    if mode in ('historical_normalized','closed_raw_then_current_norm'):
        values=[sign*1.01]
    elif mode=='aggregate_raw':
        values=[sign*2.01]
    elif mode=='per_line_normalized':
        values=[sign*1.01,sign*1.01]
    elif mode=='mismatch':
        values=[sign*1.02]
    elif mode=='closed_residue':
        values=[sign*1.005,-sign*1.01,sign*1.01]
    if mode=='closed_raw_then_current_norm':
        values=[sign*2.005,-sign*2.005,*values]
    source=[]
    for value in values:
        typ=('in' if value>=0 else 'revert_in') if kind=='in' else ('out' if value<=0 else 'revert_out')
        row=w.StockTransaction(material_id=material.id,warehouse_id=a.id,location=a.name,
            quantity=value,transaction_type=typ,reference_type=kind+'_order',reference_id=order.id,
            remark='合成已落历史流水')
        w.db.session.add(row)
        source.append(row)
    for warehouse in (a,b):
        w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=warehouse.id,
            location=warehouse.name,quantity=10,transaction_type='opening',
            reference_type='material_initial',reference_id=material.id,remark='合成基线'))
    material.stock=20+math.fsum(values)
    if location_on:
        w.db.session.add_all([
            w.LocationInventory(material_id=material.id,warehouse_id=a.id,location='SAME',quantity=10+math.fsum(values)),
            w.LocationInventory(material_id=material.id,warehouse_id=b.id,location='SAME',quantity=10)])
        if mode=='closed_residue':
            w.db.session.flush()
            w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity=10+sign*1.01
            w.db.session.add(w.LocationInventory(material_id=material.id,warehouse_id=a.id,
                location='OLD-BIN',quantity=-sign*0.005))
        elif mode=='location_difference':
            w.db.session.flush()
            w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity += 0.005
    if mode=='unknown_source':
        for row in source:
            row.warehouse_id=None
    elif mode=='missing_position':
        order.location=''
        for row in source:
            row.location=None
    w.db.session.commit()
    return client,order,material,a,b


def _post(client,order,route):
    if route=='batch_in':
        return document_post(client,'/in_order/batch_revert',json={'ids':[order.id]})
    return document_post(client,f'/{route}_order/{order.id}/revert')


def _state(material):
    w.db.session.expire_all()
    return (material.stock,
        [(row.id,row.quantity,row.reference_type,row.reference_id,row.warehouse_id)
         for row in w.StockTransaction.query.order_by(w.StockTransaction.id)],
        [(row.id,row.quantity,row.warehouse_id,row.location)
         for row in w.LocationInventory.query.order_by(w.LocationInventory.id)],
        [(row.id,row.status) for row in w.InOrder.query.order_by(w.InOrder.id)],
        [(row.id,row.status) for row in w.OutOrder.query.order_by(w.OutOrder.id)])


@pytest.mark.parametrize('route',['in','batch_in','out'])
@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['raw','aggregate_raw','historical_normalized',
                                'per_line_normalized','closed_raw_then_current_norm'])
def test_real_routes_preserve_raw_and_original_per_line_normalized_semantics(source_scene,route,location_on,mode):
    client,order,material,a,b=_scene(source_scene,route,location_on,mode)
    if mode=='closed_raw_then_current_norm' and location_on:
        before=_state(material)
        _assert_edge_refusal(_post(client,order,route),route,'闭合历史')
        assert _state(material)==before
        assert order.status=='completed'
        return
    response=_post(client,order,route)
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success',payload
    if route=='batch_in':
        assert payload['reverted']==1,payload
    assert order.status=='pending'
    assert material.stock==pytest.approx(20,abs=1e-12,rel=0)
    assert math.fsum(row.quantity for row in w.StockTransaction.query)==pytest.approx(20,abs=1e-12,rel=0)
    if location_on:
        locations={row.warehouse_id:row.quantity for row in w.LocationInventory.query}
        assert locations[a.id]==pytest.approx(10,abs=1e-12,rel=0)
        assert locations[b.id]==10


FAILURES=[(mode,location_on) for mode in ('mismatch','closed_residue','unknown_source')
          for location_on in (False,True)]+[('missing_position',True),('location_difference',True)]
MESSAGES={'mismatch':'净额不一致','closed_residue':'此前完成周期未准确回退',
          'unknown_source':'原仓归属缺失或冲突','missing_position':'原库位缺失',
          'location_difference':'原仓库位账与流水不一致'}


@pytest.mark.parametrize('route',['in','batch_in','out'])
@pytest.mark.parametrize('mode,location_on',FAILURES)
def test_real_routes_refuse_unproven_or_mismatching_history_and_rollback(source_scene,route,mode,location_on):
    client,order,material,a,b=_scene(source_scene,route,location_on,mode)
    before=_state(material)
    response=_post(client,order,route)
    payload=response.get_json()
    if route=='batch_in':
        assert response.status_code==200 and payload['status']=='success',payload
        assert payload['reverted']==0,payload
    else:
        assert response.status_code==400 and payload['status']=='error',payload
    assert MESSAGES[mode] in payload['msg'],payload
    assert _state(material)==before
    assert order.status=='completed'


def _assert_edge_refusal(response,route,message):
    payload=response.get_json()
    if route=='batch_in':
        assert response.status_code==200 and payload['status']=='success',payload
        assert payload['reverted']==0,payload
    else:
        assert response.status_code==400 and payload['status']=='error',payload
    assert message in payload['msg'],payload


@pytest.mark.parametrize('route',['in','batch_in','out'])
@pytest.mark.parametrize('location_on',[False,True])
def test_real_history_normalized_branch_cannot_return_to_a_conflicting_header_warehouse(source_scene,route,location_on):
    client,order,material,a,b=_scene(source_scene,route,location_on,'historical_normalized')
    order.warehouse=b.name
    w.db.session.commit()
    before=_state(material)
    _assert_edge_refusal(_post(client,order,route),route,'头仓库与原流水')
    assert _state(material)==before
    assert order.status=='completed'


@pytest.mark.parametrize('route',['in','batch_in'])
@pytest.mark.parametrize('extra_active',[False,True])
def test_real_zero_net_warehouse_cannot_hide_opposite_physical_positions(source_scene,route,extra_active):
    client,order,material,a,b=_scene(source_scene,route,True,'raw')
    warehouse=b if extra_active else a
    if not extra_active:
        order.items[0].quantity=0
        material.stock=20
        w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity=10
    else:
        w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=b.id,location=b.name,
            quantity=1.005,transaction_type='in',reference_type='in_order',reference_id=order.id))
    w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=warehouse.id,location=warehouse.name,
        quantity=-1.005,transaction_type='adjust_in_item',reference_type='in_order',reference_id=order.id))
    w.db.session.add_all([
        w.LocationInventory(material_id=material.id,warehouse_id=warehouse.id,location='HIST-POS',quantity=1.005),
        w.LocationInventory(material_id=material.id,warehouse_id=warehouse.id,location='HIST-NEG',quantity=-1.005)])
    w.db.session.commit()
    before=_state(material)
    _assert_edge_refusal(_post(client,order,route),route,'净零')
    assert _state(material)==before
    assert order.status=='completed'


@pytest.mark.parametrize('route',['in','batch_in','out'])
@pytest.mark.parametrize('mode',['code_placeholder','renamed_header'])
def test_real_history_uses_recorded_source_when_the_old_path_would_select_a_different_key(source_scene,route,mode):
    client,order,material,a,b=_scene(source_scene,route,True,'historical_normalized')
    if mode=='code_placeholder':
        order.warehouse=a.code
        order.location=''
        w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().location=a.name
    else:
        a.name='RENAMED-SYN-A'
    w.db.session.commit()
    response=_post(client,order,route)
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success',payload
    if route=='batch_in':
        assert payload['reverted']==1,payload
    assert order.status=='pending'
    assert material.stock==pytest.approx(20,abs=1e-12,rel=0)
    assert w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity==pytest.approx(10,abs=1e-12,rel=0)
    assert w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=b.id).one().quantity==10


@pytest.mark.parametrize('route',['in','batch_in','out'])
def test_real_zero_quantity_closed_records_have_no_unknown_physical_delta(source_scene,route):
    client,order,material,a,b=_scene(source_scene,route,True,'closed_raw_then_current_norm')
    rows=w.StockTransaction.query.filter_by(reference_type='out_order' if route=='out' else 'in_order',
        reference_id=order.id).order_by(w.StockTransaction.id).all()
    assert len(rows)==3
    sign=-1 if route=='out' else 1
    rows[0].quantity=rows[1].quantity=0
    rows[2].quantity=sign*1.005
    material.stock=20+sign*1.005
    w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity=10+sign*1.005
    w.db.session.commit()
    response=_post(client,order,route)
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success',payload
    if route=='batch_in':
        assert payload['reverted']==1,payload
    assert order.status=='pending'
    assert material.stock==pytest.approx(20,abs=1e-12,rel=0)
    assert w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity==pytest.approx(10,abs=1e-12,rel=0)


@pytest.mark.parametrize('route',['in','batch_in','out'])
@pytest.mark.parametrize('same_warehouse',[False,True])
def test_real_closed_zero_net_history_cannot_hide_physical_positions(source_scene,route,same_warehouse):
    client,order,material,a,b=_scene(source_scene,route,True,'raw')
    kind='out' if route=='out' else 'in'
    sign=-1 if kind=='out' else 1
    original=w.StockTransaction.query.filter_by(reference_type=kind+'_order',reference_id=order.id).one()
    w.db.session.delete(original)
    w.db.session.flush()
    old_warehouse=a if same_warehouse else b
    for warehouse,quantity,typ in ((old_warehouse,sign*1.005,kind),
        (old_warehouse,-sign*1.005,'revert_'+kind),(a,sign*1.005,kind)):
        w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=warehouse.id,
            location=warehouse.name,quantity=quantity,transaction_type=typ,
            reference_type=kind+'_order',reference_id=order.id))
        w.db.session.flush()
    w.db.session.add_all([
        w.LocationInventory(material_id=material.id,warehouse_id=old_warehouse.id,location='CLOSED-POS',quantity=1.005),
        w.LocationInventory(material_id=material.id,warehouse_id=old_warehouse.id,location='CLOSED-NEG',quantity=-1.005)])
    w.db.session.commit()
    before=_state(material)
    _assert_edge_refusal(_post(client,order,route),route,'闭合历史')
    assert _state(material)==before
    assert order.status=='completed'


@pytest.mark.parametrize('route',['in','batch_in','out'])
def test_real_ordinary_two_decimal_closed_records_keep_original_path(source_scene,route):
    client,order,material,a,b=_scene(source_scene,route,True,'closed_raw_then_current_norm')
    kind='out' if route=='out' else 'in'
    sign=-1 if kind=='out' else 1
    rows=w.StockTransaction.query.filter_by(reference_type=kind+'_order',reference_id=order.id).order_by(w.StockTransaction.id).all()
    assert len(rows)==3
    order.items[0].quantity=1.01
    rows[0].quantity=sign*1.01
    rows[1].quantity=-sign*1.01
    w.db.session.commit()
    response=_post(client,order,route)
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success',payload
    if route=='batch_in':
        assert payload['reverted']==1,payload
    assert order.status=='pending'
    assert material.stock==pytest.approx(20,abs=1e-12,rel=0)
    assert w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity==pytest.approx(10,abs=1e-12,rel=0)
