"""Receipt failure and retry must leave one real native document, not a synthetic double-write."""
if __name__ == '__main__':
    raise SystemExit('安全阻断：请通过已核验隔离启动器的显式 pytest 清单运行本回归')

from sqlalchemy import event
from tests.test_money_route_synthetic_20261109 import money_case
from tests.test_native_atomic_receipts_20261109 import target, snapshot


def test_native_receipt_failure_then_retry_keeps_one_document(money_case):
    c=money_case;w=c.w;endpoint,body,headers=target(c,'inbound');before=snapshot(c)
    session=w.db.session()
    def refuse_receipt(active):
        if any(isinstance(row,w.MobileApiRequest) for row in (*active.new,*active.identity_map.values())):
            raise RuntimeError('synthetic receipt persistence failure')
    event.listen(session,'before_commit',refuse_receipt)
    try:
        failed=c.client.post(endpoint,json=body,headers=headers)
    finally:
        event.remove(session,'before_commit',refuse_receipt)
    assert failed.status_code in (500,503),failed.json
    assert snapshot(c)==before
    assert w.MobileApiRequest.query.count()==0
    recovered=c.client.post(endpoint,json=body,headers=headers)
    assert recovered.status_code==200 and recovered.json['success'] is True,recovered.json
    after=snapshot(c)
    replay=c.client.post(endpoint,json=body,headers=headers)
    assert replay.status_code==200 and replay.json==recovered.json,replay.json
    assert snapshot(c)==after
    assert w.InOrder.query.count()==w.MobileApiRequest.query.count()==1
    assert w.StockTransaction.query.count()==3
    assert w.db.session.get(w.Material,c.ids['material']).stock==11
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse,c.wh1))[c.ids['material']]==6
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse,c.wh2))[c.ids['material']]==5
    assert w.PrintJob.query.count()==0
