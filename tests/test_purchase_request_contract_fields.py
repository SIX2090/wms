"""Purchase-request line contracts survive the complete document flow, in memory only."""
from tests.document_revision_client import document_post
from datetime import date
import io
import json
import re

import app as w
from openpyxl import Workbook, load_workbook
import pytest


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        assert w.db.engine.url.database == ':memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='pr-contract-fixture', role='admin',
                      password_hash='fixture-unused', must_change_password=False)
        material = w.Material(code='PR-C-M', name='申请物料', stock=100, price=2)
        suppliers = [w.Supplier(code='PR-C-S' + str(i), name='申请供应商' + str(i)) for i in (1, 2)]
        warehouses = [w.Warehouse(code='PR-C-W' + str(i), name='申请仓' + str(i),
                                  status='active', is_default=i == 1) for i in (1, 2)]
        contracts = [w.Contract(contract_no=n, project_name=p) for n, p in [
            ('HT-001', '一号工程'), ('HT-002', '二号工程'), ('HT-IMPORT', '导入工程'),
            ('=1+1', '<b>工程</b>'), ('<b>HT</b>', '<script>工程</script>')]]
        contracts += [w.Contract(contract_no=f'HT-PRINT-{i:03}', project_name=f'工程{i:03}') for i in range(31)]
        w.db.session.add_all([user, material, *suppliers, *warehouses, *contracts])
        w.db.session.flush()
        for wh, qty in zip(warehouses, (30, 70)):
            w.db.session.add(w.StockTransaction(material_id=material.id, warehouse_id=wh.id,
                                                location=wh.name, quantity=qty, transaction_type='opening'))
        w.db.session.commit()
        ids = dict(user=user.id, material=material.id, suppliers=[s.id for s in suppliers])
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(ids['user'])
        session['_fresh'] = True
    yield client, ids
    with w.app.app_context():
        assert w.db.session.get(w.Material, ids['material']).stock == 100
        assert [float(t.quantity) for t in w.StockTransaction.query.order_by(w.StockTransaction.id)] == [30, 70]
        w.db.session.remove()
        w.db.drop_all()


def payload(ids, **extra):
    return dict(request_no='PR-CONTRACT', date=date.today().isoformat(),
                items=[dict(material_id=ids['material'], quantity=5, estimated_price=2,
                            contract_no=' HT-001 ', project_name=' 一号工程 ', remark=' 第一行手工备注 ', supplier_id=ids['suppliers'][0]),
                       dict(material_id=ids['material'], quantity=7, estimated_price=3,
                            contract_no='HT-002', project_name='二号工程', remark='第二行手工备注', supplier_id=ids['suppliers'][1])], **extra)


def save(client, body, mode='json'):
    response = document_post(client,'/purchase_request/add', **({mode: body} if mode == 'json' else
                          {'data': {**body, 'items': json.dumps(body['items'])}}))
    assert response.status_code == 200, response.get_data(as_text=True)
    result = response.get_json()
    assert result['status'] == 'success', result
    return result['id']


@pytest.mark.parametrize('mode', ['json', 'form'])
def test_purchase_request_line_fields_save_edit_reopen_and_clear(case, mode):
    client, ids = case
    body = payload(ids)
    request_id = save(client, body, mode)
    with w.app.app_context():
        lines = w.PurchaseRequestItem.query.order_by(w.PurchaseRequestItem.id).all()
        assert [(getattr(x, 'contract_no', None), getattr(x, 'project_name', None)) for x in lines] == [
            ('HT-001', '一号工程'), ('HT-002', '二号工程')]
        assert w.db.session.get(w.PurchaseRequest, request_id).total_amount == 31
    page = client.get(f'/purchase_request/{request_id}/edit').get_data(as_text=True)
    initial = json.loads(re.search(r'const initialItems = (.*?);', page)[1])
    assert [(x['contract_no'], x['project_name']) for x in initial] == [('HT-001', '一号工程'), ('HT-002', '二号工程')]
    assert [x['remark'] for x in initial] == ['第一行手工备注', '第二行手工备注']
    body['request_id'] = request_id
    body['items'][0].update(contract_no='', project_name='', remark='修订备注')
    save(client, body, mode)
    with w.app.app_context():
        lines = w.PurchaseRequestItem.query.order_by(w.PurchaseRequestItem.id).all()
        assert [(x.contract_no or '', x.project_name or '') for x in lines] == [('', ''), ('HT-002', '二号工程')]
        assert [x.remark for x in lines] == ['修订备注', '第二行手工备注']


