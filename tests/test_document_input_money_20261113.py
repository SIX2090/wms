"""Owned-memory real route checks for actual front-end component intent."""
from decimal import Decimal

import pytest

from tests.document_revision_client import document_post
from tests.test_document_input_money_contract_20261113 import CASES,capture_input
from tests.test_money_route_synthetic_20261109 import money_case,unchanged_inventory
from tests.test_purchase_edit_history_20261113 import history as purchase_history,snapshot as purchase_snapshot
from tests.test_sales_edit_history_20261113 import history as sales_history,snapshot as sales_snapshot


@pytest.mark.parametrize('kind',['purchase','sales'])
@pytest.mark.parametrize('case',CASES)
def test_component_intent_display_matches_persisted_money(money_case,kind,case):
    c=money_case;w=c.w
    op,quantity,price,entered,default,amount,status=case
    if kind=='purchase':
        oid,iid,source_id,payload=purchase_history(c,amount=amount,quantity=quantity,price=price)
        line_model,order_model,snapshot=w.PurchaseOrderItem,w.PurchaseOrder,purchase_snapshot
        url='/purchase_order/save'
    else:
        oid,iid,payload=sales_history(c,amount=Decimal(str(amount)),quantity=quantity)
        line_model,order_model,snapshot=w.SalesOrderItem,w.SalesOrder,sales_snapshot
        w.db.session.get(line_model,iid).price=price
        url=f'/sales/{oid}/edit'
    w.db.session.get(w.Material,c.ids['material']).price=default
    w.db.session.commit()
    before=snapshot(c,oid)
    shown=capture_input(kind,case)
    for row in shown['items']:
        row['line_id']=iid if row['line_id'] is not None else None
        if kind=='purchase':row['material_id']=c.ids['material']
    payload['items']=shown['items']
    response=document_post(c.client,url,json=payload)
    assert response.status_code==status,response.json
    if status==400:
        assert snapshot(c,oid)==before
        assert shown['items'][0]['price']==''
    else:
        assert response.json['status']=='success',response.json
        w.db.session.expire_all()
        order=w.db.session.get(order_model,oid)
        for displayed,stored in zip(shown['shown'],sorted(order.items,key=lambda item:item.id)):
            assert Decimal(displayed['amount'])==Decimal(str(stored.amount))
            if kind=='sales':
                assert Decimal(displayed['untaxed'])==Decimal(str(stored.untaxed_amount))
                assert Decimal(displayed['tax'])==Decimal(str(stored.tax_amount))
        assert Decimal(shown['total'].lstrip('¥'))==Decimal(str(order.total_amount))
        original=w.db.session.get(line_model,iid)
        if op in ('metadata','new'):
            assert (original.quantity,original.price,float(original.amount))==(quantity,price,amount)
        if op=='quantity':assert original.price==price
        if op=='price':assert original.quantity==quantity
        if kind=='purchase':assert original.purchase_request_item_id==source_id
    unchanged_inventory(c)
