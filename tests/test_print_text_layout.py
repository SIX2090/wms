"""Printed text must fit its own row without altering data or saved templates."""
from datetime import date
import io
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
import pytest
from tests.test_document_print_flow import KINDS, print_case


def _layout():
    from services.excel_print_layout import fit_print_rows, print_column_width, print_row_height
    return fit_print_rows, print_column_width, print_row_height


def test_print_column_width():
    _, width, _ = _layout()
    sheet = Workbook().active
    sheet.sheet_format.defaultColWidth = 9
    assert width(sheet, 1) == 68
    sheet.column_dimensions['A'].width = 5
    assert width(sheet, 1) == 40
    sheet.column_dimensions.group('B', 'D', hidden=True)
    assert [width(sheet, col) for col in (2, 3, 4)] == [0, 0, 0]


def test_print_row_height():
    _, _, height = _layout()
    sheet = Workbook().active
    sheet.sheet_format.defaultRowHeight = 23
    assert height(sheet, 1) == 23
    sheet.row_dimensions[2].height = 40
    sheet.row_dimensions[3].hidden = True
    assert height(sheet, 2) == 40 and height(sheet, 3) == 0


@pytest.mark.parametrize('wrapped', [False, True])
def test_fit_print_rows(wrapped):
    fit, _, _ = _layout()
    sheet = Workbook().active
    sheet.column_dimensions['A'].width = 16.5
    sheet['A1'] = 'ZB-BVR-450/750V\n1*2.5mm² 黄绿双色'
    sheet['A1'].font = Font(name='宋体', size=10)
    sheet['A1'].alignment = Alignment(wrap_text=wrapped, vertical='center')
    sheet.row_dimensions[1].height = 20
    sheet['A2'] = '下一条明细'
    sheet['A3'] = '合计及签字'
    before = [cell.value for row in sheet for cell in row]
    fit(sheet)
    assert sheet.row_dimensions[1].height >= 36
    assert sheet['A1'].alignment.wrap_text
    assert [cell.value for row in sheet for cell in row] == before
    first = dict((row, dimension.height) for row, dimension in sheet.row_dimensions.items())
    fit(sheet)
    assert {row: dimension.height for row, dimension in sheet.row_dimensions.items()} == first


def test_fit_print_rows_preserves_merges_hidden_data_and_print_area():
    fit, _, _ = _layout()
    sheet = Workbook().active
    sheet.column_dimensions['A'].width = sheet.column_dimensions['B'].width = 9
    sheet.merge_cells('A1:B2')
    sheet['A1'] = '完整工程名称及设备规格' * 8
    sheet['A1'].font = Font(size=11)
    sheet['A1'].alignment = Alignment(wrap_text=True)
    sheet.row_dimensions[1].height = sheet.row_dimensions[2].height = 15
    sheet['A3'] = '隐藏数据' * 100
    sheet.row_dimensions[3].hidden = True
    sheet['A4'] = '打印区域之外' * 100
    sheet.print_area = 'A1:B3'
    before_area = str(sheet.print_area)
    fit(sheet)
    assert sheet.row_dimensions[2].height > 15
    assert sheet.row_dimensions[3].hidden and sheet.row_dimensions[3].height is None
    assert sheet.row_dimensions[4].height is None
    assert str(sheet.merged_cells) == 'A1:B2'
    assert str(sheet.print_area) == before_area


def test_fit_print_rows_rejects_unprintable_text_instead_of_silent_clipping():
    fit, _, _ = _layout()
    sheet = Workbook().active
    sheet.column_dimensions['A'].width = 5
    sheet['A1'] = '超长规格' * 1000
    fit(sheet)
    assert sheet.row_dimensions[1].height <= 409.5
    with pytest.raises(ValueError, match='A1.*内容过长'):
        fit(sheet, strict=True)


def test_build_document_excel_preview_grows_rows_and_keeps_every_following_cell():
    from services.document_excel_preview import build_document_excel_preview
    book = Workbook()
    sheet = book.active
    sheet.column_dimensions['A'].width = 16.5
    sheet['A1'] = 'ZB-BVR-450/750V\n1*2.5mm² 黄绿双色'
    sheet['A1'].font = Font(name='宋体', size=10)
    sheet['A1'].alignment = Alignment(wrap_text=True)
    sheet.row_dimensions[1].height = 20
    sheet['A2'] = 'NEXT-DETAIL'
    sheet['A3'] = 'FOOTER-KEEP'
    stream = io.BytesIO()
    book.save(stream)
    original = stream.getvalue()
    pages = build_document_excel_preview(stream)
    cells = [cell for page in pages for cell in page['cells']]
    text = next(cell for cell in cells if 'ZB-BVR' in cell['text'])
    following = next(cell for cell in cells if cell['text'] == 'NEXT-DETAIL')
    assert text['height'] >= 48
    assert following['top'] >= text['top'] + text['height'] - .01
    assert next(cell for cell in cells if cell['text'] == 'FOOTER-KEEP')
    assert stream.getvalue() == original


