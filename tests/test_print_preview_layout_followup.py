"""Print layout regression: wide built-ins fit landscape, custom layouts stay intact."""
from datetime import date
import re

from bs4 import BeautifulSoup
from flask import render_template
from openpyxl import Workbook
import pytest

import app as m
from services.report_print_preview import build_report_print_preview


@pytest.mark.parametrize('count,orientation', [(3, 'portrait'), (12, 'landscape')])
@pytest.mark.parametrize('size', [0, 120])
def test_builtin_orientation_repeated_headers_and_complete_rows(count, orientation, size):
    columns = [{'field': 'f%d' % i, 'title': '字段%d' % i} for i in range(count)]
    rows = [{'f%d' % i: 'ROW-%03d-%d' % (n, i) for i in range(count)} for n in range(size)]
    sheets = build_report_print_preview('库存台账', columns, rows)
    sheet = sheets[0]
    assert sheet['orientation'] == orientation
    assert sheet['page_width'] == (297 if orientation == 'landscape' else 210)
    assert float(sheet['margins']['top'][:-2]) <= 12
    with m.app.test_request_context():
        html = render_template('report_print_preview.html', title='库存台账', sheets=sheets,
                               template_name='系统内置模板', total=size, error=None, print_scope='仓库：QA')
    soup = BeautifulSoup(html, 'html.parser')
    assert not soup.select('.sheet h2')
    assert len(soup.select('thead tr')) == 2
    assert len(soup.select('tbody tr')) == max(1, size) + 1
    if size:
        assert 'ROW-119-0' in soup.get_text()
    if count >= 4:
        assert '打印日期：' + date.today().isoformat() in soup.get_text()


def test_custom_paper_margins_and_rows_are_preserved(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.page_setup.paperSize = '11'
    ws.page_setup.orientation = 'portrait'
    ws.page_margins.top = .75
    ws.append(['自定义标题'] + [''] * 11)
    ws.append(['{item.code}'] + [''] * 11)
    path = tmp_path / 'custom.xlsx'
    wb.save(path)
    before = path.read_bytes()
    sheet = build_report_print_preview('自定义', [{'field': 'code', 'title': '编码'}],
                                       [{'code': 'A'}], template_path=path)[0]
    assert sheet['paper'] == 'A5' and sheet['orientation'] == 'portrait'
    assert sheet['margins']['top'] == '19.05mm'
    assert not any(row.get('is_header') for row in sheet['rows'])
    assert path.read_bytes() == before


def test_last_sheet_disables_forced_page_break_even_before_the_script():
    sheets = build_report_print_preview('打印', [{'field': 'code', 'title': '编码'}], [])
    with m.app.test_request_context():
        html = render_template('report_print_preview.html', title='打印', sheets=sheets * 2,
                               template_name='内置', total=0, error=None)
    soup = BeautifulSoup(html, 'html.parser')
    selector = re.search(r'([^{}]+)\{\s*break-after:\s*auto;', soup.style.string).group(1).strip()
    assert soup.select(selector) == [soup.select('.sheet')[-1]], 'No forced blank page after the final sheet'
