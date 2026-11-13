"""Actual completed inbound requests; only verified isolated fresh memory runtime."""
import math

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
from sqlalchemy import event  # noqa: E402
import app as w  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402
from tests.test_recorded_order_quantity_runtime_20261113 import source_scene, _scene  # noqa: E402,F401


def _prepare(scene,location_on,*,quantity=1.005,recorded=1.005,empty=False):
    client,order,material,a,b=_scene(scene,'in',location_on,
        'historical_normalized' if recorded==1.01 else 'raw')
    row=w.InOrderItem.query.filter_by(in_order_id=order.id).one()
    row.quantity=quantity
    if empty:
        w.StockTransaction.query.filter_by(reference_type='in_order',reference_id=order.id).delete(synchronize_session=False)
        w.db.session.delete(row)
        material.stock=20
        if location_on:
            w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity=10
        row=None
    w.db.session.commit()
    return client,order,material,a,b,row


def _source(order,material,row=None,received=0):
    purchase=w.PurchaseOrder(order_no='SYN-COMPLETED-PO',status='approved')
    w.db.session.add(purchase)
    w.db.session.flush()
    source=w.PurchaseOrderItem(purchase_order_id=purchase.id,material_id=material.id,quantity=100,
        received_quantity=received,price=1,amount=100,contract_no='SOURCE-CONTRACT',project_name='SOURCE-PROJECT')
    w.db.session.add(source)
    w.db.session.flush()
    if row is not None:
        row.source_purchase_order_item_id=source.id
    if received==10:
        other=w.InOrder(order_no='SYN-COMPLETED-OTHER',status='pending',warehouse=order.warehouse)
        w.db.session.add(other)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=other.id,material_id=material.id,
            source_purchase_order_item_id=source.id,quantity=10,price=0,amount=0))
    w.db.session.commit()
    return source


def _state(order,material,source):
    w.db.session.expire_all()
    return (order.status,material.stock,source.received_quantity,order.total_amount,
        [(r.id,r.quantity,r.price,r.amount,r.remark,r.contract_no,r.source_purchase_order_item_id)
         for r in w.InOrderItem.query.filter_by(in_order_id=order.id).order_by(w.InOrderItem.id)],
        [(r.id,r.quantity,r.warehouse_id,r.reference_type,r.reference_id) for r in w.StockTransaction.query.order_by(w.StockTransaction.id)],
        [(r.id,r.quantity,r.location,r.warehouse_id) for r in w.LocationInventory.query.order_by(w.LocationInventory.id)],
        w.OperationAudit.query.count(),w.OperationLog.query.count(),
        [(r.id,r.status,r.pushed_quantity) for r in w.DocumentPushLine.query.order_by(w.DocumentPushLine.id)],
        source.purchase_order.status,[(r.id,r.quantity,r.source_in_order_item_id) for r in w.OutOrderItem.query.order_by(w.OutOrderItem.id)])


def _assert_stock(material,expected,location_on,b):
    assert material.stock==pytest.approx(expected,abs=1e-12,rel=0)
    assert math.fsum(r.quantity for r in w.StockTransaction.query.filter_by(material_id=material.id))==pytest.approx(expected,abs=1e-12,rel=0)
    if location_on:
        assert math.fsum(r.quantity for r in w.LocationInventory.query.filter_by(material_id=material.id))==pytest.approx(expected,abs=1e-12,rel=0)
    assert w.StockTransaction.query.filter_by(material_id=material.id,warehouse_id=b.id).one().quantity==10


def _post(client,order,payload):
    return document_post(client,f'/in_order/{order.id}/update_completed',json=payload)


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('linked,previous',[(False,0),(True,0),(True,10)])
@pytest.mark.parametrize('quantity,expected',[(1.005,1.01),(1.004,1.00),(0.004,0)])
def test_real_new_row_uses_one_quantity_for_line_money_stock_and_reservation(source_scene,location_on,linked,previous,quantity,expected):
    client,order,material,a,b,row=_prepare(source_scene,location_on,empty=True)
    source=_source(order,material,received=previous)
    before=_state(order,material,source)
    added={'is_new':True,'code':material.code,'quantity':quantity,'price':4}
    if linked:
        added['source_purchase_order_item_id']=source.id
    response=_post(client,order,{'items':[added]})
    payload=response.get_json()
    if not expected:
        assert response.status_code==400 and '两位' in payload['msg'],payload
        assert _state(order,material,source)==before
        return
    assert response.status_code==200 and payload['status']=='success',payload
    row=w.InOrderItem.query.filter_by(in_order_id=order.id).one()
    assert row.quantity==expected
    assert row.amount==pytest.approx(expected*4,abs=1e-12,rel=0)
    assert source.received_quantity-previous==pytest.approx(expected if linked else 0,abs=1e-12,rel=0)
    assert row.contract_no==('SOURCE-CONTRACT' if linked else None)
    assert row.project_name==('SOURCE-PROJECT' if linked else None)
    _assert_stock(material,20+expected,location_on,b)
    assert w.OperationAudit.query.filter_by(operation='update_completed_in_order',target_id=order.id).count()==1