@pytest.mark.parametrize('split_suppliers', [False, True])
def test_purchase_request_contracts_follow_selected_push_without_merging_lines(case, split_suppliers):
    client, ids = case
    body = payload(ids)
    if not split_suppliers:
        body['items'][1]['supplier_id'] = body['items'][0]['supplier_id']
    request_id = save(client, body)
    with w.app.app_context():
        order = w.db.session.get(w.PurchaseRequest, request_id)
        order.status = 'approved'
        lines = sorted(order.items, key=lambda x: x.id)
        selected = [dict(item_id=x.id, quantity=2) for x in lines]
        w.db.session.commit()
    response = document_post(client,f'/purchase_request/{request_id}/create_purchase_order', json={'items': selected})
    assert response.status_code == 200 and response.get_json()['status'] == 'success'
    with w.app.app_context():
        items = w.PurchaseOrderItem.query.order_by(w.PurchaseOrderItem.id).all()
        assert [(x.contract_no, x.project_name, x.quantity) for x in items] == [
            ('HT-001', '一号工程', 2), ('HT-002', '二号工程', 2)]
        assert w.PurchaseOrder.query.count() == (2 if split_suppliers else 1)
        assert [x.remark for x in items] == ['第一行手工备注', '第二行手工备注']
        expected = {}
        for item in items:
            expected.setdefault(item.purchase_order_id, []).append((item.contract_no, item.project_name, item.remark))
    for order_id, values in expected.items():
        response = client.get(f'/purchase_order/{order_id}?embedded=1')
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert '来源申请' in html and f'/purchase_request/{request_id}' in html
        for contract_no, project_name, remark in values:
            assert contract_no in html and project_name in html and remark in html


def test_purchase_request_detail_print_export_and_import_template_keep_line_fields(case):
    client, ids = case
    request_id = save(client, payload(ids))
    for path in [f'/purchase_request/{request_id}', f'/purchase_request/{request_id}/print']:
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert all(value in html for value in ['合同编号', 'HT-001', 'HT-002', '备注', '第一行手工备注', '第二行手工备注'])
        if not path.endswith('/print'):
            assert all(value in html for value in ['工程名称', '一号工程', '二号工程'])
        else:
            assert '一号工程' not in html and '二号工程' not in html
    response = client.get('/purchase_request/export')
    workbook = load_workbook(io.BytesIO(response.data))
    rows = list(workbook.active.values)
    headers = rows[0]
    assert [(r[headers.index('合同编号')], r[headers.index('工程名称')]) for r in rows[1:]] == [
        ('HT-001', '一号工程'), ('HT-002', '二号工程')]
    assert [r[headers.index('备注')] for r in rows[1:]] == ['第一行手工备注', '第二行手工备注']
    template = client.get('/export/template/purchase_request')
    sheet = load_workbook(io.BytesIO(template.data)).active
    assert '合同编号' in [c.value for c in sheet[1]] and '工程名称' in [c.value for c in sheet[1]]


@pytest.mark.parametrize('field,value', [('contract_no', 'X' * 51), ('project_name', '工' * 201),
                                        ('contract_no', {'bad': 'type'}), ('project_name', [1]),
                                        ('remark', '备' * 201), ('remark', ['bad'])])
def test_purchase_request_invalid_contract_fields_reject_without_destroying_existing_lines(case, field, value):
    client, ids = case
    body = payload(ids)
    request_id = save(client, body)
    body['request_id'] = request_id
    body['items'][0][field] = value
    response = document_post(client,'/purchase_request/add', json=body)
    assert response.status_code == 400
    with w.app.app_context():
        assert w.PurchaseRequestItem.query.count() == 2
        assert w.PurchaseRequestItem.query.order_by(w.PurchaseRequestItem.id).first().contract_no == 'HT-001'


