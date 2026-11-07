"""Filled Excel print files must retain data, layout and pagination in the browser."""
import importlib.util
import io
from pathlib import Path
import pytest
from openpyxl import Workbook
from openpyxl.styles import Font,Alignment
from openpyxl.worksheet.pagebreak import Break


def render(book):
    spec=importlib.util.find_spec('services.document_excel_preview')
    assert spec is not None,'A filled-workbook preview is required before offering direct Excel-template printing'
    from services.document_excel_preview import build_document_excel_preview
    stream=io.BytesIO();book.save(stream);stream.seek(0)
    return build_document_excel_preview(stream)


@pytest.mark.parametrize('landscape',[False,True])
def test_build_document_excel_preview(landscape):
    book=Workbook();s=book.active;s.title='申请单';s.merge_cells('A1:C1');s['A1']='公司 <原样> & 合同'
    s['A1'].font=Font(name='宋体',size=20,bold=True);s['A1'].alignment=Alignment(horizontal='center')
    s.column_dimensions['A'].width=20;s.row_dimensions[1].height=35;s['A2']='物料';s['B2']='001-A';s['C2']=100
    s.page_setup.paperSize=s.PAPERSIZE_A4;s.page_setup.orientation='landscape' if landscape else 'portrait'
    pages=render(book);assert len(pages)==1
    page=pages[0];assert page['orientation']==s.page_setup.orientation and page['paper']=='A4'
    cell=next(c for c in page['cells'] if c['text'].startswith('公司'))
    assert cell['text']=='公司 <原样> & 合同' and 'font-size:20pt' in cell['css'] and 'font-weight:bold' in cell['css']
    assert cell['width']>250 and cell['height']>40
    assert next(c for c in page['cells'] if c['text']=='001-A')


def test_build_document_excel_preview_keeps_every_row_across_pages_and_repeats_titles():
    book=Workbook();s=book.active;s.append(['物料','数量']);s.print_title_rows='1:1'
    for i in range(130):s.append([f'M-{i:03}',i+.5])
    s.print_area='A1:B131'
    pages=render(book);assert len(pages)>=3
    values=[c['text'] for p in pages for c in p['cells']]
    assert [v for v in values if v.startswith('M-')]==[f'M-{i:03}' for i in range(130)]
    assert values.count('物料')==len(pages)
    for p in pages:
        assert all(c['top']>=0 and c['top']+c['height']<=p['content_height']+.1 for c in p['cells'])


def test_build_document_excel_preview_respects_hidden_rows_columns_and_print_area():
    book=Workbook();s=book.active
    s['A1']='excluded';s['B2']='keep';s['C2']='hidden-column';s['B3']='hidden-row';s['B4']='keep-2'
    s.column_dimensions['C'].hidden=True;s.row_dimensions[3].hidden=True;s.print_area='B2:C4'
    values=[c['text'] for p in render(book) for c in p['cells']]
    assert 'keep' in values and 'keep-2' in values
    assert not {'excluded','hidden-column','hidden-row'}&set(values)


def test_build_document_excel_preview_keeps_sheet_pages_logo_and_footer():
    import base64
    from openpyxl.drawing.image import Image
    book=Workbook();s=book.active;s['A1']='页一';s['A2']='细节';s.print_area='A1:C8'
    logo=Image(io.BytesIO(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')))
    s.add_image(logo,'A1');s.oddFooter.center.text='第 &P / &N 页'
    other=book.create_sheet('页二');other['A1']='页二';other.print_area='A1:B3'
    pages=render(book);assert len(pages)==2
    assert pages[0]['images'][0]['src'].startswith('data:image/png;base64,')
    assert pages[0]['footer']['center']=='第 1 / 2 页'
    assert any(c['text']=='页二' for c in pages[1]['cells'])


def test_build_document_excel_preview_honors_explicit_page_break():
    book=Workbook();s=book.active
    for i in range(10):s.append([f'R-{i}'])
    s.row_breaks.append(Break(id=5));s.print_area='A1:A10'
    pages=render(book);assert len(pages)==2
    assert [c['text'] for c in pages[0]['cells']]==[f'R-{i}' for i in range(5)]


def test_build_document_excel_preview_respects_fit_to_one_page():
    book=Workbook();s=book.active
    for i in range(30):
        s.append([f'R-{i}']);s.row_dimensions[i+1].height=50
    s.sheet_properties.pageSetUpPr.fitToPage=True
    s.page_setup.fitToWidth=1;s.page_setup.fitToHeight=1
    pages=render(book)
    assert len(pages)==1
    assert [c['text'] for c in pages[0]['cells']]==[f'R-{i}' for i in range(30)]


def test_build_document_excel_preview_preserves_date_format():
    from datetime import datetime
    book=Workbook();s=book.active;s['A1']=datetime(2026,11,7);s['A1'].number_format='yyyy年m月d日'
    assert render(book)[0]['cells'][0]['text']=='2026年11月7日'


@pytest.mark.parametrize('fault',['formula','chart','multiple_areas','unknown_paper','oversized_merge'])
def test_build_document_excel_preview_blocks_inaccurate_or_unsupported_output(fault):
    book=Workbook();s=book.active;s['A1']='数据';s['B1']=1
    if fault=='formula':s['A2']='=SUM(B1:B1)'
    elif fault=='chart':
        from openpyxl.chart import BarChart
        s.add_chart(BarChart(),'C1')
    elif fault=='multiple_areas':s.print_area=['A1:B2','D1:E2']
    elif fault=='unknown_paper':s.page_setup.paperSize='99'
    else:
        s.merge_cells('A1:A150')
        for row in range(1,151):s.row_dimensions[row].height=30
    with pytest.raises(ValueError):render(book)
