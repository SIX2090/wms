"""售后 history/identity/stock/report cases, only existing owned-memory fixture."""
from datetime import date
from decimal import Decimal
import io
import uuid

import pytest

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


def history(c,amount=4.02,quantity=1.15,price=3.5,total=9.99):
    w=c.w
    contract=w.Contract(contract_no='AS-SYN-C',project_name='合成售后工程')
    w.db.session.add(contract);w.db.session.flush()
    order=w.AfterSaleOutOrder(order_no='ASO-SYN-HISTORY',date=date.today(),customer='合成售后客户',
        customer_id=c.customer,warehouse=c.warehouse,location='',reason='合成售后',status='pending',
        operator_id=c.ids['user'],total_amount=total,remark='original header')
    w.db.session.add(order);w.db.session.flush()
    line=w.AfterSaleOutOrderItem(after_sale_out_order_id=order.id,material_id=c.ids['material'],
        quantity=quantity,price=price,amount=amount,contract_id=contract.id,contract_no=contract.contract_no,
        project_name=contract.project_name,remark='original line')
    w.db.session.add(line);w.db.session.commit()
    payload=dict(order_id=order.id,date=date.today().isoformat(),customer='合成售后客户',warehouse_id=c.wh1,
        reason='合成售后',remark='header note',items=[dict(line_id=line.id,code='B-M',quantity=str(quantity),
        price=str(price),remark='line note')])
    return order.id,line.id,contract.id,payload


def snapshot(c,oid):
    w=c.w;w.db.session.expire_all();order=w.db.session.get(w.AfterSaleOutOrder,oid)
    return order.total_amount,tuple(sorted((r.id,r.material_id,r.quantity,r.price,r.amount,
        r.contract_id,r.contract_no,r.project_name) for r in order.items))


@pytest.mark.parametrize('amount',[0,4.02,7.77])
@pytest.mark.parametrize('quantity',[1.15,.0001])
def test_note_only_save_preserves_history_amount_components_contract_and_identity(money_case,amount,quantity):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c,amount,quantity);before=snapshot(c,oid)
    page=c.client.get(f'/after_sale_out/{oid}/edit')
    assert page.status_code==200 and f'"line_id": {iid}' in page.get_data(as_text=True)
    payload['items'][0].update(saved_amount=999,amount=888,contract_no='FORGED',project_name='FORGED')
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200 and response.json['status']=='success',response.json
    assert snapshot(c,oid)==before
    assert w.db.session.get(w.AfterSaleOutOrderItem,iid).remark=='line note'
    assert w.db.session.get(w.AfterSaleOutOrder,oid).remark=='header note'
    unchanged_inventory(c)


@pytest.mark.parametrize('field,value,quantity,price,amount',[
    ('quantity','1.23',1.23,3.56789,4.39),('quantity','2.12345',2.12345,3.56789,7.58),
    ('price','0',1.2345,0,0)])
def test_explicit_financial_change_keeps_other_precision_contract_and_row_id(money_case,field,value,quantity,price,amount):
    c=money_case;oid,iid,cid,payload=history(c,7.77,1.2345,3.56789)
    payload['items'][0][field]=value
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==(amount,((iid,c.ids['material'],quantity,price,amount,cid,'AS-SYN-C','合成售后工程'),))
    unchanged_inventory(c)


@pytest.mark.parametrize('total,expected',[(0,0),(None,4.02)])
def test_zero_and_missing_header_have_distinct_semantics(money_case,total,expected):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c)
    w.db.session.get(w.AfterSaleOutOrder,oid).total_amount=total;w.db.session.commit()
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==(expected,((iid,c.ids['material'],1.15,3.5,4.02,cid,'AS-SYN-C','合成售后工程'),))
    unchanged_inventory(c)


