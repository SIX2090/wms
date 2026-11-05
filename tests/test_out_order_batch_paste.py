"""BUG-2026-10-22-012: missing outbound paste route, transactional draft-only repair."""
from datetime import date
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import app as app_module
from app import (Contract, Customer, InOrder, InOrderItem, LocationInventory, Material,
                 OperationLog, OutOrder, OutOrderItem, SalesOrder, SalesOrderItem,
                 StockTransaction, Unit, User, Warehouse, db, set_system_setting)


@pytest.fixture
def case(monkeypatch):
    app = app_module.app
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setitem(app.config, 'SESSION_COOKIE_SECURE', False)
    with app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.drop_all()
        db.create_all()
        user = User(username='paste-test', password_hash='fixture-only', role='warehouse', must_change_password=False)
        unit = Unit(code='PCS', name='个')
        wh1 = Warehouse(code='WHA', name='仓甲', status='active', is_default=True)
        wh2 = Warehouse(code='WHB', name='仓乙', status='active', is_default=False)
        whx = Warehouse(code='WHX', name='停用仓', status='inactive')
        contract = Contract(contract_no='C-PASTE', project_name='测试项目', status='active')
        db.session.add_all([user, unit, wh1, wh2, whx, contract])
        db.session.flush()
        m1 = Material(code='M1', name='物料甲', unit_id=unit.id, stock=40, price=2)
        m2 = Material(code='中文&A', name='物料乙', unit_id=unit.id, stock=30, price=3)
        db.session.add_all([m1, m2])
        db.session.flush()
        for material, qty in [(m1, 20), (m2, 15)]:
            for warehouse in [wh1, wh2]:
                db.session.add(LocationInventory(material_id=material.id, warehouse_id=warehouse.id, location='A01', quantity=qty))
                db.session.add(StockTransaction(material_id=material.id, warehouse_id=warehouse.id, transaction_type='in', quantity=qty, location=warehouse.name))
        order = OutOrder(order_no='OUT-PASTE', date=date.today(), business_type='领料单', warehouse=wh1.name, location='A01', status='pending', operator_id=user.id, contract_id=contract.id, contract_no=contract.contract_no, project_name=contract.project_name, total_amount=2)
        db.session.add(order)
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=order.id, material_id=m1.id, quantity=1, price=2, amount=2))
        db.session.commit()
        set_system_setting('location_management_enabled', '0')
        set_system_setting('prefer_default_warehouse', '1')
        client = app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield SimpleNamespace(app=app, client=client, order_id=order.id, user_id=user.id,
                              wh1=wh1.id, wh2=wh2.id, whx=whx.id, m1=m1.id, m2=m2.id,
                              contract_id=contract.id)
        db.session.remove()


def post(case, content='M1,2,4', **kwargs):
    headers = {'X-Requested-With': 'XMLHttpRequest', **kwargs.pop('headers', {})}
    return case.client.post(f'/out_order/{case.order_id}/batch_add_items', json={'content': content}, headers=headers, **kwargs)


def inventory_snapshot():
    return ([tuple(row) for row in db.session.query(Material.id, Material.stock).order_by(Material.id)],
            [tuple(row) for row in db.session.query(LocationInventory.id, LocationInventory.warehouse_id, LocationInventory.quantity).order_by(LocationInventory.id)],
            [tuple(row) for row in db.session.query(StockTransaction.id, StockTransaction.warehouse_id, StockTransaction.quantity).order_by(StockTransaction.id)])


def document_snapshot(case):
    order = db.session.get(OutOrder, case.order_id)
    return (order.warehouse, order.location, order.status, order.total_amount,
            [tuple(row) for row in db.session.query(OutOrderItem.id, OutOrderItem.material_id, OutOrderItem.quantity, OutOrderItem.price, OutOrderItem.amount).filter_by(out_order_id=order.id).order_by(OutOrderItem.id)], inventory_snapshot())