NORMAL_CASES=[('modify',linked,quantity,expected) for linked in (False,True)
              for quantity,expected in ((1.005,1.01),(1.004,1),(0.004,0))]
NORMAL_CASES += [('delete',linked,0,0) for linked in (False,True)]


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode,linked,quantity,expected',NORMAL_CASES)
def test_real_normal_two_decimal_edit_delete_and_source_link_keep_existing_behavior(source_scene,location_on,mode,linked,quantity,expected):
    client,order,material,a,b,row=_prepare(source_scene,location_on,quantity=1.01,recorded=1.01)
    source=_source(order,material,row if linked else None,1.01 if linked else 0)
    before=_state(order,material,source)
    data={'deleted_items':[row.id]} if mode=='delete' else {'items':[{'id':row.id,'quantity':quantity,'price':4}]}
    response=_post(client,order,data)
    payload=response.get_json()
    if mode=='modify' and not expected:
        assert response.status_code==400 and payload['status']=='error',payload
        assert _state(order,material,source)==before
        return
    assert response.status_code==200 and payload['status']=='success',payload
    assert source.received_quantity==(expected if linked else 0)
    _assert_stock(material,20+expected,location_on,b)
    rows=w.InOrderItem.query.filter_by(in_order_id=order.id).all()
    if mode=='delete':
        assert not rows
    else:
        assert len(rows)==1 and rows[0].quantity==expected
        assert rows[0].amount==pytest.approx(expected*4,abs=1e-12,rel=0)


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('linked',[False,True])
@pytest.mark.parametrize('recorded',[1.005,1.01])
@pytest.mark.parametrize('mode',['delete','modify'])
def test_real_high_precision_history_cannot_be_guessed_from_document_net(source_scene,location_on,linked,recorded,mode):
    client,order,material,a,b,row=_prepare(source_scene,location_on,recorded=recorded)
    source=_source(order,material,row if linked else None,1.01 if linked else 0)
    before=_state(order,material,source)
    data={'deleted_items':[row.id]} if mode=='delete' else {'items':[{'id':row.id,'quantity':2,'price':0}]}
    response=_post(client,order,data)
    assert response.status_code==400 and '历史' in response.get_json()['msg'],response.get_json()
    assert _state(order,material,source)==before


