"""Actual database/API regression for repeated source rows, without production data."""
from types import SimpleNamespace

import pytest
import app as w


@pytest.fixture
def flow_case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setenv('WMS_THREE_LEDGER_ASSERT', '0')
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='flow-test', password_hash='fixture-only', role='admin', status='active')
        unit = w.Unit(code='EACH', name='个')
        box = w.Unit(code='BOX', name='箱')
        wh = w.Warehouse(code='WA', name='审计仓A', status='active', is_default=True)
        other = w.Warehouse(code='WB', name='审计仓B', status='active')
        supplier = w.Supplier(code='S1', name='审计供应商')
        customer = w.Customer(code='C1', name='审计客户')
        w.db.session.add_all([user, unit, box, wh, other, supplier, customer])
        w.db.session.flush()
        mat = w.Material(code='M1', name='审计物料', unit_id=unit.id, price=5, stock=100)
        w.db.session.add(mat)
        w.db.session.flush()
        w.db.session.add(w.StockTransaction(material_id=mat.id, quantity=100,
            transaction_type='opening', warehouse_id=wh.id, location=wh.name))
        w.db.session.commit()
        ids = dict(user=user.id, each=unit.id, box=box.id, wh=wh.id, other=other.id,
                   mat=mat.id, supplier=supplier.id, customer=customer.id)
    client = w.app.test_client()
    client.environ_base['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
    with client.session_transaction() as session:
        session['_user_id'] = str(ids['user'])
        session['_fresh'] = True
    yield client, ids
    with w.app.app_context():
        w.db.session.remove()
        w.db.drop_all()


def source_case(ids, mode):
    if mode == 'purchase_return':
        source = w.InOrder(order_no='SOURCE', business_type='采购入库', warehouse='审计仓A',
                           status='completed', supplier_id=ids['supplier'])
        w.db.session.add(source)
        w.db.session.flush()
        line = w.InOrderItem(in_order_id=source.id, material_id=ids['mat'], quantity=10, price=5, amount=50)
    else:
        source = w.SalesOrder(order_no='SOURCE', customer_id=ids['customer'], warehouse='审计仓A',
                             warehouse_id=ids['wh'], status='confirmed')
        w.db.session.add(source)
        w.db.session.flush()
        line = w.SalesOrderItem(sales_order_id=source.id, material_id=ids['mat'], quantity=10,
                               shipped_quantity=0 if mode == 'sale' else 10)
    w.db.session.add(line)
    w.db.session.commit()
    return source.id, line.id


@pytest.mark.parametrize('mode', ['sale', 'sales_return', 'purchase_return'])
@pytest.mark.parametrize('quantities,allowed', [([6, 6], False), ([4, 6], True)])
def test_source_limit_sums_rows(flow_case, mode, quantities, allowed):
    _, ids = flow_case
    with w.app.app_context():
        _, sid = source_case(ids, mode)
        field = 'source_in_order_item_id' if mode == 'purchase_return' else 'source_sales_order_item_id'
        doc = SimpleNamespace(items=[SimpleNamespace(quantity=q, **{field:sid}) for q in quantities])
        fn = {'sale':w.sales_outbound_remaining_check, 'sales_return':w.sales_return_remaining_check,
              'purchase_return':w.purchase_return_remaining_check}[mode]
        assert fn(doc)[0] is allowed


@pytest.mark.parametrize('mode', ['sale', 'sales_return', 'purchase_return'])
def test_same_material_different_source_lines_remain_independent(flow_case, mode):
    _, ids = flow_case
    with w.app.app_context():
        source_id, sid = source_case(ids, mode)
        if mode == 'purchase_return':
            line = w.InOrderItem(in_order_id=source_id, material_id=ids['mat'], quantity=10, price=5, amount=50)
        else:
            line = w.SalesOrderItem(sales_order_id=source_id, material_id=ids['mat'], quantity=10,
                                   shipped_quantity=0 if mode == 'sale' else 10)
        w.db.session.add(line)
        w.db.session.commit()
        field = 'source_in_order_item_id' if mode == 'purchase_return' else 'source_sales_order_item_id'
        doc = SimpleNamespace(items=[SimpleNamespace(quantity=6, **{field:source}) for source in [sid, line.id]])
        fn = {'sale':w.sales_outbound_remaining_check, 'sales_return':w.sales_return_remaining_check,
              'purchase_return':w.purchase_return_remaining_check}[mode]
        assert fn(doc)[0] is True


@pytest.mark.parametrize('mode', ['sale', 'sales_return', 'purchase_return'])
def test_save_rejects_duplicate_source_overflow(flow_case, mode):
    client, ids = flow_case
    with w.app.app_context():
        source_id, sid = source_case(ids, mode)
        if mode == 'sale':
            doc = w.OutOrder(order_no='EDIT', business_type='销售出库', warehouse='审计仓A',
                             status='pending', source_sales_order_id=source_id)
            w.db.session.add(doc)
            w.db.session.commit()
            oid = doc.id
    field = 'source_in_order_item_id' if mode == 'purchase_return' else 'source_sales_order_item_id'
    payload = dict(order_no='EDIT', warehouse='审计仓A',
                   items=[dict(code='M1', quantity=6, price=5, **{field:sid}) for _ in range(2)])
    if mode == 'sales_return':
        payload.update(business_type='销售退货入库', customer_id=ids['customer'], source_sales_order_id=source_id)
        url = '/in_order/add'
    else:
        url = '/out_order/add'
        payload.update(business_type='销售出库' if mode == 'sale' else '采购退货出库',
                       customer='审计客户' if mode == 'sale' else '审计供应商')
        if mode == 'sale':
            payload['order_id'] = oid
        else:
            payload['source_in_order_id'] = source_id
    response = client.post(url, json=payload)
    assert response.get_json()['status'] == 'error'
    with w.app.app_context():
        assert w.db.session.get(w.Material, ids['mat']).stock == 100
        if mode == 'sale':
            assert len(w.db.session.get(w.OutOrder, oid).items) == 0


@pytest.mark.parametrize('mode', ['sale', 'sales_return', 'purchase_return'])
@pytest.mark.parametrize('batch', [False, True])
def test_completion_blocks_legacy_split_overflow(flow_case, mode, batch):
    client, ids = flow_case
    with w.app.app_context():
        source_id, sid = source_case(ids, mode)
        if mode == 'sales_return':
            doc = w.InOrder(order_no='TARGET', business_type='销售退货入库', warehouse='审计仓A',
                            customer_id=ids['customer'], source_sales_order_id=source_id, status='pending')
            model, fk, prefix = w.InOrderItem, 'in_order_id', 'in_order'
        else:
            doc = w.OutOrder(order_no='TARGET', business_type='销售出库' if mode == 'sale' else '采购退货出库',
                             warehouse='审计仓A', status='pending')
            if mode == 'sale':
                doc.source_sales_order_id = source_id
            else:
                doc.source_in_order_id = source_id
            model, fk, prefix = w.OutOrderItem, 'out_order_id', 'out_order'
        w.db.session.add(doc)
        w.db.session.flush()
        source_field = 'source_in_order_item_id' if mode == 'purchase_return' else 'source_sales_order_item_id'
        for _ in range(2):
            w.db.session.add(model(material_id=ids['mat'], quantity=6, price=5, amount=30,
                                   **{fk:doc.id, source_field:sid}))
        w.db.session.commit()
        oid = doc.id
        txn_count = w.StockTransaction.query.count()
    url = f'/{prefix}/batch_complete' if batch else f'/{prefix}/{oid}/complete'
    response = client.post(url, json={'ids':[oid]})
    with w.app.app_context():
        model = w.InOrder if mode == 'sales_return' else w.OutOrder
        assert w.db.session.get(model, oid).status == 'pending'
        assert w.db.session.get(w.Material, ids['mat']).stock == 100
        assert w.StockTransaction.query.count() == txn_count
    assert '超过' in str(response.get_json())
