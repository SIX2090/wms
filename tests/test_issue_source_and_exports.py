"""Exercise source reservations, actual postings and Excel with isolated business documents."""
import io
import json
import re

from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook

from tests.document_revision_client import document_post
from tests.frontend_page_source import in_order_add_data
from tests.test_auto_push_requisition import _create_purchase_in_order, _login, _reset_db, _seed
from tests.test_requisition_location_flow_integration import accepted, save, scene, wms


def test_pushed_issue_edit_complete_revert_and_release():
    with wms.app.app_context():
        _reset_db()
        supplier = _seed()
    client = wms.app.test_client()
    _login(client)
    receipt = _create_purchase_in_order(client, supplier, False)
    accepted(client.post(f'/in_order/{receipt}/complete?force=1'))
    with wms.app.app_context():
        source_line = wms.db.session.get(wms.InOrder, receipt).items[0].id
    issue = accepted(client.post(f'/in_order/{receipt}/push', json={
        'target_type': 'requisition', 'request_id': 'issue-edit-roundtrip',
        'items': [{'source_item_id': source_line, 'quantity': 2}],
    }))['id']
    with wms.app.app_context():
        line = wms.db.session.get(wms.OutOrder, issue).items[0].id
    detail = BeautifulSoup(client.get(f'/out_order/{issue}').data, 'html.parser')
    assert not detail.select_one(f'a[href="/out_order/add?order_id={issue}"]')
    assert detail.select_one('[data-document-action="completeOrder"]').get_text(strip=True) == '完成领料出库'
    assert detail.select_one('.dropdown-menu button[onclick^="deleteOrder"]')
    assert detail.select_one('[data-bs-target="#editHeaderModal"]').get_text(strip=True) == '编辑基本信息'
    assert client.get(f'/out_order/add?order_id={issue}').location.endswith(f'/out_order/{issue}')
    for path, data in [
        ('/out_order/item/update', {'id': line, 'quantity': 4}),
        (f'/out_order/{issue}/item/add', {'code': 'AUTO_MAT', 'quantity': 1}),
        (f'/out_order/{issue}/item/{line}/delete', {}),
    ]:
        assert document_post(client, path, data=data).status_code == 409
    assert document_post(client, f'/out_order/{issue}/batch_add_items',
                         json={'content': 'AUTO_MAT\t1'}).status_code == 409
    accepted(client.post(f'/out_order/{issue}/complete?force=1'))
    undo = BeautifulSoup(client.get(f'/out_order/{issue}').data, 'html.parser').select_one('#issueRevert')
    assert undo.get_text(strip=True) == '撤销领料'
    assert all(text in undo['data-summary'] for text in ('自动领料仓', 'AUTO_MAT', '2.0 个', '删除草稿才会释放'))
    with wms.app.app_context():
        assert wms.Material.query.filter_by(code='AUTO_MAT').one().stock == 3
    accepted(client.post(f'/out_order/{issue}/revert'))
    assert client.post(f'/out_order/{issue}/revert').get_json()['status'] == 'error'
    with wms.app.app_context():
        assert wms.Material.query.filter_by(code='AUTO_MAT').one().stock == 5
        assert wms.DocumentPushLine.query.filter_by(target_document_id=issue, status='active').one().pushed_quantity == 2
        # A draft saved by the old inline editor must also be caught at posting time.
        wms.db.session.get(wms.OutOrderItem, line).quantity = 4
        wms.db.session.commit()
    assert client.post(f'/out_order/{issue}/complete?force=1').get_json()['status'] == 'error'
    assert client.post(f'/in_order/{receipt}/revert').status_code == 409
    accepted(client.post(f'/out_order/{issue}/delete'))
    accepted(client.post(f'/in_order/{receipt}/revert'))


