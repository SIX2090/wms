"""Actual HTTP/ORM regressions, only via the existing owned memory fixture.

Never execute this file against an inherited database or an existing service.
"""
import io
import json
import re
import uuid
from decimal import Decimal

import pytest
from openpyxl import Workbook

from tests.document_revision_client import document_post
from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory


def seed(c, quantity=1.15, unit_cost=3.5, amount=4.02, total=9.99):
    w = c.w
    bom = w.db.session.get(w.BOM, c.ids['bom'])
    row = bom.items[0]
    row.quantity, row.unit_cost, row.total_cost = quantity, unit_cost, amount
    row.usage, row.remark = '原用途', '原行备注'
    bom.total_cost, bom.remark = total, '原头备注'
    w.db.session.commit()
    return row.id


def body(c):
    page = c.client.get('/bom/' + str(c.ids['bom']))
    assert page.status_code == 200
    text = page.get_data(as_text=True)
    token = re.search(r'<meta name="document-revision" content="([^"]+)"', text)
    assert token, 'BOM must use the existing signed document guard'
    items = json.loads(re.search(r'const existingItems = (.*?);', text).group(1))
    return {'order_id': c.ids['bom'], 'order_no': 'BOM-AUDIT',
            'header': {'product_code': 'B-P', 'product_name': '审计产品', 'version': 'V1',
                       'status': 'active', 'remark': '只改头备注'},
            'items': [{'line_id': r['line_id'], 'material_id': r['material_id'], 'code': r['code'],
                       'unit_id': r['unit_id'], 'quantity': r['quantity'], 'price': r['recorded_unit_cost'],
                       'usage': r['usage'], 'remark': '只改行备注'} for r in items]}, token.group(1)


def snapshot(c):
    c.w.db.session.remove()
    bom = c.w.db.session.get(c.w.BOM, c.ids['bom'])
    return (bom.product_code, bom.product_name, bom.version, bom.status, bom.remark, bom.total_cost,
            tuple(sorted((r.id, r.material_id, r.unit_id, r.quantity, r.unit_cost, r.total_cost,
                          r.usage, r.remark) for r in bom.items)))


def finance(c):
    s = snapshot(c)
    return s[5], tuple(r[:6] for r in s[6])


