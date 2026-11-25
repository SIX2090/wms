"""Exercise stocktake displays and document controls through the ordinary web routes."""
from html import unescape
from io import BytesIO
import re
from urllib.parse import parse_qs, urlsplit

from openpyxl import Workbook, load_workbook
import pytest

import app as wms
from tests.document_revision_client import document_post
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene
from tests.test_stocktake_adjustment_controls import _complete, _count


def material_rows(response, code):
    assert response.status_code == 200
    return [row for row in load_workbook(BytesIO(response.data), data_only=True).active.values if code in row]


def test_stocktake_list_creation_uses_filtered_warehouse(scene):
    client, default, filtered, _ = scene

    def selected_warehouse(response):
        assert response.status_code == 200
        html = response.get_data(as_text=True).split('id="addForm"', 1)[1].split('</form>', 1)[0]
        return re.search(r'<option value="(\d+)" selected>', html).group(1)

    assert selected_warehouse(client.get('/check')) == str(default.id)
    result = client.get('/check', query_string={'warehouse_id': filtered.id, 'status': 'completed'})
    assert selected_warehouse(result) == str(filtered.id)
    created = client.post('/check/add', data={'warehouse_id': str(filtered.id)}).get_json()
    assert created['status'] == 'success'
    order = wms.db.session.get(wms.InventoryCheck, created['id'])
    assert order.warehouse == filtered.name and order.status == 'pending'
    assert client.get(f'/check/{order.id}?embedded=1').status_code == 200


@pytest.mark.parametrize('embedded', [None, '1'])
def test_saved_stocktake_returns_to_its_warehouse_list(scene, embedded):
    client, _, warehouse, material = scene
    key = _count(client, warehouse, material, [{'actual_stock': 40}])
    check = wms.db.session.get(wms.InventoryCheck, key)
    query = {'embedded': embedded} if embedded else {}
    detail = client.get(f'/check/{key}', query_string=query)
    assert detail.status_code == 200
    href = re.search(r'<a data-wms-back href="([^"]+)"', detail.get_data(as_text=True)).group(1)
    destination = urlsplit(unescape(href))
    assert destination.path == '/check'
    assert parse_qs(destination.query) == {
        'warehouse_id': [str(warehouse.id)], **({'embedded': ['1']} if embedded else {}),
    }
    listing = client.get(destination.geturl())
    assert listing.status_code == 200 and check.check_no in listing.get_data(as_text=True)
    assert check.check_no not in client.get('/check').get_data(as_text=True)


@pytest.mark.parametrize('batch', [False, True], ids=['single', 'batch'])
def test_delete_stocktake_after_removed_adjustment_is_fully_reversed(scene, batch):
    client, _, warehouse, material = scene
    check_id = _count(client, warehouse, material, [{'actual_stock': 110}])
    check_no = wms.db.session.get(wms.InventoryCheck, check_id).check_no
    assert _complete(client, check_id)['status'] == 'success'
    order_id = wms.AdjustmentOrder.query.one().id
    for path in (f'/adjustment/{order_id}/complete', f'/adjustment/{order_id}/revert',
                 f'/check/{check_id}/revert', f'/adjustment/{order_id}/delete'):
        assert document_post(client, path, json={}).json['status'] == 'success'
    ledger = wms.StockTransaction.query.filter_by(reference_type='adjustment', reference_id=order_id)
    flows = [(row.id, row.quantity, row.warehouse_id, row.location) for row in ledger.order_by(wms.StockTransaction.id)]
    assert sorted(flow[1] for flow in flows) == [-10, 10]

    filters = {'warehouse_id': warehouse.id, 'search': check_no}
    html = client.get('/check', query_string=filters).get_data(as_text=True)
    checkbox = re.search(r'class="itemCheck check-item" value="' + str(check_id) + r'" [^>]*>', html)
    assert checkbox is not None and 'disabled' not in checkbox[0]
    url = '/check/batch_delete' if batch else f'/check/{check_id}/delete'
    result = document_post(client, url, json={'ids': [check_id]} if batch else {}).json
    assert result['status'] == 'success', result
    if batch:
        assert result['deleted'] == 1

    assert wms.db.session.get(wms.InventoryCheck, check_id) is None
    assert not wms.InventoryCheckItem.query.filter_by(inventory_check_id=check_id).count()
    assert client.get(f'/check/{check_id}').status_code == 404
    listing = client.get('/check', query_string=filters).get_data(as_text=True)
    assert '暂无盘点记录' in listing and f'href="/check/{check_id}"' not in listing
    assert not material_rows(client.get('/check/export', query_string=filters), material.code)
    if batch:
        assert document_post(client, url, json={'ids': [check_id]}).json['deleted'] == 0
    else:
        assert document_post(client, url, json={}).status_code == 404
    historical_adjustment = wms.db.session.get(wms.AdjustmentOrder, order_id)
    assert historical_adjustment.status == 'deleted' and historical_adjustment.source_id is None
    assert [(row.id, row.quantity, row.warehouse_id, row.location) for row in ledger.order_by(wms.StockTransaction.id)] == flows
    assert material.stock == 100


