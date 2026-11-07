"""A02: warehouse aliases never silently select or write another warehouse."""
import io
from datetime import datetime, timedelta

import pytest
from openpyxl import Workbook
from werkzeug.security import generate_password_hash

import app as w


@pytest.fixture
def state(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        assert w.db.engine.url.database == ':memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='namespace-admin', role='admin', must_change_password=False,
                      password_hash=generate_password_hash('synthetic-fixture-only'))
        first = w.Warehouse(code='N-A', name='甲仓', status='active', is_default=True)
        second = w.Warehouse(code='N-B', name='乙仓', status='active')
        unit = w.Unit(code='N-U', name='个')
        w.db.session.add_all([user, first, second, unit])
        w.db.session.flush()
        material = w.Material(code='N-M', name='合成物料', unit_id=unit.id, stock=0)
        w.db.session.add(material)
        w.db.session.commit()
        client = w.app.test_client()
        client.environ_base['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield client, first.id, second.id, material.id
        w.db.session.remove()


def legacy_collision(second_id, *, inactive=False):
    # Reproduce an already-existing historical record; never use ORM writes as
    # the new master-data contract or rewrite a real warehouse.
    w.db.session.connection().exec_driver_sql(
        'UPDATE warehouse SET name = ?, status = ? WHERE id = ?',
        ('N-A', 'inactive' if inactive else 'active', second_id))
    w.db.session.commit()


@pytest.mark.parametrize('code,name', [('N-C', 'N-A'), ('甲仓', '丙仓')])
def test_check_warehouse_namespace(state, code, name):
    client, *_ = state
    response = client.post('/warehouse/add', data={'code': code, 'name': name})
    assert response.status_code == 400
    assert response.get_json()['status'] == 'error'
    assert w.Warehouse.query.count() == 2
    assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('code,name', [('N-C', 'N-A'), ('甲仓', '丙仓')])
def test_edit_rejects_cross_field_aliases_without_renaming_documents(state, code, name):
    client, first_id, second_id, _ = state
    response = client.post(f'/warehouse/{second_id}/edit', data={'code': code, 'name': name})
    assert response.status_code == 400
    assert response.get_json()['status'] == 'error'
    assert w.db.session.get(w.Warehouse, first_id).name == '甲仓'
    assert w.db.session.get(w.Warehouse, second_id).name == '乙仓'


@pytest.mark.parametrize('code,name', [('N-C', 'N-A'), ('甲仓', '丙仓')])
def test_master_import_rejects_cross_field_aliases_atomically(state, code, name):
    client, *_ = state
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['仓库编码', '仓库名称'])
    sheet.append(['N-OK', '正常待导入仓'])
    sheet.append([code, name])
    stream = io.BytesIO()
    workbook.save(stream)
    stream.seek(0)
    response = client.post('/warehouse/import', data={'file': (stream, 'synthetic.xlsx')})
    assert response.status_code == 400
    assert response.get_json()['status'] == 'error'
    assert w.Warehouse.query.count() == 2
    assert w.Warehouse.query.filter_by(code='N-OK').first() is None


def test_validate_warehouse_namespace(state):
    """check_warehouse_namespace must validate both queued ORM producers."""
    w.db.session.add_all([
        w.Warehouse(code='PAIR', name='第三仓', status='active'),
        w.Warehouse(code='OTHER', name='PAIR', status='active'),
    ])
    with pytest.raises(ValueError, match='仓库'):
        w.db.session.flush()
    w.db.session.rollback()
    assert w.Warehouse.query.count() == 2


def test_self_alias_and_normal_update_remain_legal(state):
    client, first_id, _, _ = state
    response = client.post('/warehouse/add', data={'code': 'SELF', 'name': 'SELF'})
    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'
    response = client.post(f'/warehouse/{first_id}/edit', data={'code': 'N-A', 'name': '甲仓'})
    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'


