"""BUG-2026-11-07-004: warehouse boundaries survive whole-document Excel imports."""
from io import BytesIO

import app as w
from openpyxl import Workbook, load_workbook
import pytest

OLD_HEADERS = ['单据编号', '日期', '客户', '联系人', '电话', '售后原因', '物料编码',
               '物料名称', '规格', '单位', '数量', '单价', '备注']
ADJUSTMENT_HEADERS = ['单据编号', '日期', '调整类型', '物料编码', '物料名称', '规格',
                      '单位', '数量', '库位', '原因', '备注']
TRANSFER_HEADERS = ['单据编号', '日期', '调出仓库', '调入仓库', '物料编码', '物料名称',
                    '规格', '单位', '数量', '单价', '备注']


@pytest.fixture
def import_state(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setitem(w.app.config, 'SESSION_COOKIE_SECURE', False)
    with w.app.app_context(), w.app.test_request_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove(); w.db.drop_all(); w.db.create_all()
        user = w.User(username='after-import-only', password_hash='unused', role='warehouse', must_change_password=False)
        unit = w.Unit(code='AI-U', name='个')
        category = w.MaterialCategory(code='AI-C', name='合成分类')
        warehouses = [w.Warehouse(code='AI-A', name='导入甲仓', status='active', is_default=True),
                      w.Warehouse(code='AI-B', name='导入乙仓', status='active'),
                      w.Warehouse(code='AI-OFF', name='停用合成仓', status='inactive')]
        w.db.session.add_all([user, unit, category, *warehouses]); w.db.session.flush()
        material = w.Material(code='AI-M', name='合成物料', unit_id=unit.id,
                              category_id=category.id, stock=0, price=3)
        w.db.session.add(material); w.db.session.flush()
        from services.warehouse_stock_service import apply_stock_delta
        for warehouse, quantity in zip(warehouses, [10, 20]):
            ok, error = apply_stock_delta(material, quantity, transaction_type='in',
                                         reference_type='after_import_test', warehouse=warehouse.name)
            assert ok, error
        w.db.session.commit()
        ids = dict(user=user.id, material=material.id, warehouses=[item.id for item in warehouses])
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(ids['user']); session['_fresh'] = True
    yield client, ids
    with w.app.app_context():
        w.db.session.remove(); w.db.drop_all()


def workbook(rows, extra_headers=(), *, base_headers=OLD_HEADERS):
    book = Workbook()
    sheet = book.active
    headers = [*base_headers, *extra_headers]
    sheet.append(headers)
    for values in rows:
        row = {'单据编号': 'ASO-IMPORT-001', '日期': '2026-11-06', '客户': '合成新客户',
               '物料编码': 'AI-M', '物料名称': '合成物料', '单位': '个', '数量': 2, '单价': 3,
               '调整类型': '盘盈', '调出仓库': 'AI-A', '调入仓库': 'AI-B', **values}
        sheet.append([row.get(name) for name in headers])
    output = BytesIO(); book.save(output); output.seek(0)
    return output


def post_file(client, rows, extra_headers=(), *, url='/after_sale_out/import', base_headers=OLD_HEADERS):
    return client.post(url, data={'file': (workbook(rows, extra_headers, base_headers=base_headers), 'drafts.xlsx')},
                       headers={'X-Requested-With': 'XMLHttpRequest'})


def snapshot(ids):
    with w.app.app_context():
        return dict(orders=w.AfterSaleOutOrder.query.count(), items=w.AfterSaleOutOrderItem.query.count(),
                    adjustments=w.AdjustmentOrder.query.count(), adjustment_items=w.AdjustmentOrderItem.query.count(),
                    transfers=w.TransferOrder.query.count(), transfer_items=w.TransferOrderItem.query.count(),
                    customers=w.Customer.query.count(), materials=w.Material.query.count(),
                    warehouses=w.Warehouse.query.count(),
                    transactions=w.StockTransaction.query.count(),
                    stock=float(w.db.session.get(w.Material, ids['material']).stock),
                    quantities=[w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, warehouse_id)).get(ids['material'], 0)
                                for warehouse_id in ids['warehouses'][:2]])


