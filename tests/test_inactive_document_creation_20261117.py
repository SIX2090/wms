"""Disabled master data cannot start new intent; historical inventory remains usable."""
from datetime import date, datetime

import pytest
import app as w


@pytest.fixture
def material_case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='synthetic-review', role='admin', password_hash='unused',
                      must_change_password=False)
        unit = w.Unit(code='PCS', name='件')
        wh = w.Warehouse(code='SYN-A', name='合成甲仓', status='active', is_default=True)
        dep = w.Department(code='SYN-DEP', name='合成部门', status='active')
        supplier = w.Supplier(code='SYN-SUP', name='合成供应商')
        customer = w.Customer(code='SYN-CUS', name='合成客户')
        w.db.session.add_all([user, unit, wh, dep, supplier, customer])
        w.db.session.flush()
        material = w.Material(code='SYN-DISABLED', name='合成停用物料', status='inactive',
                              unit_id=unit.id, stock=100, price=1)
        w.db.session.add(material)
        w.db.session.flush()
        from flask_login import login_user
        from services.warehouse_stock_service import apply_opening_balance
        with w.app.test_request_context('/'):
            login_user(user)
            ok, error = apply_opening_balance(material, 100, warehouse=wh.name)
            assert ok, error
        w.db.session.commit()
        ids = dict(user=user.id, unit=unit.id, warehouse=wh.id, department=dep.id,
                   supplier=supplier.id, customer=customer.id, material=material.id)
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(ids['user'])
        session['_fresh'] = True
    yield client, ids
    with w.app.app_context():
        w.db.session.remove()


def _payloads(ids):
    row = {'code': 'SYN-DISABLED', 'material_code': 'SYN-DISABLED',
           'quantity': 2, 'price': 1, 'unit_id': ids['unit']}
    header = {'warehouse_id': ids['warehouse'], 'warehouse': '合成甲仓'}
    return [
        ('/in_order/add', dict(header, business_type='采购入库', supplier_id=ids['supplier'], items=[row])),
        ('/out_order/add', dict(header, business_type='领料单', department_id=ids['department'], items=[row])),
        ('/out_order/add', dict(header, business_type='其他出库', items=[row])),
        ('/purchase_order/save', {'supplier_id': ids['supplier'], 'items': [row]}),
        ('/after_sale_out/add', dict(header, customer_id=ids['customer'], items=[row])),
        ('/requisition/save_table', {'header': header, 'items': [row]}),
        ('/mobile/api/scan_submit', dict(header, mode='in', code=row['code'], quantity=2)),
        ('/mobile/api/scan_submit', dict(header, mode='out', code=row['code'], quantity=2)),
        ('/mobile/api/scan_batch_draft', dict(header, mode='in', lines=[row])),
        ('/mobile/api/scan_batch_draft', dict(header, mode='out', lines=[row])),
    ]