@pytest.mark.parametrize('blocker', ['adjustment', 'warehouse', 'location', 'scan', 'direct_flow'])
def test_delete_stocktake_rejects_unresolved_dependencies(scene, blocker):
    client, other, warehouse, material = scene
    check_id = _count(client, warehouse, material, [{'actual_stock': 110}])
    assert _complete(client, check_id)['status'] == 'success'
    order_id = wms.AdjustmentOrder.query.one().id
    for path in (f'/adjustment/{order_id}/complete', f'/adjustment/{order_id}/revert', f'/check/{check_id}/revert'):
        assert document_post(client, path, json={}).json['status'] == 'success'
    if blocker != 'adjustment':
        assert document_post(client, f'/adjustment/{order_id}/delete', json={}).json['status'] == 'success'
    if blocker in ('warehouse', 'location'):
        reversal = wms.StockTransaction.query.filter_by(reference_type='adjustment', reference_id=order_id,
                                                         transaction_type='revert_adjustment_in').one()
        if blocker == 'warehouse':
            reversal.warehouse_id = other.id
        else:
            reversal.location = 'Different bin'
    if blocker == 'scan':
        wms.db.session.add(wms.InventoryCheckScan(check_id=check_id, check_no='SCAN-LINKED', warehouse=warehouse.name))
    if blocker == 'direct_flow':
        wms.db.session.add(wms.StockTransaction(material_id=material.id, warehouse_id=warehouse.id,
                                                transaction_type='check_in', quantity=1,
                                                reference_type='check', reference_id=check_id))
    wms.db.session.commit()

    html = client.get('/check', query_string={'warehouse_id': warehouse.id}).get_data(as_text=True)
    checkbox = re.search(r'class="itemCheck check-item" value="' + str(check_id) + r'" [^>]*>', html)
    assert checkbox is not None and 'disabled' in checkbox[0]
    expected = {'adjustment': '移除', 'warehouse': '冲回', 'location': '冲回', 'scan': '扫码', 'direct_flow': '盘点流水'}[blocker]
    assert expected in document_post(client, f'/check/{check_id}/delete', json={}).json['msg']
    batch = document_post(client, '/check/batch_delete', json={'ids': [check_id]}).json
    assert batch['deleted'] == 0 and expected in batch['skipped'][0]
    assert wms.db.session.get(wms.InventoryCheck, check_id) is not None
    assert wms.db.session.get(wms.AdjustmentOrder, order_id).source_id == check_id


def test_pallet_count_outputs_and_source_navigation(scene):
    client, _, warehouse, material = scene
    key = _count(client, warehouse, material, [{'actual_stock': 40}, {'actual_stock': 70}])
    single = material_rows(client.get(f'/check/{key}/export'), material.code)
    assert [(r[6], r[7], r[8], r[-1]) for r in single] == [(100, 40, 10, 110), (None, 70, None, None)]
    listing = material_rows(client.get('/check/export', query_string={'warehouse_id': warehouse.id}), material.code)
    assert [(r[7], r[8], r[9], r[-1]) for r in listing] == [(100, 40, 10, 110), (None, 70, None, None)]
    printed = material_rows(client.get(f'/check/{key}/print_excel'), material.code)
    assert [r[5:9] for r in printed] == [(100, 40, 110, 10), (None, 70, None, None)]
    page = client.get(f'/check/{key}/print').get_data(as_text=True)
    assert warehouse.name in page and '110.00' in page and '-60.00' not in page and '-30.00' not in page
    assert _complete(client, key)['status'] == 'success'
    adj = wms.AdjustmentOrder.query.one()
    assert adj.items[0].quantity == 10 and material.stock == 100
    check_page = client.get(f'/check/{key}').get_data(as_text=True)
    assert f'href="/adjustment/{adj.id}"' in check_page and adj.adjustment_no in check_page
    detail = client.get(f'/adjustment/{adj.id}').get_data(as_text=True)
    assert f'href="/check/{key}"' in detail and '确认调整库存' in detail
    for action in ('complete', 'revert'):
        assert document_post(client, f'/adjustment/{adj.id}/{action}', json={}).json['status'] == 'success'
    assert document_post(client, f'/check/{key}/revert', json={}).json['status'] == 'success'
    assert material.stock == 100 and '已撤回' in client.get(f'/adjustment/{adj.id}').get_data(as_text=True)


def test_zero_and_unfinished_pallet_have_no_premature_net(scene):
    client, _, warehouse, material = scene
    key = _count(client, warehouse, material, [{'actual_stock': 0}, {'actual_stock': None}])
    rows = material_rows(client.get(f'/check/{key}/export'), material.code)
    assert [(r[6], r[7], r[8], r[-1]) for r in rows] == [(100, 0, None, None), (None, None, None, None)]