def test_legacy_template_uses_configured_default_without_changing_stock(import_state):
    client, ids = import_state
    before = snapshot(ids)
    response = post_file(client, [{}])
    assert response.status_code == 200 and response.json['status'] == 'success'
    with w.app.app_context():
        order = w.AfterSaleOutOrder.query.one()
        assert (order.warehouse, order.location, order.status, order.operator_id) == ('导入甲仓', '', 'pending', ids['user'])
        assert order.total_amount == 6 and len(order.items) == 1
    after = snapshot(ids)
    assert (after['stock'], after['quantities'], after['transactions']) == (before['stock'], before['quantities'], before['transactions'])


@pytest.mark.parametrize('header,value', [('仓库', '导入乙仓'), ('仓库', 'AI-B'),
                                         ('仓库名称', '导入乙仓'), ('仓库编码', 'AI-B')])
def test_explicit_name_or_code_overrides_default(import_state, header, value):
    client, ids = import_state
    response = post_file(client, [{header: value}], [header])
    assert response.status_code == 200 and response.json['status'] == 'success'
    with w.app.app_context():
        assert w.AfterSaleOutOrder.query.one().warehouse == '导入乙仓'
    assert snapshot(ids)['quantities'] == [10, 20]


@pytest.mark.parametrize('mode', ['no_default', 'autofill_off', 'default_inactive', 'unknown', 'inactive'])
def test_invalid_or_missing_warehouse_rejects_without_any_write(import_state, mode):
    client, ids = import_state
    with w.app.app_context():
        default = w.db.session.get(w.Warehouse, ids['warehouses'][0])
        if mode == 'no_default':
            default.is_default = False
        elif mode == 'autofill_off':
            w.db.session.add(w.SystemSetting(key='prefer_default_warehouse', value='0'))
        elif mode == 'default_inactive':
            default.status = 'inactive'
        w.db.session.commit()
    before = snapshot(ids)
    value = 'NOT-A-WAREHOUSE' if mode == 'unknown' else 'AI-OFF' if mode == 'inactive' else ''
    response = post_file(client, [{'仓库': value}], ['仓库'])
    assert response.status_code == 400 and response.json['status'] == 'error'
    assert '仓库' in response.json['msg'] and '第2行' in response.json['msg']
    assert snapshot(ids) == before


def test_later_bad_row_prevents_earlier_draft_and_master_data(import_state):
    client, ids = import_state
    before = snapshot(ids)
    response = post_file(client, [{'单据编号': 'ASO-FIRST', '仓库': 'AI-A', '物料编码': 'UNCREATED-FIRST'},
                                  {'单据编号': 'ASO-SECOND', '仓库': 'MISSING', '物料编码': 'UNCREATED'}], ['仓库'])
    assert response.status_code == 400 and '第3行' in response.json['msg']
    assert snapshot(ids) == before


def test_same_document_cannot_mix_warehouses(import_state):
    client, ids = import_state
    before = snapshot(ids)
    response = post_file(client, [{'仓库': 'AI-A'}, {'仓库': 'AI-B'}], ['仓库'])
    assert response.status_code == 400 and '仓库' in response.json['msg']
    assert snapshot(ids) == before


@pytest.mark.parametrize('location,expected', [('', 400), ('乙-01', 200)])
def test_enabled_location_management_requires_and_preserves_location(import_state, location, expected):
    client, ids = import_state
    with w.app.app_context():
        w.db.session.add(w.SystemSetting(key='location_management_enabled', value='1')); w.db.session.commit()
    before = snapshot(ids)
    response = post_file(client, [{'仓库': 'AI-B', '库位': location}], ['仓库', '库位'])
    assert response.status_code == expected
    if expected == 400:
        assert '库位' in response.json['msg'] and snapshot(ids) == before
    else:
        with w.app.app_context():
            order = w.AfterSaleOutOrder.query.one()
            assert (order.warehouse, order.location) == ('导入乙仓', '乙-01')
        after = snapshot(ids)
        assert (after['stock'], after['transactions']) == (before['stock'], before['transactions'])


