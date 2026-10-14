"""Return facts must retain enough completed source quantities after rollback."""
import pytest
import app as w
from tests.test_flow_source_limits import flow_case
from services.document_return_guard import sales_outbound_revert_check, purchase_inbound_revert_check


def make_sale(ids, quantities):
    source = w.SalesOrder(order_no='SO', customer_id=ids['customer'], warehouse='审计仓A',
                         warehouse_id=ids['wh'], status='confirmed')
    w.db.session.add(source)
    w.db.session.flush()
    line = w.SalesOrderItem(sales_order_id=source.id, material_id=ids['mat'], quantity=10,
                           shipped_quantity=0, price=5, amount=50)
    w.db.session.add(line)
    w.db.session.flush()
    out_ids = []
    for index, quantity in enumerate(quantities):
        out = w.OutOrder(order_no=f'OUT{index}', business_type='销售出库', warehouse='审计仓A',
                         source_sales_order_id=source.id, status='pending')
        w.db.session.add(out)
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(out_order_id=out.id, material_id=ids['mat'], quantity=quantity,
                                       price=5, amount=5*quantity, source_sales_order_item_id=line.id))
        out_ids.append(out.id)
    w.db.session.commit()
    return source.id, line.id, out_ids


def test_sales_outbound_revert_check_preserves_no_return_legacy_counter(flow_case):
    client, ids = flow_case
    with w.app.app_context():
        _, sid, out_ids = make_sale(ids, [10])
    assert client.post(f'/out_order/{out_ids[0]}/complete').get_json()['status'] == 'success'
    with w.app.app_context():
        w.db.session.get(w.SalesOrderItem, sid).shipped_quantity = 0
        w.db.session.commit()
    assert client.post(f'/out_order/{out_ids[0]}/revert').get_json()['status'] == 'success'
    with w.app.app_context():
        assert w.db.session.get(w.Material, ids['mat']).stock == 100


@pytest.mark.parametrize('quantities,allowed', [([10], False), ([6, 4], True), ([8, 2], False)])
def test_sales_outbound_revert_check(flow_case, quantities, allowed):
    client, ids = flow_case
    with w.app.app_context():
        source_id, sid, out_ids = make_sale(ids, quantities)
    for oid in out_ids:
        assert client.post(f'/out_order/{oid}/complete').get_json()['status'] == 'success'
    with w.app.app_context():
        ret = w.InOrder(order_no='RETURN', business_type='销售退货入库', warehouse='审计仓A',
                        customer_id=ids['customer'], source_sales_order_id=source_id, status='pending')
        w.db.session.add(ret)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=ret.id, material_id=ids['mat'], quantity=4,
                                       price=5, amount=20, source_sales_order_item_id=sid))
        w.db.session.commit()
        rid = ret.id
    assert client.post(f'/in_order/{rid}/complete').get_json()['status'] == 'success'
    with w.app.app_context():
        before = w.StockTransaction.query.count()
        assert sales_outbound_revert_check(w.db.session.get(w.OutOrder, out_ids[0]))[0] is allowed
    response = client.post(f'/out_order/{out_ids[0]}/revert').get_json()
    assert (response['status'] == 'success') is allowed
    with w.app.app_context():
        assert w.db.session.get(w.Material, ids['mat']).stock == (94 + quantities[0] if allowed else 94)
        assert w.db.session.get(w.OutOrder, out_ids[0]).status == ('pending' if allowed else 'completed')
        assert w.db.session.get(w.SalesOrderItem, sid).shipped_quantity == (10-quantities[0] if allowed else 10)
        assert w.db.session.get(w.InOrder, rid).status == 'completed'
        if not allowed:
            assert w.StockTransaction.query.count() == before
    if not allowed:
        assert client.post(f'/in_order/{rid}/revert').get_json()['status'] == 'success'
        assert client.post(f'/out_order/{out_ids[0]}/revert').get_json()['status'] == 'success'


@pytest.mark.parametrize('batch', [False, True])
def test_purchase_inbound_revert_check(flow_case, batch):
    client, ids = flow_case
    with w.app.app_context():
        source = w.InOrder(order_no='IN', business_type='采购入库', warehouse='审计仓A', status='pending', supplier_id=ids['supplier'])
        w.db.session.add(source)
        w.db.session.flush()
        line = w.InOrderItem(in_order_id=source.id, material_id=ids['mat'], quantity=10, price=5, amount=50)
        w.db.session.add(line)
        w.db.session.commit()
        oid, sid = source.id, line.id
    assert client.post(f'/in_order/{oid}/complete').get_json()['status'] == 'success'
    with w.app.app_context():
        ret = w.OutOrder(order_no='RETURN', business_type='采购退货出库', warehouse='审计仓A', status='pending')
        w.db.session.add(ret)
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(out_order_id=ret.id, material_id=ids['mat'], quantity=4,
                                       price=5, amount=20, source_in_order_item_id=sid))
        w.db.session.commit()
        rid = ret.id
    assert client.post(f'/out_order/{rid}/complete').get_json()['status'] == 'success'
    with w.app.app_context():
        before = w.StockTransaction.query.count()
        assert purchase_inbound_revert_check(w.db.session.get(w.InOrder, oid))[0] is False
    url = '/in_order/batch_revert' if batch else f'/in_order/{oid}/revert'
    response = client.post(url, json={'ids':[oid]}).get_json()
    assert '退货' in str(response)
    with w.app.app_context():
        assert w.db.session.get(w.InOrder, oid).status == 'completed'
        assert w.db.session.get(w.Material, ids['mat']).stock == 106
        assert w.StockTransaction.query.count() == before
    assert client.post(f'/out_order/{rid}/revert').get_json()['status'] == 'success'
    assert client.post(f'/in_order/{oid}/revert').get_json()['status'] == 'success'
