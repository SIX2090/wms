"""Exercise stocktake displays and document controls through the ordinary web routes."""
from io import BytesIO

from openpyxl import Workbook, load_workbook

import app as wms
from tests.document_revision_client import document_post
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene
from tests.test_stocktake_adjustment_controls import _complete, _count


def material_rows(response, code):
    assert response.status_code == 200
    return [row for row in load_workbook(BytesIO(response.data), data_only=True).active.values if code in row]


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
    assert response['status'] == 'error' and '第2行' in response['msg']
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