def test_same_document_cannot_mix_locations(import_state):
    client, ids = import_state
    with w.app.app_context():
        w.db.session.add(w.SystemSetting(key='location_management_enabled', value='1')); w.db.session.commit()
    before = snapshot(ids)
    response = post_file(client, [{'仓库': 'AI-A', '库位': '甲-01'}, {'仓库': 'AI-A', '库位': '甲-02'}], ['仓库', '库位'])
    assert response.status_code == 400 and '库位' in response.json['msg']
    assert snapshot(ids) == before


def test_different_documents_keep_their_own_warehouses(import_state):
    client, ids = import_state
    response = post_file(client, [{'单据编号': 'ASO-A', '仓库': 'AI-A'},
                                  {'单据编号': 'ASO-B', '仓库': 'AI-B'}], ['仓库'])
    assert response.status_code == 200 and response.json['count'] == 2
    with w.app.app_context():
        assert {row.order_no: row.warehouse for row in w.AfterSaleOutOrder.query.all()} == {'ASO-A': '导入甲仓', 'ASO-B': '导入乙仓'}
    assert snapshot(ids)['quantities'] == [10, 20]


def test_completion_uses_imported_warehouse_even_when_default_is_other(import_state):
    client, ids = import_state
    response = post_file(client, [{'仓库': 'AI-B'}], ['仓库'])
    assert response.status_code == 200
    with w.app.app_context():
        order_id = w.AfterSaleOutOrder.query.one().id
    response = client.post(f'/after_sale_out/{order_id}/complete', json={})
    assert response.status_code == 200 and response.json['status'] == 'success'
    after = snapshot(ids)
    assert after['quantities'] == [10, 18] and after['stock'] == 28


@pytest.mark.parametrize('url', ['/export/template/after_sale_out', '/after_sale_out/download_template'])
def test_both_templates_preserve_old_columns_and_append_places(import_state, url):
    client, _ = import_state
    response = client.get(url)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    headers = [cell.value for cell in book.active[1]]
    assert headers[:13] == OLD_HEADERS and headers[13:] == ['仓库', '库位']


def test_after_sale_same_place_rows_merge_and_duplicate_file_keeps_existing_document(import_state):
    client, ids = import_state
    response = post_file(client, [{'仓库': 'AI-B'}, {'仓库': '导入乙仓'}], ['仓库'])
    assert response.status_code == 200 and response.json['count'] == 1 and response.json['item_count'] == 2
    with w.app.app_context():
        order = w.AfterSaleOutOrder.query.one()
        assert order.warehouse == '导入乙仓' and order.total_amount == 12
    before = snapshot(ids)
    response = post_file(client, [{'仓库': 'UNKNOWN', '物料编码': 'NEVER-CREATED'}], ['仓库'])
    assert response.status_code == 200 and response.json['count'] == 0
    assert '已存在' in response.json['warnings'] and snapshot(ids) == before


def test_adjustment_old_template_uses_default_and_explicit_code_overrides_it(import_state):
    client, ids = import_state
    response = post_file(client, [{'单据编号': 'ADJ-OLD'}], url='/adjustment/import', base_headers=ADJUSTMENT_HEADERS)
    assert response.status_code == 200 and response.json['count'] == 1
    response = post_file(client, [{'单据编号': 'ADJ-EXPLICIT', '仓库编码': 'AI-B', '调整类型': '盘亏'}], ['仓库编码'],
                         url='/adjustment/import', base_headers=ADJUSTMENT_HEADERS)
    assert response.status_code == 200 and response.json['count'] == 1
    with w.app.app_context():
        orders = {order.adjustment_no: order for order in w.AdjustmentOrder.query.all()}
        assert orders['ADJ-OLD'].warehouse == '导入甲仓'
        explicit = orders['ADJ-EXPLICIT']
        assert (explicit.warehouse, explicit.status, explicit.operator_id) == ('导入乙仓', 'pending', ids['user'])
        assert explicit.items[0].quantity == -2
        order_id = explicit.id
    assert snapshot(ids)['quantities'] == [10, 20]
    response = client.post(f'/adjustment/{order_id}/complete', json={})
    assert response.status_code == 200 and response.json['status'] == 'success'
    after = snapshot(ids)
    assert after['quantities'] == [10, 18] and after['stock'] == 28