@pytest.mark.parametrize('inactive', [False, True])
def test_ambiguous_legacy_text_is_rejected_before_active_filter(state, inactive):
    _, first_id, second_id, _ = state
    legacy_collision(second_id, inactive=inactive)
    assert w.resolve_active_inventory_warehouse('N-A') is None
    assert w.resolve_active_sales_warehouse('N-A') is None
    assert w.is_warehouse_active('N-A')[0] is False
    from ai.read_queries import _warehouse
    query_warehouse, query_error = _warehouse('查询N-A的库存')
    assert query_warehouse is None and query_error
    resolved, error = w.resolve_request_warehouse({'warehouse': 'N-A'})
    assert resolved is None
    assert '歧义' in error or '重名' in error
    with pytest.raises(ValueError, match='仓库'):
        w.resolve_inventory_warehouse_id('N-A')
    assert w.resolve_inventory_warehouse_id(first_id) == first_id
    assert w.resolve_inventory_warehouse_id(w.db.session.get(w.Warehouse, second_id)) == second_id
    exact, error = w.resolve_request_warehouse({'warehouse_code': 'N-A'})
    assert error is None and exact.id == first_id
    exact, error = w.resolve_request_warehouse({'warehouse_id': str(first_id)})
    assert error is None and exact.id == first_id


def test_ambiguous_stock_write_changes_no_global_or_warehouse_ledger(state):
    _, _, second_id, material_id = state
    legacy_collision(second_id)
    from services.warehouse_stock_service import apply_stock_delta
    material = w.db.session.get(w.Material, material_id)
    with w.app.test_request_context('/synthetic-only'):
        with pytest.raises(ValueError, match='仓库'):
            apply_stock_delta(material, 5, warehouse='N-A',
                              transaction_type='in', reference_type='synthetic', reference_id=1)
    w.db.session.expire_all()
    assert w.db.session.get(w.Material, material_id).stock == 0
    assert w.StockTransaction.query.count() == 0
    assert w.LocationInventory.query.count() == 0


def test_explicit_warehouse_objects_keep_precise_transaction_ids(state):
    _, first_id, second_id, material_id = state
    legacy_collision(second_id)
    from services.warehouse_stock_service import apply_stock_delta
    w.set_system_setting('location_management_enabled', '0')
    material = w.db.session.get(w.Material, material_id)
    with w.app.test_request_context('/synthetic-only'):
        apply_stock_delta(material, 7, warehouse=w.db.session.get(w.Warehouse, first_id),
                          transaction_type='in', reference_type='synthetic', reference_id=1)
        apply_stock_delta(material, 11, warehouse=w.db.session.get(w.Warehouse, second_id),
                          transaction_type='in', reference_type='synthetic', reference_id=2)
    w.db.session.commit()
    rows = w.StockTransaction.query.order_by(w.StockTransaction.id).all()
    assert [(row.warehouse_id, row.quantity) for row in rows] == [(first_id, 7), (second_id, 11)]
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, first_id))[material_id] == 7
    assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, second_id))[material_id] == 11
    assert w.db.session.get(w.Material, material_id).stock == 18


def test_legacy_create_helper_refuses_ambiguous_existing_alias(state):
    _, _, second_id, _ = state
    legacy_collision(second_id)
    with pytest.raises(ValueError, match='仓库'):
        w._find_or_create_warehouse('N-A')
    assert w.Warehouse.query.count() == 2


def test_default_seed_never_creates_a_cross_field_collision(state, monkeypatch):
    monkeypatch.setattr(w, 'DEFAULT_WAREHOUSES', [
        {'code': 'N-NEW', 'name': 'N-A', 'type': '合成默认仓'},
    ])
    with pytest.raises(ValueError, match='仓库'):
        w.ensure_default_warehouses()
    w.db.session.rollback()
    assert w.Warehouse.query.count() == 2


