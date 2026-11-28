"""Exercise asset declarations and purchase page data without starting WMS."""
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

from tests.frontend_page_source import in_order_add_data

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app/templates'
ENV = Environment(autoescape=True, loader=FileSystemLoader(TEMPLATES))
ASSETS = {
    'uses_date_picker': ('cdn/flatpickr.min.css', 'cdn/flatpickr.min.js', 'js/pages/flatpickr-dates.js'),
    'uses_quick_select': ('js/quick-select.js',),
    'uses_list_cache': ('js/list-cache.js',),
    'uses_quantity_summary': ('js/quantity-summary.js',),
}


def render(template, **values):
    return template.render(
        current_user=SimpleNamespace(is_authenticated=True, role='warehouse', username='fixture', id=1),
        request=SimpleNamespace(args={}, endpoint='in_order_add_page'),
        csrf_token=lambda: 'fixture-token', config={'STATIC_VERSION': 'assets-fixture'},
        other_order_navigation=lambda *args: {},
        url_for=lambda endpoint, **params: '/static/' + params['filename'] if endpoint == 'static' else '/' + endpoint,
        **values,
    )


def test_shell_loads_only_declared_page_assets():
    plain = render(ENV.get_template('base.html'))
    for flag, assets in ASSETS.items():
        child = ENV.from_string('{% extends "base.html" %}{% set ' + flag + ' = true %}')
        enabled = render(child)
        for other_flag, other_assets in ASSETS.items():
            for asset in other_assets:
                assert '/static/' + asset not in plain
                assert enabled.count('/static/' + asset) == (flag == other_flag)
    assert plain.index('cdn/jquery-3.6.4.min.js') < plain.index('function refreshCsrfToken')


def test_all_page_asset_consumers_declare_dependencies():
    markers = {
        'uses_date_picker': r'''\btype\s*=\s*["']date["']''',
        'uses_quick_select': r'\bdata-ks=',
        'uses_list_cache': r'WMS\.listCache|js/pages/(?:material-list|in-order-add)\.js',
        'uses_quantity_summary': r'\bdata-quantity-summary=',
    }
    for name in ENV.list_templates(extensions=['html']):
        source, _, _ = ENV.loader.get_source(ENV, name)
        if not re.search(r'''{%\s*extends\s+['"]base\.html['"]''', source):
            continue
        for flag, marker in markers.items():
            if re.search(marker, source):
                assert '{% set ' + flag + ' = true %}' in source, (name, flag)


def test_purchase_order_data_is_safe_and_script_order_is_preserved():
    contracts = [{'contract_no': 'HD261103', 'project_name': '</script><script>bad()</script>'}]
    for business, archive in [('采购入库', contracts), ('产品入库', None), ('其他入库', None), ('销售退货入库', None)]:
        html = render(
            ENV.get_template('in_order_add.html'), business_type=business,
            receipt_contracts=archive, materials=[], units=[], suppliers=[],
            supplier_required=business in ('采购入库', '销售退货入库'),
            is_product_in=(business == '产品入库'), is_other_in=(business == '其他入库'),
            is_sales_return=(business == '销售退货入库'), prefill={}, warehouses=[],
            source_purchase_order_id=None, edit_items=[{'expiry_date': '2027-01-31'}],
        )
        data = in_order_add_data(html)
        assert data['receiptContracts'] == archive
        assert data['editItems'] == [{'expiry_date': '2027-01-31'}]
        assert '<script>bad()' not in html
        assert 'function populateMaterialRow' not in html
        order = ('js/api.js', 'cdn/flatpickr.min.js', 'id="in-order-add-data"',
                 'js/pages/in-order-add.js?v=assets-fixture', 'js/pages/flatpickr-dates.js')
        assert [html.index(value) for value in order] == sorted(html.index(value) for value in order)
        assert ('js/quantity-column-paste.js' in html) == (business == '采购入库')


def test_date_picker_initializes_existing_and_explicit_dynamic_inputs_once():
    program = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const existing = {}, dynamic = {matches: selector => selector === 'input[type="date"]', querySelectorAll: () => []};
const seen = [];
const context = {document: {querySelectorAll: () => [existing]}, flatpickr(input, options) {
    assert.equal(options.dateFormat, 'Y-m-d');
    assert.equal(options.altFormat, 'Y年m月d日');
    assert.equal(options.locale.firstDayOfWeek, 1);
    input._flatpickr = true;
    seen.push(input);
}};
context.window = context;
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), context);
context.initFlatpickrDates(dynamic);
context.initFlatpickrDates({querySelectorAll: () => [existing, dynamic]});
assert.deepEqual(seen, [existing, dynamic]);
'''
    subprocess.run(['node', '-e', program, str(ROOT / 'app/static/js/pages/flatpickr-dates.js')], check=True)


if __name__ == '__main__':
    test_shell_loads_only_declared_page_assets()
    test_all_page_asset_consumers_declare_dependencies()
    test_purchase_order_data_is_safe_and_script_order_is_preserved()
    test_date_picker_initializes_existing_and_explicit_dynamic_inputs_once()
    print('4 offline frontend asset checks passed')
