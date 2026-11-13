"""Real ORM cases: run only through existing owned-memory money_case fixture."""
from datetime import date

import pytest

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


def history(c,amount=4.02,quantity=1.2345,price=3.56789):
    w=c.w
    order=w.PurchaseRequest(request_no='PR-SYN-HISTORY',date=date.today(),status='pending',
        applicant='合成申请人',operator_id=c.ids['user'],total_amount=9.99,remark='original')
    w.db.session.add(order);w.db.session.flush()
    line=w.PurchaseRequestItem(purchase_request_id=order.id,material_id=c.ids['material'],
        material_code='B-M',material_name='合成物料',quantity=quantity,estimated_price=price or 0,
        estimated_amount=amount or 0,remark='original line')
    w.db.session.add(line);w.db.session.flush()
    line.estimated_price=price;line.estimated_amount=amount;w.db.session.commit()
    payload=dict(request_id=order.id,date=date.today().isoformat(),remark='header note',items=[
        dict(line_id=line.id,material_id=c.ids['material'],material_code='B-M',material_name='合成物料',
            quantity=str(quantity),estimated_price='' if price is None else str(price),remark='line note')])
    return order.id,line.id,payload


def snapshot(c,oid):
    w=c.w;w.db.session.expire_all();order=w.db.session.get(w.PurchaseRequest,oid)
    return order.total_amount,tuple(sorted((r.id,r.material_id,r.quantity,r.estimated_price,r.estimated_amount) for r in order.items))


@pytest.mark.parametrize('amount',[0,4.02,7.77])
@pytest.mark.parametrize('quantity',[1.2345,.0001])
def test_notes_preserve_history_precision_and_identity(money_case,amount,quantity):
    c=money_case;w=c.w;oid,iid,payload=history(c,amount,quantity);before=snapshot(c,oid)
    page=c.client.get(f'/purchase_request/{oid}/edit')
    assert page.status_code==200
    assert f'"line_id": {iid}' in page.get_data(as_text=True)
    payload['items'][0]['saved_amount']=999
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200 and response.json['status']=='success',response.json
    assert snapshot(c,oid)==before
    assert w.db.session.get(w.PurchaseRequestItem,iid).remark=='line note'
    assert w.db.session.get(w.PurchaseRequest,oid).remark=='header note'
    unchanged_inventory(c)


@pytest.mark.parametrize('field,value,quantity,price,amount',[
    ('quantity','1.23',1.23,3.56789,4.39),('quantity','2.12345',2.12345,3.56789,7.58),
    ('estimated_price','0',1.2345,0,0),('estimated_price','3.12345',1.2345,3.12345,3.86)])
def test_explicit_changes_keep_other_precision_and_existing_line(money_case,field,value,quantity,price,amount):
    c=money_case;oid,iid,payload=history(c);payload['items'][0][field]=value
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==(amount,((iid,c.ids['material'],quantity,price,amount),))
    unchanged_inventory(c)


@pytest.mark.parametrize('price,amount,quantity,entered,status',[
    (None,7.77,'1.2345','',200),(None,7.77,'2','',400),
    (None,0,'2','',200),(None,None,'2','',200),
    (None,7.77,'2','0',200),(None,7.77,'2','3.5',200)])
def test_nullable_optional_estimate_boundaries(money_case,price,amount,quantity,entered,status):
    c=money_case;oid,iid,payload=history(c,amount,price=price);before=snapshot(c,oid)
    payload['items'][0].update(quantity=quantity,estimated_price=entered)
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==status,response.json
    if status==400:
        assert '预估单价' in response.json['msg'];assert snapshot(c,oid)==before
    elif quantity=='1.2345':assert snapshot(c,oid)==before
    else:
        result=snapshot(c,oid);assert result[1][0][0]==iid
        assert result[1][0][2]==2
        assert result[1][0][4]==(7 if entered=='3.5' else 0)
    unchanged_inventory(c)


def test_missing_amount_only_is_backfilled(money_case):
    c=money_case;oid,iid,payload=history(c,None,1.15,3.5)
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==(9.99,((iid,c.ids['material'],1.15,3.5,4.03),))
    unchanged_inventory(c)


@pytest.mark.parametrize('value',[True,0,'1e2','9'*20,99999999])
def test_bad_or_foreign_ids_are_atomic(money_case,value):
    c=money_case;oid,iid,payload=history(c);before=snapshot(c,oid);payload['items'][0]['line_id']=value
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_duplicate_identity_is_atomic(money_case):
    c=money_case;oid,iid,payload=history(c);before=snapshot(c,oid)
    payload['items'].append(dict(payload['items'][0]))
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