EXTRA_CASES=['metadata_zero','metadata_amount','metadata_rounded','mixed_rollback','ambiguous_one','ambiguous_two',
             'invalid_metadata','dml_failure','duplicate_delete','duplicate_alias_delete','delete_and_modify','delete_and_modify_alias','repeat_modify',
             'counter_producer_bad','counter_modify_bad','counter_delete_bad','counter_producer_tail','counter_modify_tail','counter_delete_tail']


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',EXTRA_CASES)
def test_real_replay_history_metadata_and_failure_are_atomic(source_scene,location_on,mode):
    historical=mode.startswith('metadata_') or mode in ('ambiguous_one','ambiguous_two')
    client,order,material,a,b,row=_prepare(source_scene,location_on,
        quantity=1.005 if historical else 1.01,recorded=1.005 if historical else 1.01)
    source=_source(order,material,row,1.01)
    if mode.startswith('metadata_'):
        amount={'metadata_zero':0,'metadata_amount':7.77,'metadata_rounded':4.02}[mode]
        row.amount=amount
        row.contract_no='HIST-CONTRACT'
        w.db.session.commit()
        before=_state(order,material,source)
        response=_post(client,order,{'items':[{'id':row.id,'quantity':1.005,'price':0,'remark':'only remark'}]})
        assert response.status_code==200 and response.get_json()['status']=='success',response.get_json()
        assert row.quantity==1.005 and row.amount==amount and row.remark=='only remark'
        assert row.contract_no=='HIST-CONTRACT' and source.received_quantity==1.01
        assert material.stock==before[1] and w.StockTransaction.query.count()==3
        return
    if mode in ('mixed_rollback','ambiguous_one','ambiguous_two'):
        second=w.InOrderItem(in_order_id=order.id,material_id=material.id,quantity=1.005,price=0,amount=0,
            source_purchase_order_item_id=source.id)
        w.db.session.add(second)
        flow=w.StockTransaction.query.filter_by(reference_type='in_order',reference_id=order.id).one()
        if mode=='ambiguous_one':
            flow.quantity=1.00
            extra=1.01
        elif mode=='ambiguous_two':
            flow.quantity=1.01
            extra=1.00
        else:
            extra=1.005
        w.db.session.add(w.StockTransaction(material_id=material.id,warehouse_id=a.id,location=a.name,
            quantity=extra,transaction_type='in',reference_type='in_order',reference_id=order.id))
        material.stock=20+flow.quantity+extra
        if location_on:
            w.LocationInventory.query.filter_by(material_id=material.id,warehouse_id=a.id).one().quantity=10+flow.quantity+extra
        source.received_quantity=2.02
        if mode=='ambiguous_one':
            target=w.OutOrder(order_no='SYN-DOWNSTREAM',warehouse=a.name,status='pending',business_type='采购退货出库')
            w.db.session.add(target)
            w.db.session.flush()
            target_item=w.OutOrderItem(out_order_id=target.id,material_id=material.id,
                source_in_order_item_id=row.id,quantity=0.5,price=0,amount=0)
            w.db.session.add(target_item)
            w.db.session.flush()
            w.db.session.add(w.DocumentPushLine(source_document_type='in_order',source_document_id=order.id,
                source_document_no=order.order_no,source_item_id=row.id,target_document_type='out_order',
                target_document_id=target.id,target_document_no=target.order_no,target_item_id=target_item.id,
                pushed_quantity=0.5,status='active',request_id='synthetic-runtime-boundary',
                created_by=w.User.query.filter_by(username='synthetic-sources').one().id))
        w.db.session.commit()
        before=_state(order,material,source)
        ids=[row.id,second.id] if mode=='mixed_rollback' else [row.id]
        response=_post(client,order,{'deleted_items':ids})
        assert response.status_code==400 and '历史' in response.get_json()['msg'],response.get_json()
        assert _state(order,material,source)==before
        return
    if mode.startswith('counter_'):
        tail=mode.endswith('_tail')
        source.received_quantity=math.nextafter(1.01,float('inf')) if tail else 1.005
        w.db.session.commit()
        before=_state(order,material,source)
        if 'producer' in mode:
            data={'items':[{'is_new':True,'code':material.code,'quantity':1.01,'price':0,'source_purchase_order_item_id':source.id}]}
            expected=22.02
        elif 'delete' in mode:
            data={'deleted_items':[row.id]}
            expected=20
        else:
            data={'items':[{'id':row.id,'quantity':2,'price':0}]}
            expected=22
        response=_post(client,order,data)
        payload=response.get_json()
        if tail:
            assert response.status_code==200 and payload['status']=='success',payload
            _assert_stock(material,expected,location_on,b)
            assert source.received_quantity==pytest.approx(expected-20,abs=1e-12,rel=0)
        else:
            assert response.status_code==400 and '历史采购预留' in payload['msg'],payload
            assert _state(order,material,source)==before
        return
    changed={'id':row.id,'quantity':2,'price':0}
    data={'items':[changed]}
    if mode=='invalid_metadata':
        changed['expiry_date']='not-a-valid-date'
    elif mode=='duplicate_delete':
        data={'deleted_items':[row.id,row.id]}
    elif mode=='duplicate_alias_delete':
        data={'deleted_items':[row.id,str(row.id),row.id]}
    elif mode=='delete_and_modify':
        data={'deleted_items':[row.id],'items':[changed]}
    elif mode=='delete_and_modify_alias':
        changed['id']=str(row.id)
        data={'deleted_items':[row.id],'items':[changed]}
    elif mode=='repeat_modify':
        data={'items':[changed,{'id':row.id,'quantity':3,'price':0}]}
    before=_state(order,material,source)
    hit=[]
    def fail_update(_connection,_cursor,statement,_parameters,_context,_executemany):
        if statement.lstrip().upper().startswith('UPDATE MATERIAL'):
            hit.append(True)
            raise RuntimeError('owned synthetic completed inbound UPDATE failure')
    if mode=='dml_failure':
        event.listen(w.db.engine,'before_cursor_execute',fail_update)
    try:
        response=_post(client,order,data)
    finally:
        if mode=='dml_failure':
            event.remove(w.db.engine,'before_cursor_execute',fail_update)
    payload=response.get_json()
    if mode in ('duplicate_delete','duplicate_alias_delete'):
        assert response.status_code==200 and payload['status']=='success',payload
        _assert_stock(material,20,location_on,b)
        assert source.received_quantity==0
        before_repeat=_state(order,material,source)
        repeated=_post(client,order,data)
        assert repeated.status_code==200 and repeated.get_json()['status']=='success',repeated.get_json()
        assert _state(order,material,source)==before_repeat
    elif mode=='repeat_modify':
        assert response.status_code==200 and payload['status']=='success',payload
        _assert_stock(material,23,location_on,b)
        assert source.received_quantity==3 and row.quantity==3
    else:
        assert response.status_code==400 and payload['status']=='error',payload
        assert _state(order,material,source)==before
        if mode=='dml_failure':
            assert hit==[True]


