"""BOM drafts, references and spreadsheet import must preserve data boundaries."""
import io
import re

import pytest
from openpyxl import Workbook
from app import app, db, BOM, BOMItem, Material, ProductionRequisition, Warehouse, User, Unit


def warehouse(code='W-A', default=True, status='active'):
    row = Warehouse(code=code, name=code, status=status, is_default=default)
    db.session.add(row)
    db.session.commit()
    return row.id


def excel(rows, headers=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers or ['产品编码','产品名称','版本','物料编码','物料名称','规格','单位','数量','用途','备注'])
    for row in rows:
        sheet.append(row)
    data = io.BytesIO()
    workbook.save(data)
    data.seek(0)
    return data


def upload(client, rows, headers=None):
    return client.post('/bom/import', data={'file':(excel(rows, headers),'bom.xlsx')},
                       content_type='multipart/form-data')


def test_bom_draft_requires_default_or_explicit_active_warehouse(bom_case):
    client, ids = bom_case
    response = client.post(f"/bom/{ids['bom']}/create_requisition", json={})
    assert response.status_code == 400
    db.session.remove()
    assert ProductionRequisition.query.count() == 0


@pytest.mark.parametrize('invalid', ['inactive', 'empty', 'negative', 'bad_unit'])
def test_invalid_bom_cannot_generate_requisition(bom_case, invalid):
    client, ids = bom_case
    warehouse()
    bom = db.session.get(BOM, ids['bom'])
    if invalid == 'inactive':
        bom.status = 'inactive'
    elif invalid == 'empty':
        BOMItem.query.filter_by(bom_id=bom.id).delete()
    elif invalid == 'negative':
        bom.items[0].quantity = -1
    else:
        bom.items[0].unit_id = 999999
    db.session.commit()
    assert client.post(f"/bom/{ids['bom']}/create_requisition", json={}).status_code == 400
    db.session.remove()
    assert ProductionRequisition.query.count() == 0


def test_bom_draft_respects_explicit_warehouse_and_does_not_move_inventory(bom_case):
    client, ids = bom_case
    warehouse()
    other_id = warehouse('W-B', False)
    response = client.post(f"/bom/{ids['bom']}/create_requisition", json={'warehouse_id':other_id})
    assert response.status_code == 200
    db.session.remove()
    requisition = db.session.get(ProductionRequisition, response.get_json()['id'])
    assert requisition.warehouse == 'W-B' and requisition.status == 'pending'
    assert requisition.items[0].quantity == 2
    assert db.session.get(Material, ids['material']).stock == 10


def test_bom_draft_rejects_inactive_selected_warehouse(bom_case):
    client, ids = bom_case
    warehouse()
    other_id = warehouse('W-B', False, 'inactive')
    assert client.post(f"/bom/{ids['bom']}/create_requisition", json={'warehouse_id':other_id}).status_code == 400


def test_bom_draft_location_required_only_when_enabled(bom_case, monkeypatch):
    import app as app_module
    client, ids = bom_case
    warehouse()
    monkeypatch.setattr(app_module, 'location_management_enabled', lambda:True)
    assert client.post(f"/bom/{ids['bom']}/create_requisition", json={}).status_code == 400
    response = client.post(f"/bom/{ids['bom']}/create_requisition", json={'location':'A-01'})
    assert response.status_code == 200
    db.session.remove()
    assert db.session.get(ProductionRequisition, response.get_json()['id']).location == 'A-01'


@pytest.mark.parametrize('route', ['delete', 'alias', 'batch'])
def test_bom_deletion_error_blocks_referenced_master(bom_case, route):
    client, ids = bom_case
    db.session.add(ProductionRequisition(req_no='REQ-LINK', bom_id=ids['bom'],
                                        warehouse='W-A', status='completed', operator_id=ids['user']))
    free = BOM(bom_no='FREE-BOM', product_code='FREE', product_name='未引用')
    db.session.add(free)
    db.session.commit()
    free_id = free.id
    if route == 'delete':
        response = client.post(f"/bom/{ids['bom']}/delete", json={})
    elif route == 'alias':
        response = client.post(f"/bom/delete/{ids['bom']}", json={})
    else:
        response = client.post('/bom/batch_delete', json={'ids':[free_id,ids['bom']]})
    assert response.status_code == 400
    db.session.remove()
    assert db.session.get(BOM, ids['bom']) is not None
    assert db.session.get(BOM, free_id) is not None
    assert ProductionRequisition.query.one().bom_id == ids['bom']


def test_parent_bom_cannot_be_deleted_while_child_bom_references_it(bom_case):
    client, ids = bom_case
    child = BOM(bom_no='CHILD', product_code='CHILD', product_name='子BOM', parent_bom_id=ids['bom'])
    db.session.add(child)
    db.session.commit()
    assert client.post(f"/bom/{ids['bom']}/delete", json={}).status_code == 400


@pytest.mark.parametrize('ids_value', [[], ['invalid'], [0], [-1]])
def test_bom_batch_delete_requires_valid_nonempty_ids(bom_case, ids_value):
    client, _ = bom_case
    assert client.post('/bom/batch_delete', json={'ids':ids_value}).status_code == 400


def test_bom_import_valid_rows_and_legacy_header_only_format(bom_case):
    client, _ = bom_case
    response = upload(client, [['NEW-P','新产品','V1','B-M','测试子件','审计规格','个',3,'','']])
    assert response.status_code == 200
    db.session.remove()
    assert BOM.query.filter_by(product_code='NEW-P').one().items[0].quantity == 3
    response = upload(client, [['HEADER-P','旧格式父件','V1']], ['code','name','version'])
    assert response.status_code == 200
    db.session.remove()
    assert BOM.query.filter_by(product_code='HEADER-P').one().items == []


