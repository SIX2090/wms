"""订单下推、委外实收和销售来源行的合成 HTTP 回归。"""
from datetime import date

import pytest
import app as w
from tests import test_sales_audit_006_complete_remaining_check as sales
from tests.document_revision_client import document_post
from tests.test_bug_2026_08_16_001_subcontract_location_inventory import client
from tests.test_money_route_synthetic_20261109 import money_case
from tests.test_purchase_zero_price_routes_20261109 import purchase


@pytest.mark.parametrize('default_exists, selected, allowed', [
    (True, '', True), (False, '', False), (True, '未知仓', False),
])
def test_purchase_draft_warehouse_before_reservation(money_case, default_exists, selected, allowed):
    c = money_case
    w.Warehouse.query.update({w.Warehouse.is_default: False})
    warehouse = w.db.session.get(w.Warehouse, c.wh1)
    warehouse.is_default = default_exists
    w.set_system_setting('prefer_default_warehouse', '1')
    w.db.session.commit()
    order_id, line_id = purchase(c, 2)
    response = c.client.post(f'/purchase_order/{order_id}/create_in_order',
                             json={'warehouse': selected, 'items': [{'item_id': line_id, 'quantity': 2}]})
    w.db.session.expire_all()
    line = w.db.session.get(w.PurchaseOrderItem, line_id)
    if allowed:
        assert response.json['status'] == 'success', response.json
        draft = w.db.session.get(w.InOrder, response.json['id'])
        assert draft.warehouse == warehouse.name and line.received_quantity == 2
    else:
        assert response.status_code == 400 and '仓库' in response.json['msg']
        assert line.received_quantity == 0 and w.InOrder.query.count() == 0


def test_purchase_push_honors_selected_warehouse_id(money_case):
    c = money_case
    order_id, line_id = purchase(c, 2)
    response = c.client.post(f'/purchase_order/{order_id}/create_in_order',
                             json={'warehouse_id': c.wh2, 'items': [{'item_id': line_id, 'quantity': 2}]})
    assert response.json['status'] == 'success', response.json
    draft = w.db.session.get(w.InOrder, response.json['id'])
    assert draft.warehouse == w.db.session.get(w.Warehouse, c.wh2).name


def test_linked_sales_copy_and_legacy_remaining(client):
    with w.app.app_context():
        sales._reset_db()
        seed = sales._seed_base()
        order, line = sales._make_confirmed_order(seed['cust'], seed['mat'], 10, 'SO-FLOW')
        w.db.session.add(w.StockTransaction(material_id=seed['mat'].id, warehouse_id=seed['wh'].id,
                                           transaction_type='opening_stock', quantity=100))
        w.db.session.commit()
        c = sales._make_client()
        pushed = c.post(f'/sales/{order.id}/create_outbound', json={})
        assert pushed.json['status'] == 'success'
        outbound = w.db.session.get(w.OutOrder, pushed.json['id'])
        assert c.post(f'/out_order/{outbound.id}/complete?force=true').json['status'] == 'success'
        assert c.post(f'/out_order/{outbound.id}/copy').status_code == 409
        assert w.OutOrder.query.count() == 1
        legacy = sales._make_pending_outbound(order, line, seed['mat'], 10, 'LEGACY-COPY')
        legacy.source_sales_order_id = None
        legacy.items[0].source_sales_order_item_id = None
        legacy.purpose = outbound.purpose
        w.db.session.commit()
        assert c.post(f'/out_order/{legacy.id}/complete?force=true').json['status'] == 'error'
        w.db.session.expire_all()
        assert line.shipped_quantity == 10 and seed['mat'].stock == 90
        assert legacy.status == 'pending'


def test_is_detached_sales_copy(client):
    from services.warehouse_stock_service import apply_stock_delta
    with w.app.app_context():
        sales._reset_db()
        seed = sales._seed_base()
        order, line = sales._make_confirmed_order(seed['cust'], seed['mat'], 10, 'SO-HISTORY')
        w.db.session.add(w.StockTransaction(material_id=seed['mat'].id, warehouse_id=seed['wh'].id,
                                           transaction_type='opening_stock', quantity=100))
        w.db.session.commit()
        c = sales._make_client()
        pushed = c.post(f'/sales/{order.id}/create_outbound', json={})
        original = w.db.session.get(w.OutOrder, pushed.json['id'])
        assert c.post(f'/out_order/{original.id}/complete?force=true').json['status'] == 'success'
        legacy = sales._make_pending_outbound(order, line, seed['mat'], 10, 'HISTORICAL-COPY')
        legacy.source_sales_order_id = None
        legacy.items[0].source_sales_order_item_id = None
        legacy.purpose = original.purpose
        legacy.remark = f'由出库单 {original.order_no} 复制生成'
        legacy.status = 'completed'
        with w.app.test_request_context():
            ok, message = apply_stock_delta(seed['mat'], -10, transaction_type='out',
                                            reference_type='out_order', reference_id=legacy.id, warehouse=legacy.warehouse)
        assert ok, message
        w.db.session.commit()
        assert seed['mat'].stock == 80
        result = c.post(f'/out_order/{legacy.id}/revert')
        assert result.json['status'] == 'success', result.json
        w.db.session.expire_all()
        assert (seed['mat'].stock, line.shipped_quantity, original.status) == (90, 10, 'completed')


