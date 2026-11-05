"""Purchase-request material form uses the existing Excel center, in isolation."""
from datetime import date
import io
from pathlib import Path
from types import SimpleNamespace

from openpyxl import load_workbook
import pytest
import app as w
import doc_print_excel as dpe


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setattr(w.app, 'static_folder', str(tmp_path))
    with w.app.app_context():
        assert w.db.engine.url.database == ':memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='pr-excel-admin', role='admin', password_hash='unused', must_change_password=False)
        unit = w.Unit(code='PR-X-U', name='米')
        w.db.session.add_all([user, unit])
        w.db.session.flush()
        order = w.PurchaseRequest(request_no='PR-EXCEL-001', date=date(2026, 11, 5), operator_id=user.id)
        w.db.session.add(order)
        w.db.session.flush()
        w.db.session.add(w.PurchaseRequestItem(purchase_request_id=order.id, material_name='宝胜电线',
                         spec='ZB-BV-450/750V', unit_id=unit.id, quantity=100,
                         contract_no='HD260921', project_name='不进入备注的工程', remark='2026-11-9用'))
        w.db.session.commit()
        ids = user.id, order.id
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(ids[0])
        session['_fresh'] = True
    yield client, ids[1], tmp_path
    with w.app.app_context():
        w.db.session.remove()
        w.db.drop_all()


def test_generate_purchase_request_template():
    content = dpe.generate_builtin_template('purchase_request')
    assert content is not None
    sheet = load_workbook(content).active
    assert sheet['A1'].value == '广东惠电科技发展有限公司'
    assert sheet['A2'].value == '材料申请单'
    assert [c.value for c in sheet[5]] == ['序号', '合同编号', '名称', '规格', '单位', '数量', '备注']
    assert sheet['A21'].value == '制表：余国珍'
    assert sheet['F21'].value == '日期：{order.date}'
    assert sheet.page_setup.orientation == 'portrait'
    assert str(sheet.page_setup.paperSize) == sheet.PAPERSIZE_A4


def test_purchase_request_print_rows():
    item = SimpleNamespace(material=None, material_name='手工材料', spec=None, unit=SimpleNamespace(name='米'),
                           quantity=2.5, contract_no='HT-A', project_name='工程A', remark='手工备注')
    rows = dpe.purchase_request_print_rows([item])
    assert rows[0].material_name == '手工材料' and rows[0].spec == ''
    assert rows[0].unit_name == '米' and rows[0].remark == '手工备注'
    assert rows[0].sequence == 1 and rows[0].project_name == '工程A'


@pytest.mark.parametrize('count,pages', [(0, 1), (1, 1), (15, 1), (16, 2), (31, 3)])
def test_render_purchase_request_excel(tmp_path, count, pages):
    template = tmp_path / 'template.xlsx'
    content = dpe.generate_builtin_template('purchase_request')
    assert content is not None
    template.write_bytes(content.read())
    order = SimpleNamespace(date=date(2026, 11, 5))
    items = [SimpleNamespace(material_name=f'材料{i}', material=None, spec='', unit=None, quantity=i + .5,
                             contract_no=f'HT-{i:03}', project_name='不进入备注的工程', remark=f'备注{i:03}') for i in range(count)]
    book = load_workbook(dpe.render_purchase_request_excel(str(template), order, items))
    assert len(book.worksheets) == pages
    for page, sheet in enumerate(book.worksheets):
        assert sheet['A1'].value == '广东惠电科技发展有限公司'
        assert sheet['A21'].value == '制表：余国珍' and sheet['F21'].value == '日期：2026-11-05'
        assert [sheet.cell(r, 1).value for r in range(6, 21)] == list(range(page * 15 + 1, page * 15 + 16))
        for row in sheet.iter_rows():
            assert not any(isinstance(c.value, str) and '{item.' in c.value for c in row)
            assert not any(c.value == '不进入备注的工程' for c in row)
    contracts = [row[1].value for s in book for row in s.iter_rows(min_row=6, max_row=20)]
    assert [v for v in contracts if v] == [f'HT-{i:03}' for i in range(count)]


def test_center_entry_and_excel_print_do_not_create_template_records(case):
    client, oid, _ = case
    for path in ['/print_templates?target_type=document&target_code=purchase_request', f'/purchase_request/{oid}']:
        response = client.get(path)
        assert response.status_code == 200
        assert '采购申请' in response.get_data(as_text=True)
        assert '打印模板' in response.get_data(as_text=True)
    html = client.get('/print_templates?target_type=document&target_code=purchase_request').get_data(as_text=True)
    assert '材料申请单' in html and '新建并在线编辑' in html
    response = client.get(f'/purchase_request/{oid}/print_excel')
    assert response.status_code == 200
    sheet = load_workbook(io.BytesIO(response.data)).active
    assert [sheet.cell(6, c).value for c in range(2, 8)] == ['HD260921', '宝胜电线', 'ZB-BV-450/750V', '米', 100, '2026-11-9用']
    with w.app.app_context():
        assert w.ExcelPrintTemplate.query.count() == 0
        assert w.PurchaseRequestItem.query.one().remark == '2026-11-9用'