@pytest.mark.parametrize('identity',[True,0,'1e1','9'*20,99999999])
def test_bad_line_identity_is_atomic(money_case,identity):
    c=money_case;oid,iid,cid,payload=history(c);before=snapshot(c,oid);payload['items'][0]['line_id']=identity
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_foreign_same_material_line_cannot_be_claimed_and_duplicate_is_rejected(money_case):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c);before=snapshot(c,oid)
    other=w.AfterSaleOutOrder(order_no='ASO-SYN-OTHER',warehouse=c.warehouse,status='pending',total_amount=5)
    w.db.session.add(other);w.db.session.flush()
    foreign=w.AfterSaleOutOrderItem(after_sale_out_order_id=other.id,material_id=c.ids['material'],quantity=1,price=5,amount=5)
    w.db.session.add(foreign);w.db.session.commit();other_id,fid=other.id,foreign.id
    other_before=snapshot(c,other_id);payload['items'][0]['line_id']=fid
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before and snapshot(c,other_id)==other_before
    payload['items'][0]['line_id']=iid;payload['items'].append(dict(payload['items'][0]))
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_active_push_real_source_still_refuses_ordinary_edit(money_case):
    c=money_case;w=c.w
    source=w.InOrder(order_no='IN-SYN-AFTER-PUSH',date=date.today(),business_type='其他入库',
        warehouse=c.warehouse,status='completed',operator_id=c.ids['user'])
    w.db.session.add(source);w.db.session.flush()
    line=w.InOrderItem(in_order_id=source.id,material_id=c.ids['material'],quantity=1,price=.5,amount=.5)
    w.db.session.add(line);w.db.session.commit()
    response=c.client.post(f'/in_order/{source.id}/push',json=dict(target_type='after_sale_out',
        request_id=uuid.uuid4().hex,reason='合成售后',customer_id=c.customer,items=[dict(source_item_id=line.id,quantity=1)]))
    assert response.status_code==200 and response.json['status']=='success',response.json
    oid=response.json['id'];before=snapshot(c,oid);iid=before[1][0][0]
    payload=dict(order_id=oid,warehouse_id=c.wh1,reason='只改备注',items=[dict(line_id=iid,code='B-M',quantity='1',price='.5')])
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==409 and '来源单' in response.json['msg'],response.json
    assert snapshot(c,oid)==before
    push=w.DocumentPushLine.query.one()
    assert (push.status,push.source_item_id,push.target_item_id)==('active',line.id,iid)
    unchanged_inventory(c)


def test_stale_revision_is_not_accepted(money_case):
    from tests.test_document_edit_conflicts import revision
    c=money_case;w=c.w;oid,iid,cid,payload=history(c)
    token=revision(c.client,f'/after_sale_out/{oid}')
    w.db.session.get(w.AfterSaleOutOrderItem,iid).remark='other synthetic edit';w.db.session.commit()
    before=snapshot(c,oid)
    response=c.client.post('/after_sale_out/add',json=payload,headers={'X-WMS-Document-Revision':token})
    assert response.status_code==409,response.json
    assert snapshot(c,oid)==before
    assert w.db.session.get(w.AfterSaleOutOrderItem,iid).remark=='other synthetic edit'
    unchanged_inventory(c)


def test_missing_revision_cannot_use_owned_line_id(money_case):
    c=money_case;oid,iid,cid,payload=history(c);before=snapshot(c,oid)
    response=c.client.post('/after_sale_out/add',json=payload)
    assert response.status_code==409,response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_later_invalid_row_rolls_back_header_line_and_money(money_case):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c);before=snapshot(c,oid)
    payload['items'][0]['quantity']='2';payload['items'].append(dict(line_id=None,code='B-M',quantity='0',price='1'))
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before
    assert w.db.session.get(w.AfterSaleOutOrder,oid).remark=='original header'
    assert w.db.session.get(w.AfterSaleOutOrderItem,iid).remark=='original line'
    unchanged_inventory(c)


def test_copy_reprices_new_document_and_metadata_edit_keeps_inherited_contract(money_case):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c);before=snapshot(c,oid)
    response=c.client.post(f'/after_sale_out/{oid}/copy')
    assert response.status_code==200 and response.json['status']=='success',response.json
    copied_id=response.json['id'];assert copied_id!=oid
    copied=snapshot(c,copied_id);copied_iid=copied[1][0][0]
    assert copied[0]==4.03 and copied[1][0][4:]==(4.03,cid,'AS-SYN-C','合成售后工程')
    payload['order_id']=copied_id;payload['items'][0]['line_id']=copied_iid
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,copied_id)==copied and snapshot(c,oid)==before
    unchanged_inventory(c)


def test_legacy_no_ids_still_explicitly_replaces_and_reprices(money_case):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c);old=w.db.session.get(w.AfterSaleOutOrderItem,iid)
    del payload['items'][0]['line_id']
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200,response.json
    result=snapshot(c,oid);row=w.db.session.get(w.AfterSaleOutOrderItem,result[1][0][0])
    assert row is not old  # SQLite may reuse a deleted integer primary key.
    assert (row.quantity,row.price,row.amount,row.contract_id)==(1.15,3.5,4.03,None)
    assert result[0]==4.03;unchanged_inventory(c)


def assert_stock_scope(c,global_quantity,warehouse_quantity,locations_enabled):
    w=c.w
    assert w.db.session.get(w.Material,c.ids['material']).stock==global_quantity
    rows=w.LocationInventory.query.order_by(w.LocationInventory.warehouse_id).with_entities(
        w.LocationInventory.warehouse_id,w.LocationInventory.quantity).all()
    assert rows==[(c.wh1,warehouse_quantity if locations_enabled else 5),(c.wh2,5)]
    assert w.normalize_stock_quantity(sum(t.quantity for t in w.StockTransaction.query.all()))==global_quantity
    warehouse=w.db.session.get(w.Warehouse,c.wh1)
    assert w.get_warehouse_stock_quantities(warehouse)[c.ids['material']]==warehouse_quantity