def test_build_filled_print_excel_autofits_and_does_not_modify_template(tmp_path):
    from print_fill import build_filled_print_excel
    book = Workbook()
    sheet = book.active
    sheet.column_dimensions['A'].width = 12
    sheet['A1'] = '{item.name}'
    sheet['A1'].font = Font(size=11)
    sheet['A1'].alignment = Alignment(wrap_text=True)
    sheet.row_dimensions[1].height = 20
    sheet['A2'] = '合计：{total_quantity}'
    path = tmp_path / 'print.xlsx'
    book.save(path)
    original = path.read_bytes()
    result = load_workbook(build_filled_print_excel(path, SimpleNamespace(items=[]),
        items=[SimpleNamespace(name='长名称及完整规格' * 8, quantity=1)]))
    assert result.active.row_dimensions[1].height > 20
    assert result.active['A1'].value == '长名称及完整规格' * 8
    assert result.active['A2'].value == '合计：1.0'
    assert path.read_bytes() == original


def test_fixed_purchase_request_and_product_pages_fit_long_specs(tmp_path):
    import doc_print_excel as templates
    from services.product_receipt_print import build_product_receipt_excel
    from services.document_excel_preview import build_document_excel_preview
    path = tmp_path / 'purchase.xlsx'
    path.write_bytes(templates.generate_builtin_template('purchase_request').getvalue())
    order = SimpleNamespace(date=date(2026, 11, 7))
    item = SimpleNamespace(material=None, material_name='宝胜电线', spec='ZB-BVR-450/750V\n1*2.5mm² 黄绿双色',
        unit=None, quantity=1000, contract_no='HD260921', project_name='', remark='')
    content = templates.render_purchase_request_excel(path, order, [item])
    sheet = load_workbook(content).active
    assert sheet.row_dimensions[6].height > 20
    assert len(build_document_excel_preview(content)) == 1
    product = SimpleNamespace(date=date(2026, 11, 7), customer=SimpleNamespace(name='客户'), contract_no='HD260921',
        project_name='工程', operator=SimpleNamespace(username='制单'), order_no='PI-PRINT-LAYOUT',
        items=[SimpleNamespace(id=1, box_no='001-A', material=SimpleNamespace(name='配电柜', spec='完整规格\n' * 4, unit=SimpleNamespace(name='台')),
            unit=SimpleNamespace(name='台'), quantity=1, price=2, amount=2, remark='')])
    output = build_product_receipt_excel(product)
    cells = [cell for page in build_document_excel_preview(output) for cell in page['cells']]
    assert any(cell['text'] == '001-A' for cell in cells)
    assert any(cell['text'] == '完整规格\n' * 4 and cell['height'] > 40 for cell in cells)


def test_document_preview_cells_use_bounded_flex_boxes():
    root = Path(__file__).resolve().parents[1]
    html = (root / 'app/templates/document_excel_preview.html').read_text(encoding='utf-8')
    import re
    rule = re.search(r'\.excel-cell\s*\{([^}]+)', html).group(1)
    assert 'display:flex' in rule.replace(' ', '')
    assert 'display:table;' not in rule


def test_print_cell_width():
    from services.excel_print_layout import print_cell_width, fit_print_rows
    from openpyxl.styles import Border, Side
    sheet = Workbook().active
    sheet.column_dimensions['A'].width = 5
    sheet['A1'] = '制表：余国珍'
    sheet['D1'] = '日期'
    sheet.print_area = 'A1:D3'
    assert print_cell_width(sheet, sheet['A1'], 4) > 150
    sheet['B2'] = '另一字段'
    sheet['A2'] = '表格内容'
    assert print_cell_width(sheet, sheet['A2'], 4) == 40
    sheet['A3'] = '明细'
    sheet['A3'].border = Border(right=Side(style='thin'))
    assert print_cell_width(sheet, sheet['A3'], 4) == 40
    fit_print_rows(sheet)
    assert not sheet['A1'].alignment.wrap_text
    assert sheet.row_dimensions[1].height <= 20