@pytest.mark.parametrize('kind', ['领料单', '其他出库', '生产出库', ''])
@pytest.mark.parametrize('location_enabled', [False, True])
def test_batch_add_out_order_items_supported_drafts(case, kind, location_enabled):
    order = db.session.get(OutOrder, case.order_id)
    order.business_type = kind
    db.session.commit()
    set_system_setting('location_management_enabled', '1' if location_enabled else '0')
    stock = inventory_snapshot()
    response = post(case, 'M1,2,4\n中文&A\t3\t\nM1,1,0')
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.json['status'] == 'success' and response.json['added'] == 3
    order = db.session.get(OutOrder, case.order_id)
    assert order.status == 'pending'
    assert len(order.items) == 4
    assert order.total_amount == pytest.approx(19)
    assert order.total_amount == pytest.approx(sum(item.amount for item in order.items))
    new = order.items[1:]
    assert [(item.quantity, item.price, item.amount) for item in new] == [(2, 4, 8), (3, 3, 9), (1, 0, 0)]
    assert all((item.contract_id, item.contract_no, item.project_name) == (case.contract_id, 'C-PASTE', '测试项目') for item in new)
    assert all(item.source_in_order_item_id is None and item.source_sales_order_item_id is None for item in new)
    assert inventory_snapshot() == stock
    assert OperationLog.query.filter_by(target_type='out_order', target_id=order.id, operation_type='批量添加出库明细').count() == 1


@pytest.mark.parametrize('content', ['', '  \n\t', 'M1', 'M1,1,2,extra', ',1,2', 'M1,0', 'M1,-1', 'M1,nan', 'M1,inf', 'M1,1,nan', 'M1,1,inf', 'M1,1,-1', 'M1,0.001', 'M1,1e308,1e308', 'M1,1,1e100', 'M1,2,4\nMISSING,1,1', 'M1,1\nM1,bad', 'M1,1\n' * 501])
def test_bad_row_leaves_entire_batch_unchanged(case, content):
    before = document_snapshot(case)
    response = post(case, content)
    assert response.status_code == 400, response.get_data(as_text=True)
    assert response.json['status'] == 'error'
    assert document_snapshot(case) == before
    assert OperationLog.query.count() == 0


@pytest.mark.parametrize('payload', [None, [], {}, {'content': None}, {'content': 123}, {'content': True}, {'content': 'x' * 100001}])
def test_pydantic_json_contract(case, payload):
    before = document_snapshot(case)
    response = case.client.post(f'/out_order/{case.order_id}/batch_add_items', json=payload)
    assert response.status_code == 400
    assert document_snapshot(case) == before


def test_form_payload_not_accepted(case):
    before = document_snapshot(case)
    response = case.client.post(f'/out_order/{case.order_id}/batch_add_items', data={'content': 'M1,1'})
    assert response.status_code == 400
    assert document_snapshot(case) == before


def test_multiple_extreme_lines_total_precision_is_atomic(case):
    before = document_snapshot(case)
    response = post(case, 'M1,1,1e25\n' * 20)
    assert response.status_code == 400
    assert '合计' in response.json['msg']
    assert document_snapshot(case) == before


def test_existing_total_precision_is_included(case):
    row = OutOrderItem.query.filter_by(out_order_id=case.order_id).one()
    row.quantity, row.price, row.amount = 1, 9e25, 9e25
    db.session.get(OutOrder, case.order_id).total_amount = 9e25
    db.session.commit()
    before = document_snapshot(case)
    response = post(case, 'M1,1,9e25')
    assert response.status_code == 400
    assert '合计' in response.json['msg']
    assert document_snapshot(case) == before


@pytest.mark.parametrize('warehouse', ['仓甲', '仓乙', 'WHA', 'WHB'])
def test_multiwarehouse_stock_stays_isolated(case, warehouse):
    order = db.session.get(OutOrder, case.order_id)
    order.warehouse = warehouse
    db.session.commit()
    stock = inventory_snapshot()
    response = post(case)
    assert response.status_code == 200
    order = db.session.get(OutOrder, case.order_id)
    assert order.warehouse == ('仓甲' if warehouse in ('仓甲', 'WHA') else '仓乙')
    assert inventory_snapshot() == stock


def test_legacy_blank_warehouse_uses_configured_default_only_on_success(case):
    order = db.session.get(OutOrder, case.order_id)
    order.warehouse = ''
    db.session.commit()
    before = document_snapshot(case)
    assert post(case, 'M1,1\nBAD,2').status_code == 400
    assert document_snapshot(case) == before
    assert post(case).status_code == 200
    assert db.session.get(OutOrder, case.order_id).warehouse == '仓甲'


@pytest.mark.parametrize('reason', ['no_default', 'auto_disabled', 'inactive', 'unknown', 'missing_location'])
def test_invalid_warehouse_or_location_never_writes(case, reason):
    order = db.session.get(OutOrder, case.order_id)
    if reason in ('no_default', 'auto_disabled'):
        order.warehouse = ''
        if reason == 'no_default':
            db.session.get(Warehouse, case.wh1).is_default = False
        else:
            set_system_setting('prefer_default_warehouse', '0')
    elif reason == 'inactive':
        order.warehouse = '停用仓'
    elif reason == 'unknown':
        order.warehouse = '不存在'
    else:
        order.location = ''
        set_system_setting('location_management_enabled', '1')
    db.session.commit()
    before = document_snapshot(case)
    assert post(case).status_code == 400
    assert document_snapshot(case) == before