@pytest.mark.parametrize('header_link',[True,False])
def test_downstream_purchase_header_or_line_reference_blocks_abnormal_pending_edit(money_case,header_link):
    c=money_case;w=c.w;oid,iid,payload=history(c)
    po=w.PurchaseOrder(order_no='PO-SYN-LINK',date=date.today(),status='pending',purchase_request_id=oid if header_link else None)
    w.db.session.add(po);w.db.session.flush()
    if not header_link:
        w.db.session.add(w.PurchaseOrderItem(purchase_order_id=po.id,purchase_request_item_id=iid,
            material_id=c.ids['material'],quantity=1,price=0,amount=0))
    w.db.session.commit();before=snapshot(c,oid)
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==400 and '下游采购单' in response.json['msg'],response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_legacy_without_ids_replaces_and_new_null_id_is_new_row(money_case):
    c=money_case;w=c.w;oid,iid,payload=history(c)
    old_line=w.db.session.get(w.PurchaseRequestItem,iid)
    del payload['items'][0]['line_id']
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200,response.json
    result=snapshot(c,oid);assert result[1][0][4]==4.4
    new_id=result[1][0][0];new_line=w.db.session.get(w.PurchaseRequestItem,new_id)
    assert new_line is not old_line  # SQLite may reuse the deleted integer primary key.
    payload['items'][0]['line_id']=None
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200,response.json
    result=snapshot(c,oid)
    assert w.db.session.get(w.PurchaseRequestItem,result[1][0][0]) is not new_line
    unchanged_inventory(c)


def test_name_only_legacy_material_compatibility_is_preserved(money_case):
    c=money_case;w=c.w;oid,iid,payload=history(c)
    line=w.db.session.get(w.PurchaseRequestItem,iid);line.material_id=None;line.material_code=''
    w.db.session.commit();before=snapshot(c,oid)
    payload['items'][0].update(material_id=None,material_code='',material_name='历史名称')
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


def test_actual_foreign_same_material_line_cannot_be_reassigned(money_case):
    c=money_case;w=c.w;oid,iid,payload=history(c);before=snapshot(c,oid)
    other=w.PurchaseRequest(request_no='PR-SYN-OTHER',date=date.today(),status='pending',total_amount=5)
    w.db.session.add(other);w.db.session.flush()
    foreign=w.PurchaseRequestItem(purchase_request_id=other.id,material_id=c.ids['material'],quantity=1,estimated_price=5,estimated_amount=5)
    w.db.session.add(foreign);w.db.session.commit();fid=foreign.id
    payload['items'][0]['line_id']=fid
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before
    assert w.db.session.get(w.PurchaseRequestItem,fid).purchase_request_id==other.id
    unchanged_inventory(c)


def test_missing_header_uses_preserved_row_values(money_case):
    c=money_case;w=c.w;oid,iid,payload=history(c,7.77)
    w.db.session.get(w.PurchaseRequest,oid).total_amount=None;w.db.session.commit()
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==(7.77,((iid,c.ids['material'],1.2345,3.56789,7.77),))
    unchanged_inventory(c)


def test_known_zero_header_is_preserved_when_only_notes_change(money_case):
    c=money_case;w=c.w;oid,iid,payload=history(c,7.77)
    w.db.session.get(w.PurchaseRequest,oid).total_amount=0;w.db.session.commit()
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==(0,((iid,c.ids['material'],1.2345,3.56789,7.77),))
    unchanged_inventory(c)


def test_later_invalid_new_line_rolls_back_earlier_metadata_and_removal(money_case):
    c=money_case;w=c.w;oid,iid,payload=history(c);before=snapshot(c,oid)
    payload['items'].append(dict(line_id=None,material_id=c.ids['material'],material_code='B-M',quantity='0',estimated_price='1'))
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==400,response.json
    assert snapshot(c,oid)==before
    assert w.db.session.get(w.PurchaseRequest,oid).remark=='original'
    assert w.db.session.get(w.PurchaseRequestItem,iid).remark=='original line'
    unchanged_inventory(c)


def test_new_document_cannot_take_existing_line_id(money_case):
    c=money_case;w=c.w;oid,iid,payload=history(c);before=snapshot(c,oid)
    payload.pop('request_id');count=w.PurchaseRequest.query.count()
    response=document_post(c.client,'/purchase_request/add',json=payload)
    assert response.status_code==400,response.json
    assert w.PurchaseRequest.query.count()==count
    assert snapshot(c,oid)==before;unchanged_inventory(c)