# Additional ULP regressions; the original 88 cases above remain unchanged.
ULP_CASES = [('metadata', False, 0, -1), ('metadata', False, 0, 1), ('metadata', False, 4.02, -1), ('metadata', False, 4.02, 1), ('metadata', False, 7.77, -1), ('metadata', False, 7.77, 1), ('metadata', True, 0, -1), ('metadata', True, 0, 1), ('metadata', True, 4.02, -1), ('metadata', True, 4.02, 1), ('metadata', True, 7.77, -1), ('metadata', True, 7.77, 1), ('counter_metadata', True, 7.77, -1), ('counter_metadata', True, 7.77, 1), ('change', False, 0, 1), ('change', False, 4.02, 1), ('change', False, 7.77, 1), ('change', True, 0, 1), ('change', True, 4.02, 1), ('change', True, 7.77, 1), ('sequential', False, 7.77, 1), ('sequential', True, 7.77, 1), ('history', False, 7.77, 1), ('history', True, 7.77, 1)]
assert len(ULP_CASES)==24


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode,linked,amount,direction',ULP_CASES)
def test_real_float_representation_is_not_a_stock_edit(source_scene,location_on,mode,linked,amount,direction):
    old_qty=(1.005 if mode=='history' else 1.01 if mode=='change' else
             math.nextafter(1.01,float('inf') if direction>0 else 0))
    client,order,material,a,b,row=_prepare(source_scene,location_on,quantity=old_qty,recorded=1.01)
    row.price=2;row.amount=amount;row.contract_no='KEEP-CONTRACT';row.project_name='KEEP-PROJECT'
    w.db.session.commit()
    reserved=(math.nextafter(1.01,float('inf') if direction>0 else 0) if linked and mode in
              ('counter_metadata','change','sequential') else 1.01 if linked else 0)
    source=_source(order,material,row if linked else None,reserved)
    before=_state(order,material,source)
    items=[{'id':row.id,'quantity':1.01,'price':2,'remark':'only note'}]
    if mode=='change':items[0]['quantity']=1.02
    elif mode=='sequential':items.append({'id':str(row.id),'quantity':1.02,'price':2})
    response=_post(client,order,{'items':items})
    payload=response.get_json()
    if mode=='history':
        assert response.status_code==400 and '历史' in payload['msg'],payload
        assert _state(order,material,source)==before
    elif mode in ('change','sequential'):
        assert response.status_code==200 and payload['status']=='success',payload
        assert (row.quantity,row.price,row.amount)==(1.02,2,2.04)
        _assert_stock(material,21.02,location_on,b)
        assert source.received_quantity==(1.02 if linked else 0)
    else:
        assert response.status_code==200 and payload['status']=='success',payload
        assert (row.quantity,row.price,row.amount,row.remark)==(old_qty,2,amount,'only note')
        assert material.stock==before[1] and source.received_quantity==reserved
        assert w.StockTransaction.query.count()==3
        assert _state(order,material,source)[6]==before[6]
    assert (row.contract_no,row.project_name,row.source_purchase_order_item_id)==(
        'KEEP-CONTRACT','KEEP-PROJECT',source.id if linked else None)