def test_rejected_location_import_leaves_no_document_or_material(scene):
    client, _, warehouse, _ = scene
    wms.set_system_setting('location_management_enabled', '1')
    wms.db.session.commit()
    book = Workbook()
    book.active.append(['单据编号','仓库','物料编码','实际库存','区域'])
    book.active.append(['CK-EMPTY', warehouse.name, 'NOT-CREATED', 3, None])
    data = BytesIO()
    book.save(data)
    data.seek(0)
    response = client.post('/check/import', data={'file': (data, 'count.xlsx')}).json
    assert response['status'] == 'error' and response['count'] == response['item_count'] == 0
    assert '没有有效盘点明细' in response['msg'] and '第2行' in response['warnings']
    assert not wms.InventoryCheck.query.count()
    assert not wms.Material.query.filter_by(code='NOT-CREATED').count()


def test_stocktake_display_values(scene):
    from services.stocktake import stocktake_display_values

    client, _, warehouse, material = scene
    key = _count(client, warehouse, material, [{'actual_stock': 40}, {'actual_stock': 70}])
    rows = sorted(wms.db.session.get(wms.InventoryCheck, key).items, key=lambda row: row.id)
    display = stocktake_display_values(reversed(rows))
    assert display[rows[0].id] == dict(system_stock=100, actual_stock=40, count_total=110, difference=10)
    assert display[rows[1].id] == dict(system_stock=None, actual_stock=70, count_total=None, difference=None)

def test_read_only_account_can_trace_documents_without_edit_controls(scene):
    from html.parser import HTMLParser

    class Controls(HTMLParser):
        def __init__(self):
            super().__init__()
            self.elements = []

        def handle_starttag(self, tag, attrs):
            if tag in ('a', 'button', 'input'):
                self.elements.append(dict(attrs))

    client, _, warehouse, material = scene
    key = _count(client, warehouse, material, [{'actual_stock': 95}])
    assert _complete(client, key)['status'] == 'success'
    adjustment_id = wms.AdjustmentOrder.query.one().id
    warehouse_id = warehouse.id
    viewer = wms.User(username='stocktake_reader', password_hash='unused-test-hash',
                      role='viewer', must_change_password=False)
    wms.db.session.add(viewer)
    wms.db.session.commit()
    viewer_id = viewer.id

    # A separate app context gives the second account its own Flask-Login user cache.
    with wms.app.app_context():
        reader = wms.app.test_client()
        with reader.session_transaction() as session:
            session['_user_id'] = str(viewer_id)
            session['_fresh'] = True
        for path in ('/check', '/adjustment', f'/check/{key}', f'/adjustment/{adjustment_id}'):
            response = reader.get(path, query_string={'warehouse_id': warehouse_id})
            assert response.status_code == 200
            controls = Controls()
            controls.feed(response.get_data(as_text=True))
            blocked = {'编辑', '删除', '复制', '撤销盘点完成', '确认调整库存', '撤销库存调整'}
            assert not any(element.get('title') in blocked for element in controls.elements)
            assert not any(element.get('data-document-action') in {
                'completeAdjustment', 'revertAdjustment', 'revertDocument', 'submitForm'
            } for element in controls.elements)
            if path in ('/check', '/adjustment'):
                assert any('check-item' in e.get('class', '').split() and 'disabled' in e for e in controls.elements)
            else:
                linked = f'/adjustment/{adjustment_id}' if path.startswith('/check/') else f'/check/{key}'
                assert any(element.get('href') == linked for element in controls.elements)


def test_negative_actuals_and_legacy_line_updates(scene):
    from tests.test_bug_2026_09_13_004_check_row_identity import _save

    client, _, warehouse, material = scene
    assert _save(client, warehouse, material, [{'actual_stock': -1}])['status'] == 'error'
    assert wms.InventoryCheck.query.count() == 0
    key = _count(client, warehouse, material, [{'actual_stock': None}])
    line = wms.db.session.get(wms.InventoryCheck, key).items[0]
    endpoint = f'/check/{key}/item/{line.id}'
    response = document_post(client, endpoint, data={'actual_stock': '-0.001'})
    assert response.status_code == 400 and '负数' in response.json['msg']
    assert not line.has_actual_count
    assert document_post(client, endpoint, data={'actual_stock': '0'}).json['status'] == 'success'
    assert line.has_actual_count and line.actual_stock == 0
    assert document_post(client, endpoint, data={'actual_stock': ''}).json['status'] == 'success'
    assert not line.has_actual_count and line.actual_stock == line.system_stock
    line.actual_stock = -1
    wms.db.session.commit()
    assert '负数' in _complete(client, key)['msg']
    assert not wms.AdjustmentOrder.query.count()
    assert material.stock == 100
