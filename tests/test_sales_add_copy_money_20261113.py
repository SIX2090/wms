"""Owned-memory real add route with captured actual Node input/copy/template payload."""
from datetime import date
from decimal import Decimal

import pytest

from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory
from tests.test_sales_add_copy_money_contract_20261113 import CASES, capture_add, rounded


@pytest.mark.parametrize('flow', ['input', 'copy', 'template'])
@pytest.mark.parametrize('quantity,price,default_price', CASES)
def test_sales_new_display_and_actual_saved_money_agree(money_case, flow, quantity, price, default_price):
    c=money_case
    w=c.w
    w.db.session.get(w.Material,c.ids['material']).price=default_price
    w.db.session.commit()
    shown=capture_add(flow,quantity,price,default_price)
    payload=dict(customer_id=c.customer,warehouse_id=c.wh1,date=date.today().isoformat(),items=shown['items'])
    response=c.client.post('/sales/add',json=payload)
    assert response.status_code==200 and response.json['status']=='success',response.json
    w.db.session.expire_all()
    order=w.db.session.get(w.SalesOrder,response.json['id'])
    assert order.status=='draft' and order.warehouse_id==c.wh1
    assert len(order.items)==len(shown['rows'])
    for sent,displayed,stored in zip(shown['items'],shown['rows'],sorted(order.items,key=lambda item:item.id)):
        qty=rounded(float(sent['quantity']))
        unit_price=rounded(float(sent['price']))
        amount=rounded(Decimal(str(qty))*Decimal(str(unit_price)))
        assert (stored.quantity,stored.price,float(stored.amount))==(qty,unit_price,amount)
        assert Decimal(displayed['amount'])==Decimal(str(stored.amount))
        assert Decimal(displayed['untaxed'])==Decimal(str(stored.untaxed_amount))
        assert Decimal(displayed['tax'])==Decimal(str(stored.tax_amount))
    assert Decimal(shown['total'])==Decimal(str(order.total_amount))
    unchanged_inventory(c)