@pytest.mark.parametrize('quantity', [0, -1, 'nan', 'abc'])
def test_invalid_import_row_leaves_no_empty_bom(bom_case, quantity):
    client, _ = bom_case
    response = upload(client, [['INVALID-P','无效产品','V1','B-M','测试子件','审计规格','个',quantity,'','']])
    assert response.status_code == 400
    db.session.remove()
    assert BOM.query.filter_by(product_code='INVALID-P').first() is None


def test_missing_import_unit_does_not_create_material_or_bom(bom_case):
    client, _ = bom_case
    response = upload(client, [['INVALID-P','无效产品','V1','UNKNOWN-M','未知子件','独立规格','',3,'','']])
    assert response.status_code == 400
    db.session.remove()
    assert Material.query.filter_by(code='UNKNOWN-M').first() is None
    assert BOM.query.filter_by(product_code='INVALID-P').first() is None


def test_import_mixed_rows_only_commits_valid_rows(bom_case):
    client, _ = bom_case
    response = upload(client, [['NEW-P','新产品','V1','B-M','测试子件','审计规格','个',3,'',''],
                               ['INVALID-P','无效产品','V1','UNKNOWN-M','未知子件','独立规格','',3,'','']])
    assert response.status_code == 200
    db.session.remove()
    assert BOM.query.filter_by(product_code='NEW-P').one().items[0].quantity == 3
    assert BOM.query.filter_by(product_code='INVALID-P').first() is None
    assert Material.query.filter_by(code='UNKNOWN-M').first() is None


def test_import_rejects_material_only_headers(bom_case):
    client, _ = bom_case
    assert upload(client, [['B-M',3]], ['物料编码','数量']).status_code == 400


def test_import_reports_repeated_material_rows(bom_case):
    client, _ = bom_case
    response = upload(client, [['NEW-P','新产品','V1','B-M','测试子件','审计规格','个',3,'',''],
                               ['NEW-P','新产品','V1','B-M','测试子件','审计规格','个',4,'','']])
    assert response.status_code == 200
    assert '重复' in response.get_json().get('warnings','')
    db.session.remove()
    assert BOM.query.filter_by(product_code='NEW-P').one().items[0].quantity == 4


def test_import_header_update_preserves_existing_zero_unit_cost(bom_case):
    client, ids = bom_case
    bom = db.session.get(BOM, ids['bom'])
    bom.items[0].unit_cost = 0
    bom.items[0].total_cost = 0
    bom.total_cost = 0
    db.session.commit()
    assert upload(client, [['B-P','改名称','V1']], ['产品编码','产品名称','版本']).status_code == 200
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).total_cost == 0


def test_import_cannot_choose_between_same_product_version_boms(bom_case):
    client, ids = bom_case
    db.session.add(BOM(bom_no='SAME-VERSION', product_code='B-P', product_name='第二方案', version='V1'))
    db.session.commit()
    response = upload(client, [['B-P','审计产品','V1','B-M','测试子件','审计规格','个',7,'','']])
    assert response.status_code == 400
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).items[0].quantity == 2


def test_old_xls_import_returns_conversion_guidance_without_writing(bom_case):
    client, _ = bom_case
    response = client.post('/bom/import',
                           data={'file':(io.BytesIO(bytes.fromhex('d0cf11e0a1b11ae1') + b'x'*256),'old.xls')},
                           content_type='multipart/form-data')
    assert response.status_code == 400
    assert '另存' in response.get_json()['msg'] and '.xlsx' in response.get_json()['msg']
    db.session.remove()
    assert BOM.query.count() == 1


def test_warehouse_bom_detail_is_readonly_and_has_no_fake_save(bom_case):
    client, ids = bom_case
    user = db.session.get(User, ids['user'])
    user.role = 'warehouse'
    db.session.commit()
    html = client.get(f"/bom/{ids['bom']}?embedded=1").get_data(as_text=True)
    assert '<form id="docForm" class="doc-form readonly-mask">' in html
    assert 'wms-no-global-actionbar' in html
    assert 'onclick="submitForm(false)"' not in html
    assert '查看BOM' in html
    for field in ('product_code','product_name','version'):
        assert 'readonly' in re.search(r'<input[^>]+name="' + field + r'"[^>]*>', html).group()


def test_legacy_header_update_validates_status_and_can_clear_remark(bom_case):
    client, ids = bom_case
    bom = db.session.get(BOM, ids['bom'])
    bom.remark = '旧备注'
    db.session.commit()
    assert client.post(f"/bom/{ids['bom']}/update", data={'status':'invalid'}).status_code == 400
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).status == 'active'
    assert client.post(f"/bom/{ids['bom']}/update", json={'remark':'','status':'inactive'}).status_code == 200
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).remark == ''
    assert db.session.get(BOM, ids['bom']).status == 'inactive'


def test_bom_alternate_unit_is_saved_without_replacing_material_unit(bom_case):
    client, ids = bom_case
    box = Unit(code='AUDIT-BOX', name='箱')
    db.session.add(box)
    db.session.commit()
    box_id = box.id
    data = {'order_id':ids['bom'], 'order_no':'BOM-AUDIT',
            'header':{'product_code':'B-P','product_name':'审计产品','version':'V1','status':'active'},
            'items':[{'code':'B-M','quantity':3,'unit_id':box_id,'price':0}]}
    assert client.post('/bom/save_table', json=data).status_code == 200
    db.session.remove()
    assert db.session.get(BOM, ids['bom']).items[0].unit_id == box_id
    assert db.session.get(Material, ids['material']).unit_id == ids['unit']
    html = client.get(f"/bom/{ids['bom']}").get_data(as_text=True)
    assert '箱' in html or '\\u7bb1' in html