@pytest.mark.parametrize('locations_enabled',[False,True])
def test_complete_revert_metadata_recomplete_keep_money_and_stock_scope_and_report(money_case,locations_enabled):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c)
    w.set_system_setting('location_management_enabled','1' if locations_enabled else '0')
    location=c.warehouse if locations_enabled else ''
    w.db.session.get(w.AfterSaleOutOrder,oid).location=location;w.db.session.commit()
    payload['location']=location;before=snapshot(c,oid)
    response=c.client.post(f'/after_sale_out/{oid}/complete')
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==before;assert_stock_scope(c,8.85,3.85,locations_enabled)
    count=w.StockTransaction.query.count()
    assert c.client.post(f'/after_sale_out/{oid}/complete').status_code==400
    assert w.StockTransaction.query.count()==count
    response=c.client.post(f'/after_sale_out/{oid}/revert')
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==before;assert_stock_scope(c,10,5,locations_enabled)
    count=w.StockTransaction.query.count()
    assert c.client.post(f'/after_sale_out/{oid}/revert').status_code==400
    assert w.StockTransaction.query.count()==count
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==before
    response=c.client.post(f'/after_sale_out/{oid}/complete')
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==before;assert_stock_scope(c,8.85,3.85,locations_enabled)
    txns=w.StockTransaction.query.filter_by(reference_type='after_sale_out_order',reference_id=oid).all()
    assert len(txns)==3
    assert w.normalize_stock_quantity(sum(t.quantity for t in txns))==-1.15
    prices=w._monthly_txn_price_map(txns)
    assert all(Decimal(str(prices[t.id]*1.15)).quantize(Decimal('.01'))==Decimal('4.02') for t in txns)
    _,rows,_=w._build_warehouse_monthly_report(dict(warehouse_id=c.wh1,warehouse=c.warehouse,
        start_month=date.today().strftime('%Y-%m'),end_month=date.today().strftime('%Y-%m'),material_code='B-M',hide_zero=False))
    assert len(rows)==1
    # 月报既定口径按流水正负分入/出；两次完成及一次回冲分别入各方向。
    assert rows[0]['out_quantity']==2.3
    assert rows[0]['out_amount']==pytest.approx(8.04,rel=0,abs=1e-9)
    assert rows[0]['in_quantity']==6.15
    assert rows[0]['in_amount']==pytest.approx(6.52,rel=0,abs=1e-9)
    assert rows[0]['ending_quantity']==3.85


def test_export_and_print_consume_recorded_amount_after_note_save(money_case,monkeypatch):
    from openpyxl import load_workbook
    c=money_case;w=c.w;oid,iid,cid,payload=history(c)
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200,response.json
    response=c.client.get('/export/after_sale_out?search=ASO-SYN-HISTORY')
    assert response.status_code==200
    values=list(load_workbook(io.BytesIO(response.data),data_only=True).active.values)
    assert len(values)==2 and values[1][10:13]==(1.15,3.5,4.02)
    captured=[]
    monkeypatch.setattr(w,'_render_generic_document_print',lambda data:captured.append(data) or w.jsonify({'status':'success'}))
    response=c.client.get(f'/after_sale_out/{oid}/print')
    assert response.status_code==200 and len(captured)==1
    assert captured[0]['rows'][0]['amount']==4.02
    unchanged_inventory(c)


def test_new_document_cannot_claim_an_old_row(money_case):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c);before=snapshot(c,oid);payload['order_id']=None
    response=c.client.post('/after_sale_out/add',json=payload)
    assert response.status_code==400,response.json
    assert w.AfterSaleOutOrder.query.count()==1 and w.AfterSaleOutOrderItem.query.count()==1
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_completed_history_is_not_editable(money_case):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c)
    w.db.session.get(w.AfterSaleOutOrder,oid).status='completed';w.db.session.commit();before=snapshot(c,oid)
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_remove_old_add_new_and_change_material_are_explicit(money_case):
    c=money_case;w=c.w;oid,iid,cid,payload=history(c)
    other=w.Material(code='AS-SYN-NEW',name='合成另一物料',unit_id=c.ids['unit'],price=3,stock=0)
    w.db.session.add(other);w.db.session.commit();other_id=other.id
    before=snapshot(c,oid);payload['items'][0]['code']='AS-SYN-NEW'
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before
    payload['items'][0].update(line_id=None,quantity='2',price='0')
    response=document_post(c.client,'/after_sale_out/add',json=payload)
    assert response.status_code==200,response.json
    result=snapshot(c,oid);assert len(result[1])==1
    row=w.db.session.get(w.AfterSaleOutOrderItem,result[1][0][0])
    assert (row.material_id,row.quantity,row.price,row.amount,row.contract_id)==(other_id,2,0,0,None)
    assert w.db.session.get(w.Material,other_id).stock==0;unchanged_inventory(c)