@pytest.mark.parametrize('invalid', [False, True])
def test_purchase_request_excel_import_preserves_contracts_or_rejects_long_text(case, invalid):
    client, ids = case
    workbook = Workbook()
    workbook.active.append(['申请编号', '物料编码', '数量', '合同编号', '工程名称', '备注'])
    workbook.active.append(['PR-IMPORT-C', 'PR-C-M', 3, 'HT-IMPORT', '旧工程名', '导入备注'])
    if invalid:
        workbook.active.append(['PR-IMPORT-C', 'PR-C-M', 2, 'X' * 51, '不可导入'])
    data = io.BytesIO()
    workbook.save(data)
    data.seek(0)
    response = document_post(client,'/purchase_request/import', data={'file': (data, 'request.xlsx')})
    assert response.status_code == (400 if invalid else 200), response.get_data(as_text=True)
    with w.app.app_context():
        if invalid:
            assert w.PurchaseRequest.query.count() == 0 and w.PurchaseRequestItem.query.count() == 0
        else:
            item = w.PurchaseRequestItem.query.one()
            assert item.contract_no == 'HT-IMPORT' and item.project_name == '导入工程'
            assert item.remark == '导入备注'


def test_purchase_request_contract_changes_participate_in_idempotency(case):
    client, ids = case
    body = payload(ids)
    headers = {'X-Idempotency-Key': 'pr-contract-field-save'}
    first = document_post(client,'/purchase_request/add', json=body, headers=headers)
    replay = document_post(client,'/purchase_request/add', json=body, headers=headers)
    assert first.status_code == replay.status_code == 200
    assert first.get_json() == replay.get_json()
    body['items'][0]['contract_no'] = 'CHANGED'
    assert document_post(client,'/purchase_request/add', json=body, headers=headers).status_code == 409
    with w.app.app_context():
        assert w.PurchaseRequest.query.count() == 1 and w.PurchaseRequestItem.query.count() == 2
        assert w.PurchaseRequestItem.query.order_by(w.PurchaseRequestItem.id).first().contract_no == 'HT-001'


def test_purchase_request_contract_text_is_escaped_on_screen_and_literal_in_excel(case):
    client, ids = case
    body = payload(ids)
    body['items'][0].update(contract_no='=1+1', project_name='<b>工程</b>')
    request_id = save(client, body)
    html = client.get(f'/purchase_request/{request_id}').get_data(as_text=True)
    assert '&lt;b&gt;工程&lt;/b&gt;' in html and '<b>工程</b>' not in html
    sheet = load_workbook(io.BytesIO(client.get('/purchase_request/export').data)).active
    headers = [cell.value for cell in sheet[1]]
    cell = sheet.cell(2, headers.index('合同编号') + 1)
    assert cell.value == '=1+1' and cell.data_type == 's'


def test_purchase_request_legacy_payload_remains_valid_without_contract_fields(case):
    client, ids = case
    body = payload(ids)
    for item in body['items']:
        item.pop('contract_no')
        item.pop('project_name')
    request_id = save(client, body)
    with w.app.app_context():
        assert all(not getattr(item, 'contract_no', None) and not getattr(item, 'project_name', None)
                   for item in w.db.session.get(w.PurchaseRequest, request_id).items)


@pytest.mark.parametrize('count,pages', [(0, 1), (1, 1), (15, 1), (16, 2), (31, 3)])
def test_purchase_request_material_print_uses_requested_columns_and_keeps_every_line(case, count, pages):
    client, ids = case
    body = payload(ids)
    body['date'] = '2026-01-02'
    body['items'] = [dict(material_id=ids['material'], quantity=i + 1, estimated_price=2,
                          contract_no=f'HT-PRINT-{i:03}', project_name=f'工程{i:03}',
                          remark=f'备注{i:03}') for i in range(count)]
    if count:
        request_id = save(client, body)
    else:
        with w.app.app_context():
            order = w.PurchaseRequest(request_no='PR-PRINT-EMPTY', date=date(2026, 1, 2),
                                      operator_id=ids['user'], status='pending')
            w.db.session.add(order)
            w.db.session.commit()
            request_id = order.id
    response = client.get(f'/purchase_request/{request_id}/print')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '材料申请单' in html
    assert html.count('class="material-request-sheet"') == pages
    assert re.findall(r'<th[^>]*>([^<]*)</th>', html) == [
        '序号', '合同编号', '名称', '规格', '单位', '数量', '备注'] * pages
    assert html.count('class="detail-row"') == pages * 15
    for i in range(count):
        assert html.count(f'HT-PRINT-{i:03}') == 1
        assert f'工程{i:03}' not in html and f'备注{i:03}' in html
    assert html.count('2026-01-02') == pages
    assert '预计单价' not in html and '预估金额' not in html