def test_catalog_reads_never_take_namespace_write_lock(state):
    from sqlalchemy import event
    client, first_id, _, _ = state
    statements = []
    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().upper())
    event.listen(w.db.engine, 'before_cursor_execute', capture)
    try:
        assert client.get(f'/warehouse/{first_id}').status_code == 200
        assert client.get('/warehouse/api/list').status_code == 200
    finally:
        event.remove(w.db.engine, 'before_cursor_execute', capture)
    assert statements
    assert not any(sql.startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for sql in statements)


def test_ai_and_print_consumers_refuse_ambiguous_alias(state):
    _, _, second_id, _ = state
    legacy_collision(second_id)
    with pytest.raises(ValueError, match='仓库'):
        w._ai_match_warehouse('N-A')
    with pytest.raises(ValueError, match='仓库'):
        w._ai_resolve_draft_warehouse(explicit='N-A')
    from routes.print_queue import _resolve_print_route
    with pytest.raises(ValueError, match='仓库'):
        _resolve_print_route('in_order', 'N-A')


def test_resolve_warehouse_text(state):
    from services.warehouse_identity import resolve_warehouse_text
    _, first_id, second_id, _ = state
    assert resolve_warehouse_text(' N-A ').id == first_id
    assert resolve_warehouse_text('乙仓').id == second_id
    assert resolve_warehouse_text('不存在') is None
    assert resolve_warehouse_text(None) is None
    legacy_collision(second_id, inactive=True)
    assert resolve_warehouse_text('N-A') is None
    with pytest.raises(ValueError, match='仓库'):
        resolve_warehouse_text('N-A', strict=True)


@pytest.mark.parametrize('locations', [False, True])
def test_warehouse_aliases(state, locations):
    _, first_id, second_id, material_id = state
    legacy_collision(second_id)
    w.set_system_setting('location_management_enabled', '1' if locations else '0')
    w.db.session.add(w.StockTransaction(material_id=material_id, warehouse_id=None,
                                       location='N-A', quantity=13, transaction_type='in',
                                       reference_type='', reference_id=0))
    if locations:
        w.db.session.add(w.LocationInventory(material_id=material_id,
                                             warehouse_id=None, location='N-A', quantity=13))
    w.db.session.add_all([
        w.InOrder(order_no='N-AMB', warehouse='N-A', business_type='其他入库', status='pending'),
        w.InOrder(order_no='N-FIRST', warehouse='甲仓', business_type='其他入库', status='pending'),
        w.InOrder(order_no='N-SECOND', warehouse='N-B', business_type='其他入库', status='pending'),
    ])
    w.db.session.get(w.Material, material_id).stock = 13
    w.db.session.commit()
    for warehouse_id in (first_id, second_id):
        warehouse = w.db.session.get(w.Warehouse, warehouse_id)
        assert w.get_warehouse_stock_quantities(warehouse).get(material_id, 0) == 0
        clause = w._warehouse_document_match_clause(w.InOrder.warehouse, warehouse=warehouse)
        assert [row.order_no for row in w.InOrder.query.filter(clause).all()] == [
            'N-FIRST' if warehouse_id == first_id else 'N-SECOND']
    assert w.StockTransaction.query.one().warehouse_id is None
    assert w.db.session.get(w.Material, material_id).stock == 13


def test_native_opening_refuses_ambiguous_text_before_any_document_or_stock_write(state):
    client, _, second_id, material_id = state
    legacy_collision(second_id)
    w.db.session.add(w.ApiToken(user_id=1, token=w.hash_access_token('namespace-fixture-token'),
                                expires_at=datetime.now() + timedelta(days=1)))
    w.db.session.commit()
    response = client.post('/api/opening_stock', headers={'Authorization': 'Bearer namespace-fixture-token'},
                           json={'warehouse_code': 'N-A', 'date': '2026-11-07',
                                 'lines': [{'material_code': 'N-M', 'quantity': 5}]})
    assert response.status_code == 400
    assert response.get_json()['status'] == 'error'
    assert w.OpeningStock.query.count() == 0
    assert w.OpeningStockDoc.query.count() == 0
    assert w.StockTransaction.query.count() == 0
    assert w.db.session.get(w.Material, material_id).stock == 0
