"""Unknown historical price input: only existing owned-memory real fixture runs this."""
from decimal import Decimal

import pytest

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory
from tests.test_purchase_request_history_20261113 import history as request_history, snapshot as request_snapshot
from tests.test_purchase_edit_history_20261113 import history as purchase_history, snapshot as purchase_snapshot
from tests.test_sales_edit_history_20261113 import history as sales_history, snapshot as sales_snapshot

DOMAINS=['request','purchase','sales']
INVALID=['abc','NaN','Infinity','-Infinity','-0.01',-1,True,False,[],{},['0']]


def setup_history(c,domain,*,amount=7.77,known_price=None):
    w=c.w
    if domain=='request':
        oid,iid,payload=request_history(c,amount,price=known_price)
        return oid,iid,payload,'/purchase_request/add','estimated_price',request_snapshot,w.PurchaseRequestItem
    if domain=='purchase':
        oid,iid,source,payload=purchase_history(c,amount,price=known_price)
        return oid,iid,payload,'/purchase_order/save','price',purchase_snapshot,w.PurchaseOrderItem
    oid,iid,payload=sales_history(c,Decimal(str(amount)))
    w.db.session.get(w.SalesOrderItem,iid).price=known_price;w.db.session.commit()
    payload['items'][0]['price']='' if known_price is None else str(known_price)
    return oid,iid,payload,f'/sales/{oid}/edit','price',sales_snapshot,w.SalesOrderItem


@pytest.mark.parametrize('domain',DOMAINS)
@pytest.mark.parametrize('quote',INVALID)
def test_unknown_price_invalid_input_after_quantity_change_is_atomic(money_case,domain,quote):
    c=money_case;oid,iid,payload,path,field,snapshot,model=setup_history(c,domain);before=snapshot(c,oid)
    payload['items'][0].update(quantity='2',**{field:quote})
    response=document_post(c.client,path,json=payload)
    assert response.status_code==400 and '单价' in response.json['msg'],response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


@pytest.mark.parametrize('domain',DOMAINS)
@pytest.mark.parametrize('quote',['abc','NaN',False])
def test_unknown_price_invalid_input_is_not_an_explicit_metadata_reprice(money_case,domain,quote):
    c=money_case;oid,iid,payload,path,field,snapshot,model=setup_history(c,domain);before=snapshot(c,oid)
    payload['items'][0][field]=quote
    response=document_post(c.client,path,json=payload)
    assert response.status_code==400 and '单价' in response.json['msg'],response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


@pytest.mark.parametrize('domain',DOMAINS)
@pytest.mark.parametrize('quote',['',' ','\t\n'])
def test_unknown_price_missing_text_preserves_metadata_only_history(money_case,domain,quote):
    c=money_case;oid,iid,payload,path,field,snapshot,model=setup_history(c,domain);before=snapshot(c,oid)
    payload['items'][0][field]=quote
    response=document_post(c.client,path,json=payload)
    assert response.status_code==200,response.json
    assert snapshot(c,oid)==before
    c.w.db.session.expire_all();line=c.w.db.session.get(model,iid)
    assert (line.estimated_price if domain=='request' else line.price) is None
    unchanged_inventory(c)


@pytest.mark.parametrize('domain',DOMAINS)
@pytest.mark.parametrize('quote',['',' '])
def test_unknown_nonzero_estimate_requires_quote_for_quantity_change(money_case,domain,quote):
    c=money_case;oid,iid,payload,path,field,snapshot,model=setup_history(c,domain);before=snapshot(c,oid)
    payload['items'][0].update(quantity='2',**{field:quote})
    response=document_post(c.client,path,json=payload)
    assert response.status_code==400 and '单价' in response.json['msg'],response.json
    assert snapshot(c,oid)==before;unchanged_inventory(c)


@pytest.mark.parametrize('domain',DOMAINS)
@pytest.mark.parametrize('quote',[0,'0','3.5'])
def test_unknown_price_accepts_explicit_numeric_zero_or_positive_quote(money_case,domain,quote):
    c=money_case;w=c.w;oid,iid,payload,path,field,snapshot,model=setup_history(c,domain)
    payload['items'][0].update(quantity='2',**{field:quote})
    response=document_post(c.client,path,json=payload)
    assert response.status_code==200,response.json
    w.db.session.expire_all();line=w.db.session.get(model,iid)
    assert line.quantity==2
    assert (line.estimated_price if domain=='request' else line.price)==float(quote)
    amount=line.estimated_amount if domain=='request' else line.amount
    assert Decimal(str(amount))==Decimal(str(quote))*2
    unchanged_inventory(c)


@pytest.mark.parametrize('amount',[0,None])
@pytest.mark.parametrize('quote',['',' '])
def test_unpriced_zero_request_remains_editable_without_quote(money_case,amount,quote):
    c=money_case;w=c.w;oid,iid,payload,path,field,snapshot,model=setup_history(c,'request',amount=amount)
    payload['items'][0].update(quantity='2',**{field:quote})
    response=document_post(c.client,path,json=payload)
    assert response.status_code==200,response.json
    w.db.session.expire_all();line=w.db.session.get(model,iid)
    assert (line.quantity,line.estimated_price,line.estimated_amount)==(2,None,0)
    unchanged_inventory(c)


@pytest.mark.parametrize('domain',DOMAINS)
def test_known_price_keeps_previous_legacy_input_policy(money_case,domain):
    c=money_case;oid,iid,payload,path,field,snapshot,model=setup_history(c,domain,known_price=3.5)
    payload['items'][0].update(quantity='2',**{field:'abc'})
    response=document_post(c.client,path,json=payload)
    assert response.status_code==200,response.json
    unchanged_inventory(c)