@pytest.mark.parametrize('mode', ['no_default', 'unknown', 'inactive', 'mixed_rows', 'missing_location', 'later_bad_row'])
def test_adjustment_invalid_place_prevents_all_document_and_master_writes(import_state, mode):
    client, ids = import_state
    rows = [{'仓库': 'AI-A'}]
    if mode == 'no_default':
        with w.app.app_context():
            w.db.session.get(w.Warehouse, ids['warehouses'][0]).is_default = False
            w.db.session.commit()
        rows = [{'仓库': ''}]
    elif mode in ('unknown', 'inactive'):
        rows = [{'仓库': 'MISSING' if mode == 'unknown' else 'AI-OFF'}]
    elif mode == 'mixed_rows':
        rows.append({'仓库': 'AI-B'})
    elif mode == 'missing_location':
        with w.app.app_context():
            w.db.session.add(w.SystemSetting(key='location_management_enabled', value='1'))
            w.db.session.commit()
    else:
        rows = [{'单据编号': 'ADJ-FIRST', '仓库': 'AI-A', '物料编码': 'NOT-CREATED'},
                {'单据编号': 'ADJ-SECOND', '仓库': 'MISSING'}]
    before = snapshot(ids)
    response = post_file(client, rows, ['仓库'], url='/adjustment/import', base_headers=ADJUSTMENT_HEADERS)
    assert response.status_code == 400 and '第' in response.json['msg']
    assert ('库位' if mode == 'missing_location' else '仓库') in response.json['msg']
    assert snapshot(ids) == before


def test_adjustment_one_warehouse_can_keep_different_item_locations(import_state):
    client, ids = import_state
    with w.app.app_context():
        w.db.session.add(w.SystemSetting(key='location_management_enabled', value='1'))
        w.db.session.commit()
    before = snapshot(ids)
    response = post_file(client, [{'仓库': 'AI-B', '库位': '乙-01'}, {'仓库': '导入乙仓', '库位': '乙-02'}],
                         ['仓库'], url='/adjustment/import', base_headers=ADJUSTMENT_HEADERS)
    assert response.status_code == 200 and response.json['count'] == 1 and response.json['item_count'] == 2
    with w.app.app_context():
        order = w.AdjustmentOrder.query.one()
        assert order.warehouse == '导入乙仓' and {item.location for item in order.items} == {'乙-01', '乙-02'}
    after = snapshot(ids)
    assert (after['stock'], after['transactions']) == (before['stock'], before['transactions'])


def test_transfer_old_template_records_both_warehouses_and_can_complete(import_state):
    client, ids = import_state
    response = post_file(client, [{}], url='/transfer/import', base_headers=TRANSFER_HEADERS)
    assert response.status_code == 200 and response.json['count'] == 1
    with w.app.app_context():
        order = w.TransferOrder.query.one()
        assert (order.from_warehouse, order.to_warehouse, order.from_location, order.to_location) == (
            '导入甲仓', '导入乙仓', '导入甲仓', '导入乙仓')
        assert order.status == 'pending' and order.operator_id == ids['user']
        order_id = order.id
    before = snapshot(ids)
    assert before['quantities'] == [10, 20] and before['warehouses'] == 3
    response = client.post(f'/transfer/{order_id}/complete', json={})
    assert response.status_code == 200 and response.json['status'] == 'success'
    after = snapshot(ids)
    assert after['quantities'] == [8, 22] and after['stock'] == 30
    assert after['transactions'] == before['transactions'] + 2


@pytest.mark.parametrize('mode', ['missing_source', 'missing_target', 'unknown', 'inactive', 'same_warehouse',
                                 'mixed_rows', 'missing_source_location', 'missing_target_location', 'later_bad_row'])
