"""Shared read-only toolbar on independent sales and stock report pages."""
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
import shutil
import subprocess

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['sales_report', 'sales_outflow_report', 'sales_trend_report', 'sales_execution_report',
         'sales_price_analysis', 'sales_reconciliation_report', 'stock_query']


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = {}
        self.body_class = ''
        self.current = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'body':
            self.body_class = attrs.get('class', '')
        if attrs.get('id'):
            assert attrs['id'] not in self.ids, 'duplicate control ID'
            self.ids[attrs['id']] = (tag, attrs)


@pytest.mark.parametrize('page', PAGES)
def test_independent_pages_keep_tables_and_have_one_explicit_report_toolbar(page):
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': "<body class='{% block body_class %}{% endblock %}'>{% block content %}{% endblock %}{% block extra_js %}{% endblock %}</body>"}),
        FileSystemLoader(ROOT / 'app/templates'),
    ]))
    env.globals.update(url_for=lambda endpoint, **kwargs: '/' + kwargs.get('filename', endpoint),
                       csrf_token=lambda: 'isolated-test', request=SimpleNamespace(args={}))
    context = dict(rows=[], orders=[], customers=[], employees=[], warehouses=[], suppliers=[],
        categories=[], materials=[], filters={}, by_customer=[], by_material=[], by_salesperson=[],
        drill_material_code='', drill_items=[], warehouse_id=2, all_warehouses_mode=False,
        chart_data=None, pagination=None, warehouse_stock_map={}, location_map={},
        total_orders=0, total_amount=0, total_untaxed=0, total_tax=0, shipped_amount=0,
        remaining_amount=0, pending_amount=0, total_quantity=0, total_shipped=0, total_rows=0,
        sort_by='code', sort_order='asc', default_warehouse=None, months_back=12)
    html = env.get_template(page + '.html').render(**context)
    dom = Elements()
    dom.feed(html)
    assert 'wms-no-global-actionbar' in dom.body_class
    assert 'reportToolbar' in dom.ids
    for name in ['refreshReportBtn', 'exportReportBtn', 'reportPrintMenu', 'templatePreviewBtn',
                 'retryPrintTemplatesBtn', 'columnSettingsBtn']:
        assert name in dom.ids, name
    assert dom.ids['reportToolbar'][1].get('role') == 'toolbar'
    assert '下载打印文件' in html and '模板管理' in html
    assert '<table' in html and '<form' in html
    assert 'report-workbench.js' in html
    if page == 'stock_query':
        assert 'stockPrintBtn' in dom.ids and 'stockTemplateSelect' in dom.ids
    else:
        assert 'templateSelect' in dom.ids
    if page == 'sales_report':
        assert 'reportPrintScope' in dom.ids
        for label in ['客户汇总', '物料汇总', '业务员汇总', '销售明细']:
            assert label in html


@pytest.mark.parametrize('scenario', ['default', 'builtin', 'failure_retry', 'all_missing', 'stale',
                                    'preview_download', 'filters_changed', 'scope', 'refresh', 'stock', 'stock_all', 'export_query'])
def test_independent_report_toolbar_runtime(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run([node, '--max-old-space-size=96',
        str(ROOT / 'tests/frontend_independent_report_toolbars.cjs'), str(ROOT), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
