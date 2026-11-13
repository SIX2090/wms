"""Real WMS reconciliation request, only inside the verified isolated pytest job."""
from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

from flask import g, template_rendered  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app as w  # noqa: E402


@pytest.fixture
def reconciliation_scene(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        assert all(not row[2] for row in w.db.session.execute(text('PRAGMA database_list')))
        w.db.session.rollback()
        w.db.drop_all()
        w.db.create_all()
        def fresh_user():
            g.pop('_login_user', None)
        hooks = dict(w.app.before_request_funcs)
        hooks[None] = [fresh_user, *hooks.get(None, [])]
        monkeypatch.setattr(w.app, 'before_request_funcs', hooks)
        user = w.User(username='synthetic-reconciliation', password_hash='non-login-test-value',
                      role='admin', must_change_password=False)
        a = w.Warehouse(code='SYN-A', name='合成甲仓', status='active')
        b = w.Warehouse(code='SYN-B', name='合成乙仓', status='active')
        customer = w.Customer(code='SYN-C', name='合成客户')
        material = w.Material(code='SYN-M', name='合成物料', stock=0)
        w.db.session.add_all([user, a, b, customer, material])
        w.db.session.flush()
        order = w.SalesOrder(order_no='SYN-S', customer_id=customer.id, warehouse=a.name,
            warehouse_id=a.id, status='confirmed', shipment_status='shipped', total_amount=5,
            shipped_amount=5, untaxed_amount=5, tax_amount=0)
        w.db.session.add(order)
        w.db.session.flush()
        sources = []
        for qty in (3, 2):
            item = w.SalesOrderItem(sales_order_id=order.id, material_id=material.id,
                quantity=qty, shipped_quantity=qty, price=1, amount=qty, tax_rate=0,
                untaxed_amount=qty, tax_amount=0, tax_included_amount=qty)
            sources.append(item)
            w.db.session.add(item)
        outbound = w.OutOrder(order_no='SYN-O', source_sales_order_id=order.id,
            status='completed', business_type='销售出库', warehouse=a.name, total_amount=5)
        w.db.session.add(outbound)
        w.db.session.flush()
        for item in sources:
            w.db.session.add(w.OutOrderItem(out_order_id=outbound.id, material_id=material.id,
                source_sales_order_item_id=item.id, quantity=item.quantity, price=1, amount=item.quantity))
            w.db.session.add(w.StockTransaction(reference_type='out_order', reference_id=outbound.id,
                material_id=material.id, warehouse_id=a.id, transaction_type='out', quantity=-item.quantity))
        w.db.session.commit()
        client = w.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'], session['_fresh'] = str(user.id), True
        yield client, a.id, order.id
        w.db.session.remove()


def test_real_reconciliation_request_and_print_collector_count_split_material_once(reconciliation_scene):
    client, warehouse_id, order_id = reconciliation_scene
    contexts = []
    def record(_sender, _template=None, **kwargs):
        contexts.append(kwargs['context'])
    with template_rendered.connected_to(record, w.app):
        response = client.get('/sales/reconciliation', query_string={'warehouse_id': warehouse_id})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert contexts, 'The real report template must render'
    row = contexts[-1]['rows'][0]
    assert row['order'].id == order_id
    assert (row['shipped_qty'], row['completed_qty'], row['inventory_qty']) == (5, 5, 5)
    assert row['ok']
    from services.sales_report_print import collect_sales_report_print
    with w.app.test_request_context('/sales/reconciliation/print', query_string={'warehouse_id': warehouse_id}):
        data = collect_sales_report_print('reconciliation')
    assert data['rows'][0]['inventory_qty'] == 5
    assert data['rows'][0]['result'] == '通过'
    assert w.StockTransaction.query.count() == 2
    assert w.OutOrderItem.query.count() == 2