def test_transfer_invalid_place_never_creates_warehouses_drafts_or_materials(import_state, mode):
    client, ids = import_state
    rows = [{}]
    if mode == 'missing_source':
        rows = [{'调出仓库': ''}]
    elif mode == 'missing_target':
        rows = [{'调入仓库': ''}]
    elif mode in ('unknown', 'inactive'):
        rows = [{'调入仓库': 'MISSING' if mode == 'unknown' else 'AI-OFF'}]
    elif mode == 'same_warehouse':
        rows = [{'调入仓库': '导入甲仓'}]
    elif mode == 'mixed_rows':
        rows.append({'调出仓库': 'AI-B', '调入仓库': 'AI-A'})
    elif mode.startswith('missing_'):
        with w.app.app_context():
            w.db.session.add(w.SystemSetting(key='location_management_enabled', value='1'))
            w.db.session.commit()
        rows = [{'调出库位': '' if mode == 'missing_source_location' else '甲-01',
                 '调入库位': '' if mode == 'missing_target_location' else '乙-01'}]
    else:
        rows = [{'单据编号': 'TF-FIRST', '物料编码': 'NOT-CREATED'},
                {'单据编号': 'TF-SECOND', '调入仓库': 'MISSING'}]
    before = snapshot(ids)
    response = post_file(client, rows, ['调出库位', '调入库位'], url='/transfer/import', base_headers=TRANSFER_HEADERS)
    assert response.status_code == 400 and '第' in response.json['msg']
    assert snapshot(ids) == before


@pytest.mark.parametrize('same_warehouse', [False, True])
def test_transfer_enabled_locations_remain_distinct_from_warehouse_names(import_state, same_warehouse):
    client, ids = import_state
    with w.app.app_context():
        w.db.session.add(w.SystemSetting(key='location_management_enabled', value='1'))
        w.db.session.commit()
    response = post_file(client, [{'调入仓库': 'AI-A' if same_warehouse else 'AI-B', '调出库位': '甲-01', '调入库位': '目标-02'}],
                         ['调出库位', '调入库位'], url='/transfer/import', base_headers=TRANSFER_HEADERS)
    assert response.status_code == 200 and response.json['count'] == 1
    with w.app.app_context():
        order = w.TransferOrder.query.one()
        assert (order.from_warehouse, order.to_warehouse) == ('导入甲仓', '导入甲仓' if same_warehouse else '导入乙仓')
        assert (order.from_location, order.to_location) == ('甲-01', '目标-02')
    assert snapshot(ids)['stock'] == 30


def test_transfer_reordered_location_columns_do_not_capture_legacy_warehouse_aliases(import_state):
    client, _ = import_state
    headers = ['调出库位', '调入库位', *TRANSFER_HEADERS]
    response = post_file(client, [{'调出库位': '甲-01', '调入库位': '乙-01'}],
                         url='/transfer/import', base_headers=headers)
    assert response.status_code == 200 and response.json['count'] == 1
    with w.app.app_context():
        order = w.TransferOrder.query.one()
        assert (order.from_warehouse, order.to_warehouse) == ('导入甲仓', '导入乙仓')
        assert (order.from_location, order.to_location) == ('甲-01', '乙-01')


@pytest.mark.parametrize('url,headers', [('/adjustment/import', ADJUSTMENT_HEADERS), ('/transfer/import', TRANSFER_HEADERS)])
def test_existing_adjustment_and_transfer_orders_are_skipped_without_new_masters(import_state, url, headers):
    client, ids = import_state
    response = post_file(client, [{}], url=url, base_headers=headers)
    assert response.status_code == 200 and response.json['count'] == 1
    before = snapshot(ids)
    response = post_file(client, [{'仓库': 'UNKNOWN', '调出仓库': 'UNKNOWN', '物料编码': 'NOT-CREATED'}],
                         ['仓库'] if url == '/adjustment/import' else [], url=url, base_headers=headers)
    assert response.status_code == 200 and response.json['count'] == 0
    assert '已存在' in response.json['warnings'] and snapshot(ids) == before


@pytest.mark.parametrize('url,old_headers,added', [('/export/template/adjustment', ADJUSTMENT_HEADERS, ['仓库']),
                                               ('/export/template/transfer', TRANSFER_HEADERS, ['调出库位', '调入库位'])])
def test_adjustment_and_transfer_templates_keep_original_column_order(import_state, url, old_headers, added):
    client, _ = import_state
    response = client.get(url)
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data))
    assert [cell.value for cell in book.active[1]] == [*old_headers, *added]