def test_purchase_request_material_print_escapes_text_and_supports_manual_materials(case):
    client, ids = case
    body = payload(ids)
    body['items'] = [dict(material_name='手工材料', material_code='', spec='手工规格', quantity=3,
                          contract_no='<b>HT</b>', project_name='<script>工程</script>', remark='<img src=x>')]
    request_id = save(client, body)
    html = client.get(f'/purchase_request/{request_id}/print').get_data(as_text=True)
    assert '手工材料' in html and '手工规格' in html
    assert '&lt;b&gt;HT&lt;/b&gt;' in html and '<b>HT</b>' not in html
    assert '&lt;script&gt;工程&lt;/script&gt;' not in html and '<script>工程</script>' not in html
    assert '&lt;img src=x&gt;' in html and '<img src=x>' not in html
    assert w.app.test_client().get(f'/purchase_request/{request_id}/print').status_code == 302


def test_resolve_purchase_request_line_fields(case):
    from routes.purchase_request import resolve_purchase_request_line_fields
    client, ids = case
    body = payload(ids)
    body['items'][0]['project_name'] = '伪造工程'
    request_id = save(client, body)
    with w.app.app_context():
        fields = resolve_purchase_request_line_fields(body['items'][0])
        assert fields.project_name == '一号工程' and fields.remark == '第一行手工备注'
        item = w.db.session.get(w.PurchaseRequest, request_id).items[0]
        assert item.contract_no == 'HT-001' and item.project_name == '一号工程'
        assert item.remark == '第一行手工备注'


@pytest.mark.parametrize('contract_no,project_name', [('UNKNOWN', ''), ('', '无合同的工程')])
def test_purchase_request_unknown_master_reference_keeps_existing_lines(case, contract_no, project_name):
    client, ids = case
    body = payload(ids)
    body['request_id'] = save(client, body)
    body['items'][0].update(contract_no=contract_no, project_name=project_name)
    response = document_post(client, '/purchase_request/add', json=body)
    assert response.status_code == 400 and '合同' in response.get_json()['msg']
    with w.app.app_context():
        items = w.PurchaseRequestItem.query.order_by(w.PurchaseRequestItem.id).all()
        assert len(items) == 2 and items[0].contract_no == 'HT-001'
        assert items[0].remark == '第一行手工备注'


def test_purchase_request_master_rename_sync_and_both_delete_guards_keep_manual_remark(case):
    client, ids = case
    request_id = save(client, payload(ids))
    with w.app.app_context():
        contract_id = w.Contract.query.filter_by(contract_no='HT-001').one().id
    response = document_post(client, f'/contract/{contract_id}/edit', data={
        'contract_no': 'HT-RENAMED', 'project_name': '新工程', 'status': 'active'})
    assert response.status_code == 200 and response.get_json()['status'] == 'success'
    with w.app.app_context():
        items = sorted(w.db.session.get(w.PurchaseRequest, request_id).items, key=lambda x: x.id)
        assert (items[0].contract_no, items[0].project_name, items[0].remark) == (
            'HT-RENAMED', '新工程', '第一行手工备注')
        assert (items[1].contract_no, items[1].project_name) == ('HT-002', '二号工程')
    for path, body in [(f'/contract/{contract_id}/delete', {}), ('/contract/delete', {'ids': [contract_id]})]:
        response = document_post(client, path, json=body)
        assert response.get_json()['status'] == 'error' and '采购申请' in response.get_json()['msg']
    with w.app.app_context():
        assert w.db.session.get(w.Contract, contract_id) is not None
