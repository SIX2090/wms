"""Actual routes preserving the global primitive guard under verified isolation."""
import math

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from sqlalchemy import event  # noqa: E402
import app as w  # noqa: E402
from tests.test_recorded_order_quantity_runtime_20261113 import (  # noqa: E402,F401
    source_scene, _scene, _post, _state)


def _other(material,b,quantity,location_on):
    w.StockTransaction.query.filter_by(material_id=material.id,warehouse_id=b.id,
        reference_type='material_initial').one().quantity=quantity
    material.stock=math.fsum(row.quantity for row in w.StockTransaction.query.filter_by(material_id=material.id))
    if location_on:
        w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=b.id).one().quantity=quantity
    w.db.session.commit()


def _business_state(material):
    return _state(material),[(row.id,row.stock) for row in w.Material.query.order_by(w.Material.id)]


def _assert_rejected(response,route):
    payload=response.get_json()
    if route=='batch_in':
        assert response.status_code==200 and payload['status']=='success',payload
        assert payload['reverted']==0,payload
    else:
        assert response.status_code==400 and payload['status']=='error',payload
    return payload


@pytest.mark.parametrize('route',['in','batch_in'])
@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['raw','historical_normalized','ordinary'])
def test_real_global_shortfall_preserves_raw_normalized_and_ordinary_primitive_boundary(source_scene,route,location_on,mode):
    client,order,material,a,b=_scene(source_scene,route,location_on,
        'historical_normalized' if mode=='ordinary' else mode)
    if mode=='ordinary':
        order.items[0].quantity=1.01
        w.db.session.commit()
    _other(material,b,-10.505 if mode=='raw' else -10.51,location_on)
    before=_business_state(material)
    payload=_assert_rejected(_post(client,order,route),route)
    if mode=='raw':
        assert '全局' in payload['msg'],payload
    assert _business_state(material)==before
    assert order.status=='completed'


@pytest.mark.parametrize('route',['in','batch_in'])
@pytest.mark.parametrize('location_on',[False,True])
def test_real_allow_negative_policy_remains_effective_without_rewriting_the_other_warehouse(source_scene,route,location_on):
    client,order,material,a,b=_scene(source_scene,route,location_on,'raw')
    _other(material,b,-10.505,location_on)
    w.set_system_setting('allow_negative_stock','1')
    w.db.session.commit()
    response=_post(client,order,route)
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success',payload
    if route=='batch_in':
        assert payload['reverted']==1,payload
    assert material.stock==pytest.approx(-0.505,abs=1e-12,rel=0)
    assert w.StockTransaction.query.filter_by(material_id=material.id,warehouse_id=b.id).one().quantity==-10.505
    if location_on:
        assert w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=b.id).one().quantity==-10.505


@pytest.mark.parametrize('location_on',[False,True])
def test_real_outbound_inverse_can_improve_a_still_negative_global_balance(source_scene,location_on):
    client,order,material,a,b=_scene(source_scene,'out',location_on,'raw')
    _other(material,b,-30,location_on)
    response=_post(client,order,'out')
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success',payload
    assert material.stock==pytest.approx(-20,abs=1e-12,rel=0)
    assert w.StockTransaction.query.filter_by(material_id=material.id,warehouse_id=b.id).one().quantity==-30


@pytest.mark.parametrize('route',['in','batch_in'])
@pytest.mark.parametrize('location_on',[False,True])
def test_real_float_representation_tail_is_not_a_material_global_shortfall(source_scene,route,location_on):
    client,order,material,a,b=_scene(source_scene,route,location_on,'raw')
    _other(material,b,-10,location_on)
    material.stock=math.nextafter(1.005,float('-inf'))
    w.db.session.commit()
    response=_post(client,order,route)
    payload=response.get_json()
    assert response.status_code==200 and payload['status']=='success',payload
    if route=='batch_in':
        assert payload['reverted']==1,payload
    assert abs(material.stock)<=8*math.ulp(1.005)
    assert w.StockTransaction.query.filter_by(material_id=material.id,warehouse_id=b.id).one().quantity==-10


def _second(order,a,b,location_on):
    second=w.Material(code='SYN-GLOBAL-SECOND',name='合成第二物料',stock=21.005)
    w.db.session.add(second)
    w.db.session.flush()
    w.db.session.add(w.InOrderItem(in_order_id=order.id,material_id=second.id,quantity=1.005,price=0,amount=0))
    for warehouse,quantity,typ,ref in ((a,1.005,'in','in_order'),(a,10,'opening','material_initial'),
                                      (b,10,'opening','material_initial')):
        w.db.session.add(w.StockTransaction(material_id=second.id,warehouse_id=warehouse.id,location=warehouse.name,
            quantity=quantity,transaction_type=typ,reference_type=ref,
            reference_id=order.id if ref=='in_order' else second.id))
    if location_on:
        w.db.session.add_all([
            w.LocationInventory(material_id=second.id,warehouse_id=a.id,location='SAME',quantity=11.005),
            w.LocationInventory(material_id=second.id,warehouse_id=b.id,location='SAME',quantity=10)])
    w.db.session.commit()
    return second


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['later_global','later_dml'])
def test_real_multi_material_failure_rolls_back_the_entire_order(source_scene,location_on,mode):
    client,order,material,a,b=_scene(source_scene,'in',location_on,'raw')
    second=_second(order,a,b,location_on)
    if mode=='later_global':
        _other(second,b,-10.505,location_on)
    before=_business_state(material)
    hit=[]
    def fail_later_stock_update(_connection,_cursor,statement,parameters,_context,_executemany):
        if statement.lstrip().upper().startswith('UPDATE MATERIAL SET STOCK='):
            hit.append(parameters)
            if len(hit)==2:
                raise RuntimeError('owned synthetic later stock UPDATE failure')
    if mode=='later_dml':
        event.listen(w.db.engine,'before_cursor_execute',fail_later_stock_update)
    try:
        response=_post(client,order,'in')
    finally:
        if mode=='later_dml':
            event.remove(w.db.engine,'before_cursor_execute',fail_later_stock_update)
    _assert_rejected(response,'in')
    if mode=='later_dml':
        assert len(hit)==2,hit
    assert _business_state(material)==before
    assert order.status=='completed'
