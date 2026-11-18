"""委外实收校验只在隔离库运行，使用实际路由和库存流水。"""
import pytest
import app as w
from tests.document_revision_client import document_post
from tests.test_bug_2026_08_16_001_subcontract_location_inventory import client


def snapshot():
    return (
        [(r.id, r.status, r.total_quantity) for r in w.SubcontractReceive.query.order_by(w.SubcontractReceive.id)],
        [(r.id, r.material_id, r.quantity) for r in w.SubcontractReceiveItem.query.order_by(w.SubcontractReceiveItem.id)],
        [(r.id, r.stock) for r in w.Material.query.order_by(w.Material.id)],
        [(r.id, r.quantity) for r in w.StockTransaction.query.order_by(w.StockTransaction.id)],
        [(r.id, r.quantity) for r in w.LocationInventory.query.order_by(w.LocationInventory.id)],
        w.SubcontractOrder.query.one().status,
    )


@pytest.mark.parametrize('entry', ['quick', 'api', 'draft', 'append', 'complete'])
def test_disabled_receipt_rolls_back_the_entire_operation(client, entry):
    with w.app.app_context():
        order = w.SubcontractOrder.query.one()
        good = w.Material.query.filter_by(code='M-RAW').one()
        disabled = w.Material.query.filter_by(code='M-FG').one()
        oid, mid = order.id, disabled.id
        draft = w.SubcontractReceive(receive_no='SC-TEST', subcontract_order_id=oid,
                                     status='pending', warehouse=order.warehouse)
        w.db.session.add(draft)
        w.db.session.flush()
        if entry == 'complete':
            for product in (good, disabled):
                w.db.session.add(w.SubcontractReceiveItem(receive_id=draft.id, material_id=product.id, quantity=1))
        disabled.status = 'inactive'
        w.db.session.commit()
        rid, first = draft.id, good.id
        before = snapshot()
    item = {'material_code': 'M-FG', 'quantity': 1, 'price': 2}
    if entry == 'api':
        result = client.post('/api/subcontract/quick_receive', json=dict(order_id=oid, material_id=mid, quantity=1))
    elif entry == 'quick':
        result = client.post(f'/subcontract/{oid}/receive', data=item)
    elif entry == 'draft':
        result = client.post('/subcontract_receive/add', data=dict(subcontract_order_id=oid,
                             material_id=[str(first), str(mid)], quantity=['1', '1'], warehouse='主仓'))
    elif entry == 'append':
        result = document_post(client, f'/subcontract_receive/{rid}/item/add', data=item)
    else:
        result = client.post(f'/subcontract_receive/{rid}/complete')
    assert result.status_code == 400, result.get_data(as_text=True)
    assert 'M-FG' in result.json['msg'] and '停用' in result.json['msg']
    with w.app.app_context():
        assert snapshot() == before


def test_disabled_material_preserves_historical_reversal(client):
    with w.app.app_context():
        oid = w.SubcontractOrder.query.one().id
    result = client.post(f'/subcontract/{oid}/receive', data=dict(material_code='M-FG', quantity=1, price=2))
    assert result.json['status'] == 'success'
    with w.app.app_context():
        rid = w.SubcontractReceive.query.one().id
        product = w.Material.query.filter_by(code='M-FG').one()
        product.status = 'inactive'
        w.db.session.commit()
    assert client.get(f'/subcontract_receive/{rid}').status_code == 200
    assert client.post(f'/subcontract_receive/{rid}/revert').json['status'] == 'success'
    with w.app.app_context():
        assert w.Material.query.filter_by(code='M-FG').one().stock == 0
        assert w.db.session.get(w.SubcontractReceive, rid).status == 'pending'


def test_monthly_estimate_separates_subcontract_receipts_and_reversals(client):
    from datetime import date
    with w.app.app_context():
        wh = w.Warehouse.query.one().id
        oid = w.SubcontractOrder.query.one().id
        product = w.Material.query.filter_by(code='M-FG').one()
        product.price = 99
        w.set_system_setting('price_dimension_enabled', '1')
        w.db.session.commit()
    response = client.post(f'/subcontract/{oid}/receive', data=dict(material_code='M-FG', quantity=3, price=2))
    assert response.json['status'] == 'success', response.json
    params = dict(warehouse_id=wh, start_month=date.today().strftime('%Y-%m'),
                  end_month=date.today().strftime('%Y-%m'), material_code='M-FG')
    def report():
        payload = client.get('/report/api/warehouse_monthly', query_string=params).json
        return payload['data'][0], {c['field']: c['title'] for c in payload['columns']}
    with w.app.app_context():
        receipt = w.SubcontractReceive.query.one()
        rid = receipt.id
        assert (receipt.items[0].price, receipt.items[0].amount) == (2, 6)
    row, columns = report()
    assert row['in_amount'] == 297
    assert '委外' in columns['subcontract_in_estimate_amount'] and '参考估值' in columns['subcontract_in_estimate_amount']
    assert row['subcontract_in_estimate_amount'] == 297 and row['subcontract_out_estimate_amount'] == 0
    assert '加工费' in client.get(f'/subcontract_receive/{rid}').get_data(as_text=True)
    assert client.post(f'/subcontract_receive/{rid}/revert').json['status'] == 'success'
    row, _ = report()
    assert row['ending_quantity'] == 0
    assert (row['out_amount'], row['subcontract_out_estimate_amount']) == (297, 297)


