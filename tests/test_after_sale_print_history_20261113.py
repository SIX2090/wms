"""Owned-memory real print rendering, detail and Excel preserve historical zero."""
import io

from flask import template_rendered
from openpyxl import load_workbook
import pytest

from tests.test_after_sale_history_20261113 import history
from tests.test_money_route_synthetic_20261109 import money_case,unchanged_inventory


@pytest.mark.parametrize('header_amount',[0,None,9.99])
@pytest.mark.parametrize('line_amount',[0,4.02])
def test_real_print_uses_only_none_fallback_and_preserves_recorded_line(money_case,header_amount,line_amount):
    c=money_case;w=c.w
    oid,iid,cid,payload=history(c,amount=line_amount)
    order=w.db.session.get(w.AfterSaleOutOrder,oid)
    order.total_amount=header_amount;w.db.session.commit()
    captured=[]
    def record(sender,template,context,**extra):
        if template.name=='document_print.html':captured.append(context['doc'])
    with template_rendered.connected_to(record,w.app):
        response=c.client.get(f'/after_sale_out/{oid}/print')
    assert response.status_code==200 and len(captured)==1
    expected=line_amount if header_amount is None else header_amount
    assert captured[0]['total_amount']==expected
    assert dict(captured[0]['info'])['总金额']==f'{expected:.2f}'
    assert captured[0]['rows'][0]['amount']==line_amount
    assert captured[0]['rows'][0]['price']==3.5
    detail=c.client.get(f'/after_sale_out/{oid}')
    assert detail.status_code==200
    if header_amount==0:assert '<strong>¥0.00</strong>' in detail.get_data(as_text=True)
    response=c.client.get('/export/after_sale_out?search=ASO-SYN-HISTORY')
    assert response.status_code==200
    values=list(load_workbook(io.BytesIO(response.data),data_only=True).active.values)
    assert len(values)==2 and values[1][10:13]==(1.15,3.5,line_amount)
    w.db.session.expire_all()
    assert w.db.session.get(w.AfterSaleOutOrder,oid).total_amount==header_amount
    assert w.db.session.get(w.AfterSaleOutOrderItem,iid).amount==line_amount
    unchanged_inventory(c)
