"""MATERIAL-MERGE-HUMAN-001: operator selection/confirmation, never production data."""
from pathlib import Path

import pytest
from tests import test_material_merge as legacy

app_module, db, Material = legacy.app_module, legacy.db, legacy.Material
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client():
    with app_module.app.app_context():
        assert db.engine.url.get_backend_name() == 'sqlite'
        assert db.engine.url.database in (None, '', ':memory:')
    return legacy._reset()


def pair(**kwargs):
    target = legacy._seed('102059', name='TeSys交流三级接触器', spec='LC1D25M7C', brand='施耐德', **kwargs)
    source = legacy._seed('102120', name='TeSys交流三极接触器', spec='LC1D25M7C', brand='施耐德', **kwargs)
    return target, source


def test_material_merge_preview_manual_review_shows_differences_without_mutation(client):
    target, source = pair(stock=2)
    response = client.post('/material/merge_preview', json={
        'source_code': '102120', 'target_code': '102059', 'manual_review': True}, headers=legacy.AJAX_HEADERS)
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['source']['name'] != data['target']['name']
    assert data['source']['id'] == source and data['target']['id'] == target
    assert data['stock_after'] == 4
    with app_module.app.app_context():
        assert Material.query.count() == 2
        assert db.session.get(Material, source).stock == 2


@pytest.mark.parametrize('confirm,identity', [(False, False), (False, True), (True, False)])
def test_merge_material_requires_manual_identity_and_execution_confirmations(client, confirm, identity):
    target, source = pair()
    response = client.post(f'/material/{source}/merge', json={
        'target_code': '102059', 'confirm': confirm, 'identity_confirmed': identity}, headers=legacy.AJAX_HEADERS)
    assert response.get_json()['status'] != 'success'
    with app_module.app.app_context():
        assert Material.query.count() == 2
        assert db.session.get(Material, source) is not None


@pytest.mark.parametrize('field,value', [('name', '人工确认名称'), ('spec', '人工确认规格'), ('brand', '人工确认品牌')])
def test_merge_material_human_can_confirm_attribute_differences(client, field, value):
    target, source = pair()
    with app_module.app.app_context():
        setattr(db.session.get(Material, source), field, value)
        db.session.get(Material, source).status = 'inactive'
        db.session.commit()
    response = client.post(f'/material/{source}/merge', json={
        'target_code': '102059', 'confirm': True, 'identity_confirmed': True}, headers=legacy.AJAX_HEADERS)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()['status'] == 'success'
    with app_module.app.app_context():
        assert db.session.get(Material, source) is None
        kept = db.session.get(Material, target)
        assert kept.name == 'TeSys交流三级接触器' and kept.spec == 'LC1D25M7C' and kept.brand == '施耐德'
        assert kept.status == 'active'
        from app import AIMaterialAlias
        assert AIMaterialAlias.query.filter_by(material_id=target).count() == 1


def test_merge_material_manual_confirm_does_not_bypass_unit_safety(client):
    from app import Unit
    a = legacy._seed('A', name='同一名称')
    b = legacy._seed('B', name='同一名称')
    with app_module.app.app_context():
        piece, box = Unit(code='PIECE', name='个'), Unit(code='BOX', name='箱')
        db.session.add_all([piece, box]); db.session.flush()
        db.session.get(Material, a).unit_id = piece.id
        db.session.get(Material, b).unit_id = box.id
        db.session.commit()
    response = client.post(f'/material/{b}/merge', json={
        'target_code': 'A', 'confirm': True, 'identity_confirmed': True}, headers=legacy.AJAX_HEADERS)
    assert response.status_code == 400
    assert '单位' in response.get_json()['msg']
    with app_module.app.app_context():
        assert Material.query.count() == 2


