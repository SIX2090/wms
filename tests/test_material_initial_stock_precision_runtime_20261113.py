"""Real material creation with one normalized initial quantity in isolated CI."""
from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

from flask import g  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app as w  # noqa: E402


@pytest.fixture
def initial_stock_scene(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
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
        user = w.User(username='synthetic-initial', password_hash='non-login-test-value',
                      role='admin', must_change_password=False)
        a = w.Warehouse(code='SYN-A', name='合成甲仓', status='active', is_default=True)
        b = w.Warehouse(code='SYN-B', name='合成乙仓', status='active')
        w.db.session.add_all([user, a, b])
        w.db.session.commit()
        client = w.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'], session['_fresh'] = str(user.id), True
        yield client, a, b
        w.db.session.remove()


@pytest.mark.parametrize('location_on', [False, True])
@pytest.mark.parametrize('raw,expected', [('1.005',1.01),('1.004',1),('0.004',0),
    ('0.005',0.01),('12.34',12.34),('99999999.99',99999999.99)])
def test_real_material_create_uses_one_initial_stock_in_three_ledgers(initial_stock_scene, raw, expected, location_on):
    client, a, b = initial_stock_scene
    w.set_system_setting('location_management_enabled', '1' if location_on else '0')
    w.db.session.commit()
    response = client.post('/material/add', data={
        'code':'SYN-INITIAL', 'name':'合成初始库存物料', 'spec':'S', 'stock':raw, 'price':'0'})
    assert response.status_code == 200 and response.get_json()['status'] == 'success', response.get_json()
    material = w.Material.query.filter_by(code='SYN-INITIAL').one()
    assert material.stock == expected
    txns = w.StockTransaction.query.filter_by(material_id=material.id).all()
    assert sum(row.quantity for row in txns) == expected
    assert len(txns) == int(expected > 0)
    assert all(row.warehouse_id == a.id for row in txns)
    locations = w.LocationInventory.query.filter_by(material_id=material.id).all()
    assert [(row.warehouse_id,row.quantity) for row in locations] == (
        [(a.id,expected)] if location_on and expected else [])
    assert w.StockTransaction.query.filter_by(warehouse_id=b.id).count() == 0


def test_real_material_without_default_keeps_normalized_quantity_unattributed(initial_stock_scene):
    client, a, _b = initial_stock_scene
    a.is_default = False
    w.set_system_setting('location_management_enabled', '1')
    w.db.session.commit()
    response = client.post('/material/add', data={
        'code':'SYN-UNKNOWN', 'name':'合成无默认仓物料', 'stock':'1.005', 'price':'0'})
    assert response.status_code == 200 and response.get_json()['status'] == 'success', response.get_json()
    material = w.Material.query.filter_by(code='SYN-UNKNOWN').one()
    assert material.stock == 1.01
    txn = w.StockTransaction.query.filter_by(material_id=material.id).one()
    assert txn.quantity == 1.01 and txn.warehouse_id is None
    assert w.LocationInventory.query.filter_by(material_id=material.id).count() == 0


def test_real_material_stock_above_bound_stays_rejected(initial_stock_scene):
    client, _a, _b = initial_stock_scene
    response = client.post('/material/add', data={
        'code':'SYN-INVALID', 'name':'合成超范围物料', 'stock':'99999999.991', 'price':'0'})
    assert response.get_json()['status'] == 'error'
    assert w.Material.query.filter_by(code='SYN-INVALID').count() == 0
    assert w.StockTransaction.query.count() == 0