# Header regressions: retain the original 136 cases above unchanged.
HEAD_CASES = [('metadata', 0, 0), ('metadata', 0, 4.02), ('metadata', 0, 7.77), ('metadata', 9.99, 0), ('metadata', 9.99, 4.02), ('metadata', 9.99, 7.77), ('ulp', 0, 4.02), ('ulp', 0, 7.77), ('ulp', 9.99, 4.02), ('ulp', 9.99, 7.77), ('missing', None, 4.02), ('missing', None, 7.77), ('price', 0, 4.02), ('price', 9.99, 4.02), ('quantity', 0, 7.77), ('quantity', 9.99, 7.77), ('add', 0, 7.77), ('add', 9.99, 7.77), ('delete', 0, 7.77), ('delete', 9.99, 7.77), ('netback', 0, 7.77), ('netback', 9.99, 7.77), ('invalid', 0, 7.77), ('invalid', 9.99, 7.77), ('late', 0, 7.77), ('late', 9.99, 7.77)]
assert len(HEAD_CASES)==26


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode,head,amount',HEAD_CASES)
def test_real_completed_header_only_changes_for_effective_finance(source_scene,location_on,mode,head,amount):
    quantity=math.nextafter(1.01,float('inf')) if mode=='ulp' else 1.01
    client,order,material,a,b,row=_prepare(source_scene,location_on,quantity=quantity,recorded=1.01)
    row.price=0;row.amount=amount;order.total_amount=head;w.db.session.commit()
    source=_source(order,material,row,1.01)
    before=_state(order,material,source)
    changed={'id':row.id,'quantity':1.01,'price':0,'remark':'note only'}
    data={'items':[changed]}
    if mode=='price':changed['price']=2
    elif mode=='quantity':changed['quantity']=2
    elif mode=='add':data={'items':[{'is_new':True,'code':material.code,'quantity':1.01,'price':2,'source_purchase_order_item_id':source.id}]}
    elif mode=='delete':data={'deleted_items':[row.id]}
    elif mode=='netback':data={'items':[{'id':row.id,'quantity':2,'price':0},changed]}
    elif mode=='invalid':
        foreign=w.InOrder(order_no='HEAD-FOREIGN',warehouse=b.name,status='pending')
        w.db.session.add(foreign);w.db.session.flush()
        foreign_row=w.InOrderItem(in_order_id=foreign.id,material_id=material.id,quantity=2,price=0,amount=0)
        w.db.session.add(foreign_row);w.db.session.commit()
        data['items'].extend([{'id':str(foreign_row.id),'quantity':3,'price':2},{'id':999999,'quantity':3,'price':2}])
        data['deleted_items']=[str(foreign_row.id),999999]
    elif mode=='late':
        changed['quantity']=2
        data['items'].append({'is_new':True,'code':material.code,'quantity':1.01,'price':0,'expiry_date':'invalid'})
    response=_post(client,order,data);payload=response.get_json()
    if mode=='late':
        assert response.status_code==400 and payload['status']=='error',payload
        assert _state(order,material,source)==before
        return
    assert response.status_code==200 and payload['status']=='success',payload
    if mode in ('metadata','ulp','invalid'):
        assert (order.total_amount,row.amount,row.quantity)==(head,amount,quantity)
        assert material.stock==before[1] and source.received_quantity==1.01
        assert w.StockTransaction.query.count()==3
        if mode=='invalid':assert (foreign_row.quantity,foreign_row.price,foreign_row.amount)==(2,0,0)
    elif mode=='missing':assert (order.total_amount,row.amount)==(amount,amount)
    elif mode=='price':assert (order.total_amount,row.amount)==(2.02,2.02)
    elif mode=='quantity':
        assert (order.total_amount,row.amount,row.quantity)==(0,0,2)
        _assert_stock(material,22,location_on,b);assert source.received_quantity==2
    elif mode=='delete':
        assert order.total_amount==0 and w.InOrderItem.query.filter_by(in_order_id=order.id).count()==0
        _assert_stock(material,20,location_on,b);assert source.received_quantity==0
    elif mode=='netback':
        assert (order.total_amount,row.amount,row.quantity)==(0,0,1.01)
        _assert_stock(material,21.01,location_on,b);assert source.received_quantity==1.01
    elif mode=='add':
        assert order.total_amount==9.79 and row.amount==7.77
        _assert_stock(material,22.02,location_on,b);assert source.received_quantity==2.02
        rows=w.InOrderItem.query.filter_by(in_order_id=order.id).order_by(w.InOrderItem.id).all()
        assert len(rows)==2 and [r.material_id for r in rows]==[material.id]*2
        order.total_amount=head;w.db.session.commit()
        response=_post(client,order,{'items':[{'id':r.id,'quantity':r.quantity,'price':r.price,'remark':'two same SKU notes'} for r in rows]})
        assert response.status_code==200 and response.get_json()['status']=='success',response.get_json()
        assert order.total_amount==head and [r.amount for r in rows]==[7.77,2.02]