@pytest.mark.parametrize('case', range(10))
def test_inactive_material_cannot_create_document(material_case, case):
    client, ids = material_case
    path, payload = _payloads(ids)[case]
    response = client.post(path, json=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.is_json, (path, response.status_code)
    result = response.get_json()
    assert result.get('status') == 'error', (path, response.status_code, result)
    assert '停用' in result.get('msg', result.get('message', '')), (path, result)
    with w.app.app_context():
        for model in (w.InOrder, w.OutOrder, w.PurchaseOrder, w.AfterSaleOutOrder,
                      w.ProductionRequisition):
            assert model.query.count() == 0, (path, model.__name__)
        assert w.StockTransaction.query.count() == 1
        assert w.db.session.get(w.Material, ids['material']).stock == 100


@pytest.mark.parametrize('status', ['active', None, ''])
def test_parse_api_lines_preserves_selectable_legacy_statuses(material_case, status):
    _, ids = material_case
    with w.app.app_context():
        material = w.db.session.get(w.Material, ids['material'])
        material.status = status
        w.db.session.commit()
        rows, error = w.parse_api_lines({'lines': [{'code': material.code, 'quantity': 2}]})
        assert error is None
        assert rows[0][0].id == material.id and rows[0][1] == 2


def test_parse_api_lines_rejects_inactive_material(material_case):
    with w.app.app_context():
        rows, error = w.parse_api_lines({'lines': [{'code': 'SYN-DISABLED', 'quantity': 2}]})
        assert rows is None and '停用' in error


def test_import_material_rejects_inactive_without_changing_archive(material_case):
    _, ids = material_case
    with w.app.app_context():
        with pytest.raises(ValueError, match='停用'):
            w._find_or_create_material('SYN-DISABLED', name='不能覆盖的名称', unit_name='新单位')
        assert w.db.session.get(w.Material, ids['material']).name == '合成停用物料'
        assert w.Unit.query.count() == 1


def test_inactive_history_can_still_be_viewed_and_reverted(material_case):
    client, ids = material_case
    with w.app.app_context():
        order = w.InOrder(order_no='SYN-HISTORY', date=date.today(), status='completed',
                          warehouse='合成甲仓', business_type='采购入库',
                          supplier_id=ids['supplier'], operator_id=ids['user'])
        w.db.session.add(order)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=order.id, material_id=ids['material'],
                                     quantity=2, price=1, amount=2))
        material = w.db.session.get(w.Material, ids['material'])
        from services.warehouse_stock_service import apply_stock_delta
        with w.app.test_request_context('/'):
            from flask_login import login_user
            login_user(w.db.session.get(w.User, ids['user']))
            ok, error = apply_stock_delta(material, 2, transaction_type='in', reference_type='in_order',
                                         reference_id=order.id, warehouse='合成甲仓')
            assert ok, error
        w.db.session.commit()
        order_id = order.id
    response = client.get(f'/in_order/{order_id}')
    assert response.status_code == 200 and 'SYN-DISABLED' in response.get_data(as_text=True)
    response = client.post(f'/in_order/{order_id}/revert', headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.get_json()['status'] == 'success', response.get_json()
    with w.app.app_context():
        assert w.db.session.get(w.Material, ids['material']).stock == 100
        assert w.db.session.get(w.InOrder, order_id).status == 'pending'


@pytest.mark.parametrize('business_type', ['销售出库', '领料单', '其他出库', '采购退货出库'])
def test_ledger_and_mobile_use_real_outbound_type(material_case, business_type):
    client, ids = material_case
    with w.app.app_context():
        order = w.OutOrder(order_no='SYN-OUT', date=date.today(), status='completed',
                           warehouse='合成甲仓', business_type=business_type,
                           operator_id=ids['user'])
        w.db.session.add(order)
        w.db.session.flush()
        w.db.session.add_all([
            w.StockTransaction(material_id=ids['material'], quantity=-2, transaction_type='out',
                               warehouse_id=ids['warehouse'], reference_type='out_order',
                               reference_id=order.id, created_at=datetime.now()),
            w.StockTransaction(material_id=ids['material'], quantity=2, transaction_type='revert_out',
                               warehouse_id=ids['warehouse'], reference_type='out_order',
                               reference_id=order.id, created_at=datetime.now()),
        ])
        w.db.session.commit()
        rows = w._collect_ledger_rows({'warehouse_id': ids['warehouse'], 'warehouse': '合成甲仓',
                                       'warehouse_code': 'SYN-A', 'material_id': ids['material']})
        flow = [row for row in rows if row.get('reference_no') == 'SYN-OUT']
        assert [row['reference_type'] for row in flow] == [business_type, business_type+'（反提交冲销）']
        assert [row['balance_quantity'] for row in flow] == [98, 100]
    response = client.get('/api/mobile/report/stock_ledger', query_string={
        'warehouse_code': 'SYN-A', 'material_code': 'SYN-DISABLED'})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()['data']
    assert [item['reference_type'] for item in data['items'] if item['reference_no'] == 'SYN-OUT'] == [business_type, business_type+'（反提交冲销）']


@pytest.mark.parametrize('case', [0, 1, 3, 4, 5])
def test_inactive_existing_line_preserved_but_not_duplicated(material_case, case):
    client, ids = material_case
    from tests.document_revision_client import document_post
    with w.app.app_context():
        models = {
            0: (w.InOrder, w.InOrderItem, 'in_order_id'),
            1: (w.OutOrder, w.OutOrderItem, 'out_order_id'),
            3: (w.PurchaseOrder, w.PurchaseOrderItem, 'purchase_order_id'),
            4: (w.AfterSaleOutOrder, w.AfterSaleOutOrderItem, 'after_sale_out_order_id'),
            5: (w.ProductionRequisition, w.ProductionRequisitionItem, 'requisition_id'),
        }
        model, line_model, foreign_key = models[case]
        fields = dict(order_no='SYN-OLD', req_no='SYN-OLD', status='pending', date=date.today(),
                      warehouse='合成甲仓', supplier_id=ids['supplier'], customer='合成客户',
                      customer_id=ids['customer'], operator_id=ids['user'],
                      department_id=ids['department'], business_type='采购入库' if case == 0 else '领料单')
        order = model(**{key: value for key, value in fields.items() if key in model.__table__.columns})
        w.db.session.add(order)
        w.db.session.flush()
        fields = {foreign_key: order.id, 'material_id': ids['material'],
                  'quantity': 2, 'price': 1, 'amount': 2, 'unit_id': ids['unit']}
        w.db.session.add(line_model(**{key: value for key, value in fields.items()
                                     if key in line_model.__table__.columns}))
        w.db.session.commit()
        order_id = order.id
    path, payload = _payloads(ids)[case]
    payload['order_id'] = order_id
    response = document_post(client, path, json=payload)
    assert response.status_code == 200 and response.get_json()['status'] == 'success', response.get_json()
    payload['items'] = payload['items'] * 2
    response = document_post(client, path, json=payload)
    assert response.get_json()['status'] == 'error' and '停用' in response.get_json()['msg'], response.get_json()
    with w.app.app_context():
        assert line_model.query.filter_by(**{foreign_key: order_id}).count() == 1
        assert w.db.session.get(w.Material, ids['material']).stock == 100


def test_home_alert_drilldown_uses_low_warehouse_even_when_global_stock_is_sufficient(material_case):
    client, ids = material_case
    from flask import template_rendered
    from flask_login import login_user
    from services.warehouse_stock_service import apply_opening_balance
    with w.app.app_context():
        material = w.db.session.get(w.Material, ids['material'])
        material.status, material.min_stock, material.reorder_point = 'active', 20, 50
        material.stock += 18
        warehouse = w.Warehouse(code='SYN-B', name='合成乙仓', status='active')
        w.db.session.add(warehouse)
        w.db.session.flush()
        with w.app.test_request_context('/'):
            login_user(w.db.session.get(w.User, ids['user']))
            ok, error = apply_opening_balance(material, 18, warehouse=warehouse.name)
            assert ok, error
        w.set_system_setting('inventory_alert_enabled', '1')
        w.db.session.commit()
        wid = warehouse.id
        assert material.stock == 118
    captured = []
    def capture(sender, template, context, **extra):
        captured.append((template.name, context))
    with template_rendered.connected_to(capture, w.app):
        home = client.get('/', query_string={'alert_warehouse_id': wid})
        assert home.status_code == 200
        assert f'/alert?warehouse_id={wid}' in home.get_data(as_text=True)
        listing = client.get('/alert', query_string={'warehouse_id': wid})
        assert listing.status_code == 200
    context = next(context for name, context in captured if name == 'alert.html')
    assert context['filters']['warehouse_id'] == wid
    assert context['current_warehouse'].name == '合成乙仓'
    assert [(row['code'], row['stock']) for row in context['alert_materials']] == [('SYN-DISABLED', 18)]
