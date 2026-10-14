"""Isolated BOM editing, filtering, import/export and permission checks."""
import io
import json
import re

import pytest
from flask import g
from openpyxl import load_workbook
from werkzeug.security import generate_password_hash
from app import app, db, BOM, BOMItem, Material, MaterialCategory, Unit, User


@pytest.fixture
def bom_case(monkeypatch):
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    # Each request must load its user afresh, even while the fixture holds an app context.
    def refresh_fixture_user():
        g.pop('_login_user', None)
    hooks = dict(app.before_request_funcs)
    hooks[None] = [refresh_fixture_user, *hooks.get(None, [])]
    monkeypatch.setattr(app, 'before_request_funcs', hooks)
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        unit = Unit(code='B-U', name='个')
        category = MaterialCategory(code='B-C', name='测试分类')
        user = User(username='bom-audit', role='admin',
                    password_hash=generate_password_hash('fixture-only'),
                    must_change_password=False)
        db.session.add_all([unit, category, user])
        db.session.flush()
        material = Material(code='B-M', name='测试子件', spec='审计规格',
                            unit_id=unit.id, category_id=category.id, price=5, stock=10)
        bom = BOM(bom_no='BOM-AUDIT', product_code='B-P', product_name='审计产品',
                  version='V1', status='active', total_cost=10)
        db.session.add_all([material, bom])
        db.session.flush()
        db.session.add(BOMItem(bom_id=bom.id, material_id=material.id,
                              quantity=2, unit_id=unit.id, unit_cost=5, total_cost=10))
        db.session.commit()
        ids = {'bom': bom.id, 'material': material.id, 'unit': unit.id, 'user': user.id}
        client = app.test_client()
        client.environ_base['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        assert client.post('/login', data={'username':'bom-audit','password':'fixture-only'}).status_code == 302
        yield client, ids
        db.session.remove()


def payload(ids, **changes):
    data = {'order_id':ids['bom'], 'order_no':'BOM-AUDIT',
            'header':{'product_code':'B-P','product_name':'审计产品','version':'V1','status':'active'},
            'items':[{'code':'B-M','quantity':3,'unit_id':ids['unit'],'price':0}]}
    data.update(changes)
    return data


def test_bom_save_updates_existing_rows_and_preserves_zero_cost(bom_case):
    client, ids = bom_case
    response = client.post('/bom/save_table', json=payload(ids))
    assert response.status_code == 200
    db.session.remove()
    bom = db.session.get(BOM, ids['bom'])
    assert len(bom.items) == 1
    assert bom.items[0].quantity == 3 and bom.items[0].unit_cost == 0
    assert bom.total_cost == 0
    html = client.get(f"/bom/{ids['bom']}").get_data(as_text=True)
    items = json.loads(re.search(r'const existingItems = (.*?);', html).group(1))
    assert items[0]['price'] == 0


def test_bom_new_duplicate_number_does_not_overwrite_existing(bom_case):
    client, ids = bom_case
    response = client.post('/bom/save_table', json=payload(ids, order_id=None))
    assert response.status_code == 400
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).items[0].quantity == 2


@pytest.mark.parametrize('data', [[], {'header':[]}, {'header':{'product_code':3}, 'items':[{}]}])
def test_bom_malformed_payload_returns_chinese_validation_error(bom_case, data):
    client, _ = bom_case
    assert client.post('/bom/save_table', json=data).status_code == 400


@pytest.mark.parametrize('quantity', [0, -1, float('inf'), float('nan')])
def test_bom_invalid_quantity_never_changes_existing_rows(bom_case, quantity):
    client, ids = bom_case
    data = payload(ids)
    data['items'][0]['quantity'] = quantity
    assert client.post('/bom/save_table', json=data).status_code == 400
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).items[0].quantity == 2