def test_exports_show_posted_quantity_and_picker_through_reversal(scene):
    client, warehouse, _, material, unit = scene
    issue = accepted(save(client, material, unit, {
        'warehouse_id': warehouse, 'location': 'Rack-1', 'picker': '领料甲',
    }))['id']
    for action, expected in [(None, 0), ('complete', 5), ('revert', 0)]:
        if action:
            accepted(client.post(f'/requisition/{issue}/{action}'))
        if action == 'complete':
            detail = BeautifulSoup(client.get(f'/requisition/{issue}').data, 'html.parser')
            listing = BeautifulSoup(client.get('/requisition').data, 'html.parser')
            message = detail.select_one('#issueRevert')['data-summary']
            assert listing.select_one('.revert-btn')['data-summary'] == message
            assert all(text in message for text in ('U1仓A', 'U1-M', '5.0 个', '草稿'))
        for path in ['/requisition/export', f'/requisition/{issue}/export']:
            rows = list(load_workbook(io.BytesIO(client.get(path).data)).active.values)
            row = dict(zip(rows[0], rows[1]))
            assert row['领料人'] == '领料甲' and row['数量'] == 5
            if path == '/requisition/export':
                assert row['已领数量'] == expected
    assert client.post(f'/requisition/{issue}/revert').get_json()['status'] == 'error'


def test_excel_import_rejects_wrong_unit_without_partial_draft(scene):
    client, _, _, _, _ = scene
    for unit, should_save in [('箱', False), ('U1-UNIT', True)]:
        book = Workbook()
        sheet = book.active
        sheet.append(['单据编号', '仓库', '库位', '物料编码', '数量', '单位', '领料人'])
        for label in ['个', unit]:
            sheet.append(['REQ-UNIT-TEST', 'U1仓A', 'Rack-1', 'U1-M', 2, label, '领料甲'])
        stream = io.BytesIO()
        book.save(stream)
        stream.seek(0)
        result = client.post('/requisition/import', data={'file': (stream, 'test.xlsx')}).get_json()
        draft = wms.ProductionRequisition.query.filter_by(req_no='REQ-UNIT-TEST').first()
        if should_save:
            assert draft and len(draft.items) == 2 and draft.picker == '领料甲'
        else:
            assert result['status'] == 'error' and '第3行' in result['msg'] and 'U1-M' in result['msg']
            assert draft is None


def test_continue_entry_uses_prefilled_warehouse_stock(scene):
    client, _, warehouse, material, _ = scene
    expected = wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse, warehouse))[material]
    for path in ('/out_order/add', '/in_order/add'):
        html = client.get(path, query_string={'warehouse': 'U1仓B'}).get_data(as_text=True)
        page = BeautifulSoup(html, 'html.parser')
        assert int(page.select_one('[name=warehouse_id] option[selected]')['value']) == warehouse
        if path == '/in_order/add':
            materials = in_order_add_data(html)['materials']
        else:
            materials = json.loads(re.search(r'const materials = ([^\n]+);', html).group(1))
        assert next(item['stock'] for item in materials if item['code'] == 'U1-M') == expected == 80


def test_ordinary_issue_revert_returns_once_to_original_warehouse(scene):
    client, a, b, material, _ = scene
    user = wms.User.query.filter_by(username='u1-integration').one()
    user.role = 'warehouse'
    wms.db.session.commit()
    def balances():
        return [wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse, wid))[material]
                for wid in (a, b)]
    assert balances() == [70, 80]
    issue = accepted(client.post('/out_order/add', json={
        'business_type': '领料单', 'warehouse_id': b, 'location': 'Rack-1',
        'items': [{'code': 'U1-M', 'quantity': 4}],
    }))['id']
    accepted(client.post(f'/out_order/{issue}/complete?force=1'))
    assert balances() == [70, 76]
    accepted(client.post(f'/out_order/{issue}/revert'))
    assert balances() == [70, 80]
    assert client.post(f'/out_order/{issue}/revert').get_json()['status'] == 'error'
    assert balances() == [70, 80]