def test_merge_material_ledger_regression_rolls_back_before_commit(client, monkeypatch):
    target, source = pair()
    def regress(*args, **kwargs):
        db.session.get(Material, target).stock = 99
        db.session.delete(db.session.get(Material, source))
        return {'ledger_regressed': True}
    monkeypatch.setattr(app_module, 'merge_material_duplicates', regress)
    response = client.post(f'/material/{source}/merge', json={
        'target_code': '102059', 'confirm': True, 'identity_confirmed': True}, headers=legacy.AJAX_HEADERS)
    assert response.status_code == 400
    with app_module.app.app_context():
        assert Material.query.count() == 2
        assert db.session.get(Material, target).stock == 0


@pytest.mark.parametrize('locations', [False, True])
def test_merge_material_human_preserves_multiple_warehouses_and_legacy_nulls(client, locations):
    from app import Warehouse, LocationInventory, StockTransaction, set_system_setting
    target, source = pair()
    with app_module.app.app_context():
        set_system_setting('location_management_enabled', '1' if locations else '0')
        w1, w2 = Warehouse(code='WH1', name='仓1'), Warehouse(code='WH2', name='仓2')
        db.session.add_all([w1, w2]); db.session.flush()
        warehouse_ids = [w1.id, w2.id, None]
        for material_id, amounts in [(target, [2, 3, 1]), (source, [4, 5, 2])]:
            db.session.get(Material, material_id).stock = sum(amounts)
            for warehouse_id, amount in zip(warehouse_ids, amounts):
                db.session.add(LocationInventory(material_id=material_id, warehouse_id=warehouse_id, location='SAME', quantity=amount))
                db.session.add(StockTransaction(material_id=material_id, warehouse_id=warehouse_id, location='SAME', transaction_type='in', quantity=amount))
        db.session.commit()
    response = client.post(f'/material/{source}/merge', json={
        'target_code': '102059', 'confirm': True, 'identity_confirmed': True}, headers=legacy.AJAX_HEADERS)
    assert response.get_json()['status'] == 'success', response.get_json()
    with app_module.app.app_context():
        rows = LocationInventory.query.filter_by(material_id=target).all()
        assert {row.warehouse_id: row.quantity for row in rows} == dict(zip(warehouse_ids, [6, 8, 3]))
        txns = StockTransaction.query.filter_by(material_id=target).all()
        assert sum(row.quantity for row in rows) == sum(row.quantity for row in txns) == db.session.get(Material, target).stock == 17
        assert len(txns) == 6


def test_material_merge_candidates_pagination_search_and_inactive_selection(client):
    target, source = pair()
    with app_module.app.app_context():
        db.session.get(Material, source).status = 'inactive'
        for index in range(23):
            db.session.add(Material(code=f'OTHER-{index:02}', name='其它物料', spec='匹配规格', brand='匹配品牌'))
        db.session.commit()
    url = f'/material/merge_candidates?source_id={target}'
    first_response = client.get(url)
    assert first_response.status_code == 200
    page1 = first_response.get_json()
    page2 = client.get(url + '&page=2').get_json()
    assert page1['total'] == 24 and page1['total_pages'] == 2 and len(page1['data']) == 20
    assert len(page2['data']) == 4
    assert len({row['id'] for row in page1['data'] + page2['data']}) == 24
    match = client.get(url + '&kw=102120').get_json()
    assert match['total'] == 1 and match['data'][0]['status'] == 'inactive'
    assert match['data'][0]['id'] == source
    assert client.get(url + '&kw=匹配品牌').get_json()['total'] == 23
    assert client.get(url + '&kw=匹配规格').get_json()['total'] == 23
    assert client.get(url + '&kw=%25').get_json()['total'] == 0


def test_material_merge_modal_replaces_prompt_and_requires_explicit_selection():
    template = (ROOT / 'app/templates/material.html').read_text(encoding='utf-8')
    start = template.index('function mergeMaterialInto(')
    end = template.index('// ==================== 列设置', start)
    assert 'window.prompt' not in template[start:end]
    assert 'WMS.MaterialMerge.open' in template[start:end]
    assert 'id="mergeHumanConfirmed"' in template and 'id="toolbarMergeBtn"' in template
    assert 'js/material_merge.js' in template