@pytest.mark.parametrize('code', list(KINDS))
def test_all_document_print_files_fit_long_specs_without_losing_values(print_case, code):
    import app as w
    client, docs, _ = print_case
    text = 'ZB-BVR-450/750V\n1*2.5mm² 黄绿双色\n完整设备型号及技术规格'
    with w.app.app_context():
        material = w.db.session.get(w.Material, 1)
        material.spec = text
        for name in ('PurchaseRequestItem',):
            for item in getattr(w, name).query.all():
                item.spec = text
        w.db.session.commit()
    prefix = 'sales' if code == 'sales_order' else code
    response = client.get(f'/{prefix}/{docs[code]}/print_file')
    assert response.status_code == 200
    book = load_workbook(io.BytesIO(response.data))
    found = [(sheet, cell) for sheet in book for row in sheet for cell in row if cell.value == text]
    assert found, code
    assert all(sheet.row_dimensions[cell.row].height > 20 for sheet, cell in found), code
    preview = client.get(f'/{prefix}/{docs[code]}/print_preview')
    assert preview.status_code == 200 and text in preview.get_data(as_text=True), code


def test_build_excel_label_preview_fits_materials_independently_and_keeps_images(tmp_path):
    import base64
    from openpyxl.drawing.image import Image
    from services.label_excel_preview import build_excel_label_preview
    book = Workbook()
    sheet = book.active
    sheet.column_dimensions['A'].width = 16.5
    sheet['A1'] = '{item.name}'
    sheet['A2'] = '{item.spec}'
    for row in (1, 2):
        sheet.row_dimensions[row].height = 20
        sheet.cell(row, 1).alignment = Alignment(wrap_text=True)
    sheet.print_area = 'A1:B4'
    raw = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    sheet.add_image(Image(io.BytesIO(raw)), 'B4')
    path = tmp_path / 'labels.xlsx'
    book.save(path)
    original = path.read_bytes()
    long_name = '完整设备名称和技术规格' * 8
    labels = build_excel_label_preview(path, [dict(code='001-A', name=long_name, spec='规格'),
        dict(code='002-B', name='设备', spec='规格')])
    first = next(cell for cell in labels[0]['cells'] if cell['text'] == long_name)
    second = next(cell for cell in labels[1]['cells'] if cell['text'] == '设备')
    assert first['height'] > second['height']
    assert all((label['width'], label['height']) == (90, 50) for label in labels)
    assert all(label['images'][0]['src'].startswith('data:image/png;base64,') for label in labels)
    assert labels[0]['images'][0]['top'] > labels[1]['images'][0]['top']
    assert path.read_bytes() == original


def test_partial_excel_borders_preserve_text_in_the_browser_preview():
    from openpyxl.styles import Border, Side
    from services.document_excel_preview import build_document_excel_preview
    book = Workbook()
    book.active['A1'] = '只有右边框'
    book.active['A1'].border = Border(right=Side(style='thin'))
    content = io.BytesIO()
    book.save(content)
    cells = build_document_excel_preview(content)[0]['cells']
    assert cells[0]['text'] == '只有右边框' and 'border-right:' in cells[0]['css']


@pytest.mark.parametrize('count', [0, 1, 5])
def test_fill_sheet_moves_footer_dimensions_and_discards_replaced_sample_merges(count):
    from print_fill import _Filler
    from services.report_print_preview import _fill_sheet
    book = Workbook()
    sheet = book.active
    sheet['A1'] = '模板标题'
    sheet.merge_cells('A1:B1')
    sheet['A2'] = '{item.name}'
    sheet.row_dimensions[2].height = 25
    for row in range(2, 5):
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    sheet['A5'] = '合计：{total_quantity}'
    sheet.merge_cells('A5:B5')
    sheet.row_dimensions[5].height = 55
    sheet['A6'] = '原有隐藏附注'
    sheet.row_dimensions[6].hidden = True
    sheet.print_area = 'A1:B6'
    _fill_sheet(sheet, _Filler(SimpleNamespace(),
        [SimpleNamespace(name=f'ITEM-{index}', quantity=1) for index in range(count)], '2026-11-07'))
    footer = 2 + max(1, count)
    assert sheet.cell(footer, 1).value == f'合计：{float(count) if count else 0}'
    assert sheet.row_dimensions[footer].height == 55
    assert sheet.row_dimensions[footer + 1].hidden
    assert str(sheet.merged_cells) == ' '.join(f'A{row}:B{row}' for row in range(1, footer + 1))
    assert [sheet.cell(row, 1).value for row in range(2, footer)] == (
        [f'ITEM-{index}' for index in range(count)] if count else [''])