def test_bom_cost_overflow_is_rejected_before_writing(bom_case):
    client, ids = bom_case
    data = payload(ids)
    data['items'][0].update(quantity=1e308, price=1e308)
    assert client.post('/bom/save_table', json=data).status_code == 400
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).total_cost == 10


def test_prepare_bom_items_rejects_missing_unit_before_writing(bom_case):
    client, ids = bom_case
    data = payload(ids)
    data['items'][0]['unit_id'] = 999999
    response = client.post('/bom/save_table', json=data)
    assert response.status_code == 400
    assert '单位' in response.get_json()['msg']
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).items[0].quantity == 2


def test_bom_add_item_uses_material_default_unit(bom_case):
    client, ids = bom_case
    response = client.post(f"/bom/{ids['bom']}/add_item",
                           data={'material_code':'B-M','quantity':'1'})
    assert response.status_code == 200
    db.session.remove()
    assert len(db.session.get(BOM, ids['bom']).items) == 2


def test_bom_stale_material_id_cannot_override_typed_code(bom_case):
    client, ids = bom_case
    data = payload(ids)
    data['items'][0].update(material_id=ids['material'], code='DIFFERENT')
    assert client.post('/bom/save_table', json=data).status_code == 400
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).items[0].quantity == 2


@pytest.mark.parametrize('action', ['add', 'delete'])
def test_bom_item_changes_rollback_when_cost_recalculation_fails(bom_case, monkeypatch, action):
    import app as app_module
    client, ids = bom_case
    item_id = db.session.get(BOM, ids['bom']).items[0].id
    def fail_cost(*args, **kwargs):
        raise RuntimeError('isolated cost failure')
    monkeypatch.setattr(app_module, 'calculate_bom_cost_value', fail_cost)
    if action == 'add':
        response = client.post(f"/bom/{ids['bom']}/add_item",
                               data={'material_code':'B-M','quantity':'1','unit_id':ids['unit']})
    else:
        response = client.post(f"/bom/{ids['bom']}/delete_item/{item_id}")
    assert response.status_code >= 400
    db.session.remove()
    items = db.session.get(BOM, ids['bom']).items
    assert len(items) == 1 and items[0].id == item_id


def test_bom_filters_and_export_match_child_material_search(bom_case):
    client, ids = bom_case
    for keyword in ('B-M', '审计规格', '审计产品'):
        assert 'BOM-AUDIT' in client.get('/bom', query_string={'search':keyword}).get_data(as_text=True)
    assert 'BOM-AUDIT' not in client.get('/bom?status=inactive').get_data(as_text=True)
    workbook = load_workbook(io.BytesIO(client.get('/bom/export?search=B-M').data))
    rows = list(workbook.active.values)
    assert len(rows) == 2 and rows[1][0] == 'BOM-AUDIT'
    assert len(list(load_workbook(io.BytesIO(client.get('/bom/export?search=无匹配审计').data)).active.values)) == 1


def test_bom_production_permission_is_enforced(bom_case):
    client, ids = bom_case
    user = db.session.get(User, ids['user'])
    user.role = 'warehouse'
    db.session.commit()
    assert client.get('/bom').status_code == 200
    assert client.post('/bom/save_table', json=payload(ids)).status_code == 403


def test_bom_list_uses_complete_editor_and_empty_table_spans_match(bom_case):
    client, ids = bom_case
    html = client.get('/bom').get_data(as_text=True)
    assert 'id="saveAllBtn"' not in html
    assert '/material/api/list' not in html
    assert f'href="/bom/{ids["bom"]}" target="_blank" rel="noopener"' in html
    for role in ('admin', 'warehouse'):
        user = db.session.get(User, ids['user'])
        user.role = role
        db.session.commit()
        html = client.get('/bom?status=inactive').get_data(as_text=True)
        table = html.split('<table id="bomTable"', 1)[1].split('</table>', 1)[0]
        count = len(re.findall(r'<th\b', table.split('</thead>', 1)[0]))
        assert f'colspan="{count}"' in table