@pytest.mark.parametrize('header, fee', [('单位加工费', 2), ('单价', 0), ('单价', None)])
def test_import_fee_is_independent_of_material_value(client, header, fee):
    import io
    from openpyxl import Workbook
    with w.app.app_context():
        product = w.Material.query.filter_by(code='M-FG').one()
        product.price = 99
        w.db.session.commit()
    book = Workbook()
    book.active.append(['入库单号', '委外加工单号', '物料编码', '收货数量', header, '仓库'])
    book.active.append(['FEE-IMPORT', 'SC001', 'M-FG', 3, fee, '主仓'])
    stream = io.BytesIO()
    book.save(stream)
    book.close()
    stream.seek(0)
    result = client.post('/subcontract_receive/import', data={'file': (stream, 'fee.xlsx')})
    assert result.json['status'] == 'success', result.json
    with w.app.app_context():
        line = w.SubcontractReceiveItem.query.one()
        assert (line.price, line.amount) == (fee or 0, 3 * (fee or 0))


@pytest.mark.parametrize('entry', ['api', 'append'])
def test_optional_fee_when_receiving_by_id_or_appending(client, entry):
    with w.app.app_context():
        order = w.SubcontractOrder.query.one()
        oid, mid = order.id, w.Material.query.filter_by(code='M-FG').one().id
        if entry == 'append':
            draft = w.SubcontractReceive(receive_no='FEE-APPEND', subcontract_order_id=oid,
                                          warehouse=order.warehouse, status='pending')
            w.db.session.add(draft)
            w.db.session.commit()
            rid = draft.id
    if entry == 'api':
        result = client.post('/api/subcontract/quick_receive', json=dict(order_id=oid, material_id=mid, quantity=3, price=2))
    else:
        result = document_post(client, f'/subcontract_receive/{rid}/item/add', data=dict(material_code='M-FG', quantity=3, price=2))
    assert result.json['status'] == 'success', result.json
    with w.app.app_context():
        line = w.SubcontractReceiveItem.query.one()
        assert (line.price, line.amount) == (2, 6)


def test_old_monthly_system_template_and_custom_copy(client, tmp_path, monkeypatch):
    import io
    from datetime import date
    from openpyxl import Workbook, load_workbook

    folder = tmp_path / 'static'
    uploads = folder / 'uploads' / 'print_templates'
    uploads.mkdir(parents=True)
    monkeypatch.setattr(w.app, 'static_folder', str(folder))
    old = uploads / 'builtin_report_warehouse_monthly_default.xlsx'
    custom = uploads / 'custom_monthly.xlsx'
    book = Workbook()
    book.active.append(['自定义表头'])
    book.active.append(['{item.material_code}'])
    book.save(old)
    book.save(custom)
    book.close()
    original = old.read_bytes()
    with w.app.app_context():
        wh = w.Warehouse.query.one().id
        oid = w.SubcontractOrder.query.one().id
        w.set_system_setting('price_dimension_enabled', '1')
        for file in (old, custom):
            record = w.ExcelPrintTemplate(target_type='report', target_code='report_warehouse_monthly',
                                         template_type='excel', name=file.stem, is_default=file == old,
                                         excel_template_path='/static/uploads/print_templates/' + file.name)
            w.db.session.add(record)
        w.db.session.commit()
        custom_id = record.id
    assert client.post(f'/subcontract/{oid}/receive', data=dict(material_code='M-FG', quantity=3, price=2)).json['status'] == 'success'
    params = dict(warehouse_id=wh, start_month=date.today().strftime('%Y-%m'), end_month=date.today().strftime('%Y-%m'))
    for url in ('/report/api/warehouse_monthly', '/report/warehouse_monthly/print_excel'):
        response = client.get(url, query_string=dict(params, export='excel'))
        assert response.status_code == 200
        workbook = load_workbook(io.BytesIO(response.data), read_only=True)
        try:
            assert any('其中：委外收货参考估值' in row for row in workbook.active.values)
        finally:
            workbook.close()
    preview = client.get('/report/warehouse_monthly/print_preview', query_string=params)
    assert preview.status_code == 200 and '其中：委外收货参考估值' in preview.get_data(as_text=True)
    preview = client.get('/report/warehouse_monthly/print_preview', query_string=dict(params, template_id=custom_id))
    assert '自定义表头' in preview.get_data(as_text=True)
    assert old.read_bytes() == original


def test_disabled_product_selection_and_import_rollback(client):
    import io
    import json
    import re
    from openpyxl import Workbook
    with w.app.app_context():
        oid = w.SubcontractOrder.query.one().id
        product = w.Material.query.filter_by(code='M-FG').one()
        product.status = 'inactive'
        w.db.session.commit()
        before = snapshot()
    detail = client.get(f'/subcontract/{oid}').get_data(as_text=True)
    choices = json.loads(re.search(r'const subcontractMaterials = (.*?);\n', detail).group(1))
    assert 'M-RAW' in {row['code'] for row in choices}
    assert 'M-FG' not in {row['code'] for row in choices}
    file = io.BytesIO()
    workbook = Workbook()
    workbook.active.append(['入库单号', '委外加工单号', '物料编码', '收货数量', '单位加工费', '仓库'])
    for code in ('M-RAW', 'M-FG'):
        workbook.active.append(['SC-XLS', 'SC001', code, 1, 2, '主仓'])
    workbook.save(file)
    workbook.close()
    file.seek(0)
    result = client.post('/subcontract_receive/import', data={'file': (file, 'fee.xlsx')})
    assert result.status_code == 400 and 'M-FG' in result.json['msg']
    with w.app.app_context():
        assert snapshot() == before