@pytest.mark.parametrize('kind', ['采购退货出库', '销售出库', 'unsupported'])
def test_reject_source_sensitive_business_types(case, kind):
    db.session.get(OutOrder, case.order_id).business_type = kind
    db.session.commit()
    before = document_snapshot(case)
    response = post(case)
    assert response.status_code == 400
    assert '编辑' in response.json['msg']
    assert document_snapshot(case) == before


@pytest.mark.parametrize('source', ['sales_header', 'sales_line', 'purchase_header', 'purchase_line'])
def test_historical_misclassified_sources_still_rejected(case, source):
    order = db.session.get(OutOrder, case.order_id)
    if source.startswith('sales'):
        customer = Customer(code='CUST-PASTE', name='测试客户')
        db.session.add(customer)
        db.session.flush()
        sale = SalesOrder(order_no='SALE-PASTE', date=date.today(), status='draft', customer_id=customer.id)
        db.session.add(sale)
        db.session.flush()
        if source.endswith('header'):
            order.source_sales_order_id = sale.id
        else:
            line = SalesOrderItem(sales_order_id=sale.id, material_id=case.m1, quantity=1, price=2, amount=2)
            db.session.add(line)
            db.session.flush()
            order.items[0].source_sales_order_item_id = line.id
    else:
        inbound = InOrder(order_no='IN-PASTE', date=date.today(), status='completed', business_type='采购入库', warehouse='仓甲')
        db.session.add(inbound)
        db.session.flush()
        if source.endswith('header'):
            order.source_in_order_id = inbound.id
        else:
            line = InOrderItem(in_order_id=inbound.id, material_id=case.m1, quantity=1, price=2, amount=2)
            db.session.add(line)
            db.session.flush()
            order.items[0].source_in_order_item_id = line.id
    db.session.commit()
    before = document_snapshot(case)
    assert post(case).status_code == 400
    assert document_snapshot(case) == before


@pytest.mark.parametrize('role,expected', [('admin', 200), ('warehouse', 200), ('viewer', 403), ('purchase', 403), ('production', 403)])
def test_role_contract(case, role, expected):
    db.session.get(User, case.user_id).role = role
    db.session.commit()
    before = document_snapshot(case)
    response = post(case)
    assert response.status_code == expected
    if expected != 200:
        assert document_snapshot(case) == before


def test_requires_login_and_post(case):
    before = document_snapshot(case)
    assert case.client.get(f'/out_order/{case.order_id}/batch_add_items').status_code == 405
    from flask import g
    g.pop('_login_user', None)  # A separate client must not inherit this app-context login cache.
    assert case.app.test_client().post(f'/out_order/{case.order_id}/batch_add_items', json={'content': 'M1,1'}).status_code == 302
    assert document_snapshot(case) == before


def test_completed_cannot_add(case):
    db.session.get(OutOrder, case.order_id).status = 'completed'
    db.session.commit()
    before = document_snapshot(case)
    assert post(case).status_code == 400
    assert document_snapshot(case) == before


@pytest.mark.parametrize('point', ['flush', 'commit'])
def test_database_exception_rolls_back_every_line(case, monkeypatch, point):
    before = document_snapshot(case)
    with monkeypatch.context() as patch:
        def fail(*args, **kwargs):
            raise RuntimeError('fixture database error')
        patch.setattr(db.session, point, fail)
        response = post(case, 'M1,2,4\n中文&A,3,2')
    assert response.status_code == 500
    assert response.json['status'] == 'error'
    assert document_snapshot(case) == before


def test_state_race_guard(case, monkeypatch):
    before = document_snapshot(case)
    monkeypatch.setattr(app_module, '_acquire_order_write_lock', lambda *args: (None, False))
    assert post(case).status_code == 409
    assert document_snapshot(case) == before


def test_csrf_enforced_and_valid_token_works(case, monkeypatch):
    monkeypatch.setitem(case.app.config, 'WTF_CSRF_ENABLED', True)
    before = document_snapshot(case)
    assert post(case).status_code == 400
    assert document_snapshot(case) == before
    from itsdangerous import URLSafeTimedSerializer
    with case.client.session_transaction() as session:
        session['csrf_token'] = 'paste-fixture-csrf'
    token = URLSafeTimedSerializer(case.app.secret_key, salt='wtf-csrf-token').dumps('paste-fixture-csrf')
    assert post(case, headers={'X-CSRFToken': token}).status_code == 200