def test_download_builtin_print_template(case):
    client, _, _ = case
    response = client.get('/print_templates/builtin/purchase_request/download')
    assert response.status_code == 200
    assert load_workbook(io.BytesIO(response.data)).active['A2'].value == '材料申请单'
    with w.app.app_context():
        assert w.ExcelPrintTemplate.query.count() == 0
    assert client.get('/print_templates/builtin/not_registered/download').status_code == 404
    assert w.app.test_client().get('/print_templates/builtin/purchase_request/download').status_code in (302, 401)


def test_center_edit_default_and_actual_print_round_trip(case):
    client, oid, static = case
    response = client.post('/print_templates/create_blank', data={
        'name': '材料申请单自定义', 'target_type': 'document', 'target_code': 'purchase_request'})
    assert response.status_code == 302
    with w.app.app_context():
        record = w.ExcelPrintTemplate.query.one()
        tid = record.id
    grid = client.get(f'/global_print_template/{tid}/grid').get_json()
    assert grid['status'] == 'success' and grid['sheets'][0]['name'] == '材料申请单'
    name = grid['sheets'][0]['name']
    saved = client.post(f'/global_print_template/{tid}/grid', json={'sheets': [{
        'name': name, 'upserts': [[1, 1, '编辑后的公司抬头']],
        'col_widths': {'2': 19}, 'row_heights': {'6': 25},
        'styles': [[1, 1, {'font_size': 18, 'bold': True}]],
    }]})
    assert saved.status_code == 200 and saved.get_json()['status'] == 'success'
    assert client.post(f'/print_templates/{tid}/set_default').get_json()['status'] == 'success'
    response = client.get(f'/purchase_request/{oid}/print')
    assert response.status_code == 200 and 'spreadsheetml' in response.content_type
    sheet = load_workbook(io.BytesIO(response.data)).active
    assert sheet['A1'].value == '编辑后的公司抬头'
    assert sheet['A1'].font.sz == 18 and sheet['A1'].font.bold
    assert sheet.column_dimensions['B'].width == 19 and sheet.row_dimensions[6].height == 25
    assert sheet['G6'].value == '2026-11-9用'
    plain = client.get(f'/purchase_request/{oid}/print?format=html')
    assert plain.status_code == 200 and 'text/html' in plain.content_type
    assert '材料申请单' in plain.get_data(as_text=True)


def test_excel_print_keeps_formula_looking_business_text_literal(case):
    client, oid, _ = case
    with w.app.app_context():
        item = w.PurchaseRequestItem.query.one()
        item.contract_no = '=1+1'
        item.remark = '=HYPERLINK("https://example.test")'
        w.db.session.commit()
    response = client.get(f'/purchase_request/{oid}/print_excel')
    assert response.status_code == 200
    sheet = load_workbook(io.BytesIO(response.data)).active
    assert sheet['B6'].value == '=1+1' and sheet['B6'].data_type == 's'
    assert sheet['G6'].value.startswith('=HYPERLINK') and sheet['G6'].data_type == 's'


def test_bad_excel_template_keeps_plain_print_available(case):
    client, oid, static = case
    path = static / 'uploads/print_templates/bad.xlsx'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'not an Excel archive')
    with w.app.app_context():
        w.db.session.add(w.ExcelPrintTemplate(name='坏模板', target_type='document', target_code='purchase_request',
            excel_template_path='/static/uploads/print_templates/bad.xlsx', is_default=True, template_type='excel'))
        w.db.session.commit()
    plain = client.get(f'/purchase_request/{oid}/print')
    assert plain.status_code == 200 and 'text/html' in plain.content_type
    assert 'Excel模板暂不可用' in plain.get_data(as_text=True)
    assert '材料申请单' in plain.get_data(as_text=True)
    excel = client.get(f'/purchase_request/{oid}/print_excel')
    assert excel.status_code == 400 and '普通打印' in excel.get_json()['msg']


def test_uploaded_logo_and_footer_survive_request_pagination(tmp_path):
    import base64
    from openpyxl.drawing.image import Image
    book = dpe.generate_purchase_request_template()
    image = Image(io.BytesIO(base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')))
    book.active.add_image(image, 'G1')
    book.active.oddFooter.left.text = '自定义页脚'
    path = tmp_path / 'logo.xlsx'
    book.save(path)
    before = path.read_bytes()
    items = [SimpleNamespace(material_name='测试材料', material=None, unit=None, quantity=1) for _ in range(16)]
    result = load_workbook(dpe.render_purchase_request_excel(path, SimpleNamespace(date=date(2026,11,5)), items))
    assert len(result.worksheets) == 2
    assert all(len(s._images) == 1 and s.oddFooter.left.text == '自定义页脚' for s in result)
    assert path.read_bytes() == before