@pytest.mark.parametrize('quantity,unit_cost', [(1.15, 3.5), (1.2345, 1.2345), (.0001, 0)])
@pytest.mark.parametrize('amount', [0, 4.02, 7.77])
def test_bom_note_retains_known_history_and_row_identity(money_case, quantity, unit_cost, amount):
    c = money_case
    row_id = seed(c, quantity, unit_cost, amount)
    before = finance(c)
    data, token = body(c)
    data['items'][0].update(saved_amount=999, total_cost=888)
    response = c.client.post('/bom/save_table', json=data, headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 200 and response.json['status'] == 'success', response.json
    assert finance(c) == before
    row = c.w.db.session.get(c.w.BOMItem, row_id)
    assert row.remark == '只改行备注' and row.usage == '原用途'
    unchanged_inventory(c)


@pytest.mark.parametrize('field,value,expected_q,expected_price,expected_amount', [
    ('quantity', 1.23, 1.23, 1.2345, '1.52'),
    ('price', 1.23, 1.2345, 1.23, '1.52'),
    ('price', 0, 1.2345, 0, '0'),
])
def test_bom_explicit_finance_change_preserves_other_original_component(money_case, field, value, expected_q, expected_price, expected_amount):
    c = money_case
    ident = seed(c, 1.2345, 1.2345, 7.77)
    data, _ = body(c)
    data['items'][0][field] = value
    response = document_post(c.client, '/bom/save_table', json=data)
    assert response.status_code == 200, response.json
    c.w.db.session.remove()
    row = c.w.db.session.get(c.w.BOMItem, ident)
    assert (row.quantity, row.unit_cost) == (expected_q, expected_price)
    assert Decimal(str(row.total_cost)) == Decimal(expected_amount)
    assert Decimal(str(row.bom.total_cost)) == Decimal(expected_amount)
    unchanged_inventory(c)


@pytest.mark.parametrize('head', [0, None])
def test_bom_known_zero_header_and_missing_header_are_distinct(money_case, head):
    c = money_case
    seed(c, amount=7.77, total=0)
    bom = c.w.db.session.get(c.w.BOM, c.ids['bom'])
    bom.total_cost = head
    c.w.db.session.commit()
    data, _ = body(c)
    response = document_post(c.client, '/bom/save_table', json=data)
    assert response.status_code == 200, response.json
    assert finance(c)[0] == (0 if head == 0 else 7.77)


def test_bom_same_sku_lines_reorder_without_swapping_identity(money_case):
    c = money_case
    first = seed(c, amount=4.02)
    second = c.w.BOMItem(bom_id=c.ids['bom'], material_id=c.ids['material'], unit_id=c.ids['unit'],
                         quantity=2.3456, unit_cost=3.5, total_cost=7.77, remark='第二条')
    c.w.db.session.add(second)
    c.w.db.session.commit()
    second_id = second.id
    before = finance(c)
    data, _ = body(c)
    data['items'].reverse()
    for row in data['items']:
        row['remark'] = 'ID-' + str(row['line_id'])
    response = document_post(c.client, '/bom/save_table', json=data)
    assert response.status_code == 200, response.json
    assert finance(c) == before
    for ident in (first, second_id):
        assert c.w.db.session.get(c.w.BOMItem, ident).remark == 'ID-' + str(ident)


@pytest.mark.parametrize('invalid', ['duplicate', 'foreign', 'bad', 'changed_material'])
def test_bom_unowned_or_repeated_identity_is_atomic(money_case, invalid):
    c = money_case
    seed(c)
    other_material = c.w.Material(code='B-NEW', name='合成新子件', unit_id=c.ids['unit'], price=5)
    other_bom = c.w.BOM(bom_no='BOM-FOREIGN', product_code='F', product_name='另一合成BOM', status='active')
    c.w.db.session.add_all([other_material, other_bom])
    c.w.db.session.flush()
    foreign = c.w.BOMItem(bom_id=other_bom.id, material_id=c.ids['material'], unit_id=c.ids['unit'], quantity=1, unit_cost=1, total_cost=1)
    c.w.db.session.add(foreign)
    c.w.db.session.commit()
    foreign_id, material_id = foreign.id, other_material.id
    data, _ = body(c)
    if invalid == 'duplicate': data['items'].append(dict(data['items'][0]))
    elif invalid == 'foreign': data['items'][0]['line_id'] = foreign_id
    elif invalid == 'bad': data['items'][0]['line_id'] = True
    else: data['items'][0].update(material_id=material_id, code='B-NEW')
    before = snapshot(c)
    response = document_post(c.client, '/bom/save_table', json=data)
    assert response.status_code == 400, response.json
    assert snapshot(c) == before
    unchanged_inventory(c)


@pytest.mark.parametrize('path', ['save', 'header', 'add', 'delete'])
def test_bom_content_mutators_require_signed_page(money_case, path):
    c = money_case
    ident = seed(c)
    data, _ = body(c)
    target, kwargs = {
        'save': ('/bom/save_table', {'json': data}),
        'header': (f'/bom/{c.ids["bom"]}/update', {'json': {'remark': '不得写'}}),
        'add': (f'/bom/{c.ids["bom"]}/add_item', {'data': {'material_code': 'B-M', 'quantity': '1'}}),
        'delete': (f'/bom/{c.ids["bom"]}/delete_item/{ident}', {}),
    }[path]
    before = snapshot(c)
    response = c.client.post(target, **kwargs)
    assert response.status_code == 409 and response.json['code'] == 'DOCUMENT_REVISION_REQUIRED', response.json
    assert snapshot(c) == before


@pytest.mark.parametrize('mutation', ['line', 'header', 'recalculate'])
def test_bom_stale_signed_page_cannot_overwrite_new_snapshot(money_case, mutation):
    c = money_case
    ident = seed(c)
    data, token = body(c)
    if mutation == 'line':
        c.w.db.session.get(c.w.BOMItem, ident).quantity = 2
        c.w.db.session.commit()
    elif mutation == 'header':
        response = document_post(c.client, f'/bom/{c.ids["bom"]}/update', json={'remark': '另一编辑'})
        assert response.status_code == 200, response.json
    else:
        response = c.client.post(f'/bom/{c.ids["bom"]}/calculate_cost')
        assert response.status_code == 200, response.json
    before = snapshot(c)
    response = c.client.post('/bom/save_table', json=data, headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 409 and response.json['code'] == 'DOCUMENT_EDIT_CONFLICT', response.json
    assert snapshot(c) == before


@pytest.mark.parametrize('command', ['calculate_cost', 'delete', 'create_requisition'])
def test_bom_commands_fail_atomically_when_existing_short_lock_fails(money_case, monkeypatch, command):
    c = money_case
    seed(c)
    before = snapshot(c)
    monkeypatch.setattr(c.w, '_acquire_order_write_lock', lambda *args: (None, False))
    response = c.client.post(f'/bom/{c.ids["bom"]}/{command}', json={'warehouse_id': c.wh1})
    assert response.status_code == 409, response.json
    assert snapshot(c) == before
    assert c.w.ProductionRequisition.query.count() == 0
    unchanged_inventory(c)


def test_bom_explicit_cost_command_still_uses_current_master_price(money_case):
    c = money_case
    ident = seed(c, 3.33, 1.23, 4.10)
    c.w.db.session.get(c.w.Material, c.ids['material']).price = 1.2345
    c.w.db.session.commit()
    response = c.client.post(f'/bom/{c.ids["bom"]}/calculate_cost')
    assert response.status_code == 200 and response.json['total_cost'] == 4.11, response.json
    c.w.db.session.remove()
    row = c.w.db.session.get(c.w.BOMItem, ident)
    assert (row.quantity, row.unit_cost, row.total_cost) == (3.33, 1.2345, 4.11)
    unchanged_inventory(c)


def test_bom_add_delete_preserves_other_recorded_costs(money_case):
    c = money_case
    original = seed(c, amount=7.77)
    response = document_post(c.client, f'/bom/{c.ids["bom"]}/add_item', data={'material_code': 'B-M', 'quantity': '1.234'})
    assert response.status_code == 200, response.json
    added = response.json['id']
    c.w.db.session.remove()
    assert c.w.db.session.get(c.w.BOMItem, original).total_cost == 7.77
    new = c.w.db.session.get(c.w.BOMItem, added)
    assert (new.quantity, new.unit_cost, new.total_cost) == (1.23, .5, .62)
    assert new.bom.total_cost == 8.39
    response = document_post(c.client, f'/bom/{c.ids["bom"]}/delete_item/{added}')
    assert response.status_code == 200, response.json
    assert finance(c) == (7.77, ((original, c.ids['material'], c.ids['unit'], 1.15, 3.5, 7.77),))
    unchanged_inventory(c)


def test_bom_import_preserves_untouched_children_but_revalues_explicit_import(money_case):
    c = money_case
    ident = seed(c, amount=4.02)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['产品编码', '产品名称', '版本', '物料编码', '物料名称', '单位', '数量'])
    sheet.append(['B-P', '审计产品', 'V1', 'B-IMPORTED', '合成导入子件', '个', 2])
    stream = io.BytesIO(); workbook.save(stream); stream.seek(0)
    response = c.client.post('/bom/import', data={'file': (stream, 'synthetic.xlsx')}, content_type='multipart/form-data')
    assert response.status_code == 200, response.json
    c.w.db.session.remove()
    bom = c.w.db.session.get(c.w.BOM, c.ids['bom'])
    assert len(bom.items) == 2 and c.w.db.session.get(c.w.BOMItem, ident).total_cost == 4.02
    assert bom.total_cost == 4.02
    unchanged_inventory(c)


def test_bom_failed_commit_rolls_back_in_place_metadata_and_finance(money_case, monkeypatch):
    c = money_case
    seed(c)
    data, token = body(c)
    before = snapshot(c)
    def fail(): raise RuntimeError('owned synthetic commit failure')
    monkeypatch.setattr(c.w.db.session, 'commit', fail)
    response = c.client.post('/bom/save_table', json=data, headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 400 and '保存失败' in response.json['msg'], response.json
    assert snapshot(c) == before
    unchanged_inventory(c)


def test_bom_old_client_without_line_ids_keeps_explicit_replacement_policy(money_case):
    c = money_case
    old_id = seed(c, 3.33, 1.2345, 7.77)
    old_row = c.w.db.session.get(c.w.BOMItem, old_id)
    data, token = body(c)
    data['items'][0].pop('line_id')
    response = c.client.post('/bom/save_table', json=data, headers={'X-WMS-Document-Revision': token})
    assert response.status_code == 200, response.json
    c.w.db.session.remove()
    bom = c.w.db.session.get(c.w.BOM, c.ids['bom'])
    assert len(bom.items) == 1 and bom.items[0] is not old_row
    assert (bom.items[0].quantity, bom.items[0].unit_cost, bom.items[0].total_cost, bom.total_cost) == (3.33, 1.23, 4.10, 4.10)


def test_bom_requisition_is_new_intent_and_does_not_write_source_or_stock(money_case):
    c = money_case
    seed(c, 1.2345, 1.2345, 7.77)
    before = snapshot(c)
    response = c.client.post(f'/bom/{c.ids["bom"]}/create_requisition', json={'warehouse_id': c.wh1})
    assert response.status_code == 200, response.json
    c.w.db.session.remove()
    request = c.w.db.session.get(c.w.ProductionRequisition, response.json['id'])
    assert request.status == 'pending' and request.bom_id == c.ids['bom']
    assert len(request.items) == 1 and request.items[0].quantity == 1.23
    assert snapshot(c) == before
    unchanged_inventory(c)


def test_bom_new_form_keeps_first_save_number_and_same_request_replay(money_case):
    c = money_case
    payload = {'order_no': 'STALE-PREVIEW',
               'header': {'product_code': 'NEW', 'product_name': '合成新BOM', 'version': 'V1', 'status': 'active'},
               'items': [{'code': 'B-M', 'material_id': c.ids['material'], 'unit_id': c.ids['unit'], 'quantity': 1.15, 'price': 3.5}]}
    headers = {'X-Idempotency-Key': str(uuid.uuid4())}
    first = c.client.post('/bom/save_table', json=payload, headers=headers)
    assert first.status_code == 200, first.json
    second = c.client.post('/bom/save_table', json=payload, headers=headers)
    assert second.status_code == 200 and second.json['id'] == first.json['id'], second.json
    c.w.db.session.remove()
    created = c.w.db.session.get(c.w.BOM, first.json['id'])
    assert c.w.BOM.query.count() == 2 and created.bom_no != 'STALE-PREVIEW'
    assert created.total_cost == 4.03 and len(created.items) == 1
    unchanged_inventory(c)


def test_bom_modern_add_and_remove_keep_surviving_owned_line(money_case):
    c = money_case
    original = seed(c, 1.2345, 1.2345, 7.77)
    data, _ = body(c)
    data['items'].append({'code': 'B-M', 'material_id': c.ids['material'], 'unit_id': c.ids['unit'],
                          'quantity': 1.239, 'price': 3.555, 'remark': '新行'})
    response = document_post(c.client, '/bom/save_table', json=data)
    assert response.status_code == 200, response.json
    c.w.db.session.remove()
    bom = c.w.db.session.get(c.w.BOM, c.ids['bom'])
    assert len(bom.items) == 2 and bom.total_cost == 12.18
    preserved = next(r for r in bom.items if r.id == original)
    added = next(r for r in bom.items if r.id != original)
    assert (preserved.quantity, preserved.unit_cost, preserved.total_cost) == (1.2345, 1.2345, 7.77)
    assert (added.quantity, added.unit_cost, added.total_cost) == (1.24, 3.56, 4.41)
    added_id = added.id
    data, _ = body(c)
    data['items'] = [r for r in data['items'] if int(r['line_id']) == added_id]
    response = document_post(c.client, '/bom/save_table', json=data)
    assert response.status_code == 200, response.json
    assert finance(c) == (4.41, ((added_id, c.ids['material'], c.ids['unit'], 1.24, 3.56, 4.41),))
    unchanged_inventory(c)


def test_bom_later_invalid_new_line_does_not_change_first_owned_row(money_case):
    c = money_case
    seed(c)
    data, _ = body(c)
    data['items'].append({'code': 'B-M', 'quantity': 0, 'price': 1, 'unit_id': c.ids['unit']})
    before = snapshot(c)
    response = document_post(c.client, '/bom/save_table', json=data)
    assert response.status_code == 400, response.json
    assert snapshot(c) == before
    unchanged_inventory(c)