def test_edit_same_material_rows_keep_identity(client):
    with w.app.app_context():
        sales._reset_db()
        seed = sales._seed_base()
        order, first = sales._make_confirmed_order(seed['cust'], seed['mat'], 10, 'SO-ROWS')
        out = sales._make_pending_outbound(order, first, seed['mat'], 3, 'OUT-ROWS')
        second = w.SalesOrderItem(sales_order_id=order.id, material_id=seed['mat'].id, quantity=20)
        w.db.session.add(second)
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(out_order_id=out.id, material_id=seed['mat'].id, quantity=2,
                                        source_sales_order_item_id=second.id, price=10, amount=20))
        w.db.session.commit()
        c = sales._make_client()
        body = dict(order_id=out.id, date=str(date.today()), warehouse=seed['wh'].name,
                    business_type='销售出库', customer=seed['cust'].name,
                    items=[dict(code='M001', quantity=q, price=10) for q in (2, 3)])
        assert document_post(c, '/out_order/add', json=body).status_code == 409
        for row, source in zip(body['items'], (second, first)):
            row['source_sales_order_item_id'] = source.id
        assert document_post(c, '/out_order/add', json=body).json['status'] == 'success'
        w.db.session.expire_all()
        assert {row.source_sales_order_item_id: row.quantity for row in out.items} == {first.id: 3, second.id: 2}


def test_subcontract_receipt_balances(client):
    from types import SimpleNamespace as Row
    from services.subcontract_receipts import subcontract_receipt_balances
    order = Row(items=[Row(material_id=1, quantity=2), Row(material_id=1, quantity=3), Row(material_id=2, quantity=4)],
                receive_orders=[Row(status='completed', items=[Row(material_id=1, quantity=5)]),
                                Row(status='pending', items=[Row(material_id=2, quantity=4)])])
    assert subcontract_receipt_balances(order) == {1: (5, 5), 2: (4, 0)}


def test_refresh_subcontract_receipts(client):
    with w.app.app_context():
        order = w.SubcontractOrder.query.one()
        product = w.Material.query.filter_by(code='M-FG').one()
        w.db.session.add(w.SubcontractItem(subcontract_order_id=order.id, material_id=product.id,
                                           quantity=10, unit_id=product.unit_id))
        draft = w.SubcontractReceive(subcontract_order_id=order.id, receive_no='RECEIPT-DRAFT',
                                     warehouse=order.warehouse, status='pending')
        w.db.session.add(draft)
        w.db.session.flush()
        w.db.session.add(w.SubcontractReceiveItem(receive_id=draft.id, material_id=product.id, quantity=9))
        w.db.session.commit()
        order_id, draft_id = order.id, draft.id
    for code, qty in [('M-FG', 1), ('M-RAW', 15)]:
        result = client.post(f'/subcontract/{order_id}/receive', data=dict(material_code=code, quantity=qty, price=2))
        assert result.json['status'] == 'success'
    with w.app.app_context():
        assert w.db.session.get(w.SubcontractOrder, order_id).status == 'processing'
    page = client.get('/subcontract/progress')
    assert page.status_code == 200 and '实收 1.0 / 计划 10.0' in page.get_data(as_text=True)
    assert client.post(f'/subcontract_receive/{draft_id}/complete').json['status'] == 'success'
    with w.app.app_context():
        assert w.db.session.get(w.SubcontractOrder, order_id).status == 'completed'
    assert client.post(f'/subcontract_receive/{draft_id}/revert').json['status'] == 'success'
    with w.app.app_context():
        assert w.db.session.get(w.SubcontractOrder, order_id).status == 'processing'
        assert w.Material.query.filter_by(code='M-FG').one().stock == 1