def test_report_preview_preserves_excel_footer_spill_without_clipping(tmp_path):
    from services.report_print_preview import build_report_print_preview
    book = Workbook()
    sheet = book.active
    sheet.column_dimensions['A'].width = 5
    sheet['A1'] = '报表标题'
    sheet.merge_cells('A1:D1')
    sheet['A2'] = '{item.name}'
    sheet['A3'] = '制表：余国珍'
    sheet['D3'] = '日期：{print_date}'
    path = tmp_path / 'footer.xlsx'
    book.save(path)
    result = build_report_print_preview('报告', [{'field': 'name', 'title': '名称'}],
        [{'name': '材料', 'quantity': 1}], template_path=path)[0]
    footer = next(row for row in result['rows'] if any(cell['text'] == '制表：余国珍' for cell in row['cells']))
    assert len(footer['cells']) == 2
    assert footer['cells'][0]['colspan'] == 3
    assert footer['cells'][1]['text'].startswith('日期：')


def test_report_preview_merge_spans_count_only_visible_rows_and_columns(tmp_path):
    from services.report_print_preview import build_report_print_preview
    book = Workbook()
    sheet = book.active
    sheet['A1'] = '完整合并标题'
    sheet.merge_cells('A1:D2')
    sheet.column_dimensions['B'].hidden = True
    sheet.row_dimensions[2].hidden = True
    sheet['A3'] = '{item.name}'
    sheet['D3'] = '{item.quantity}'
    sheet['A4'] = '合计：{total_quantity}'
    path = tmp_path / 'hidden.xlsx'
    book.save(path)
    result = build_report_print_preview('报告', [{'field': 'name', 'title': '名称'}],
        [{'name': '材料', 'quantity': 1}], template_path=path)[0]
    title = next(cell for row in result['rows'] for cell in row['cells'] if cell['text'] == '完整合并标题')
    assert title['colspan'] == 3 and title['rowspan'] == 1
    assert len(result['widths']) == 3


def test_excel_label_cells_keep_print_line_height_independent_of_bootstrap():
    import re
    root = Path(__file__).resolve().parents[1]
    html = (root / 'app/templates/print_batch_labels.html').read_text(encoding='utf-8')
    rule = re.search(r'\.excel-label-cell\s*\{([^}]+)', html).group(1)
    assert 'line-height:1.15' in rule.replace(' ', '')


def test_print_font_unavailable_uses_safe_metrics_without_losing_text(monkeypatch):
    from PIL import ImageFont
    from services.excel_print_layout import _print_font, fit_print_rows
    _print_font.cache_clear()
    def unavailable(*args, **kwargs):
        raise OSError('Font is not installed on this machine')
    monkeypatch.setattr(ImageFont, 'truetype', unavailable)
    try:
        assert _print_font('宋体', False) is None
        sheet = Workbook().active
        sheet['A1'] = '完整设备\nZB-BVR-450/750V'
        sheet['A1'].font = Font(name='宋体', size=10)
        fit_print_rows(sheet)
        assert sheet['A1'].value == '完整设备\nZB-BVR-450/750V'
        assert sheet.row_dimensions[1].height > 20
    finally:
        _print_font.cache_clear()


@pytest.mark.parametrize('anchor_kind', ['one_cell', 'two_cell'])
def test_fill_sheet_keeps_footer_images_with_their_moved_rows(anchor_kind):
    import base64
    from openpyxl.drawing.image import Image
    from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, TwoCellAnchor
    from print_fill import _Filler
    from services.report_print_preview import _fill_sheet
    from services.document_excel_preview import build_document_excel_preview
    book = Workbook()
    sheet = book.active
    sheet['A1'], sheet['A2'], sheet['A3'] = '标题', '{item.name}', '合计：{total_quantity}'
    sheet.print_area = 'A1:C4'
    raw = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    image = Image(io.BytesIO(raw))
    if anchor_kind == 'two_cell':
        image.anchor = TwoCellAnchor(_from=AnchorMarker(col=1, row=2), to=AnchorMarker(col=2, row=3))
        sheet.add_image(image)
    else:
        sheet.add_image(image, 'B3')
    source = io.BytesIO()
    book.save(source)
    book = load_workbook(source)
    sheet = book.active
    _fill_sheet(sheet, _Filler(SimpleNamespace(),
        [SimpleNamespace(name=f'ITEM-{index}', quantity=1) for index in range(4)], '2026-11-07'))
    assert sheet._images[0].anchor._from.row == 5
    if anchor_kind == 'two_cell':
        assert sheet._images[0].anchor.to.row == 6
    assert sheet['A6'].value == '合计：4.0'
    result = io.BytesIO()
    book.save(result)
    page = build_document_excel_preview(result)[0]
    footer = next(cell for cell in page['cells'] if cell['text'] == '合计：4.0')
    assert page['images'][0]['top'] >= footer['top'] - .01
