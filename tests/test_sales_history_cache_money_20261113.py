"""Actual owned-memory historical inactive line retains identity when clearing price."""
from decimal import Decimal

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case,unchanged_inventory
from tests.test_sales_edit_history_20261113 import history
from tests.test_sales_history_cache_money_contract_20261113 import capture_history_cache


def test_inactive_history_outside_choices_matches_visible_and_saved_default(money_case):
    c=money_case;w=c.w
    oid,iid,payload=history(c)
    original=w.db.session.get(w.SalesOrderItem,iid)
    original.price=0
    material=w.db.session.get(w.Material,c.ids['material'])
    material.status='inactive';material.price=3.5
    w.db.session.commit()
    shown=capture_history_cache()
    shown['items'][0]['line_id']=iid
    payload['items']=shown['items']
    response=document_post(c.client,f'/sales/{oid}/edit',json=payload)
    assert response.status_code==200 and response.json['status']=='success',response.json
    w.db.session.expire_all()
    line=w.db.session.get(w.SalesOrderItem,iid)
    assert (line.material_id,line.quantity,line.price,float(line.amount))==(c.ids['material'],1.2345,3.5,4.32)
    assert Decimal(shown['shown'][0]['amount'])==Decimal(str(line.amount))
    assert Decimal(shown['total'])==Decimal(str(w.db.session.get(w.SalesOrder,oid).total_amount))
    unchanged_inventory(c)
