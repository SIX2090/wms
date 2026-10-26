"""Render the actual application shell: hide duplicate lists, preserve working entries."""
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from jinja2 import Environment
import pytest

ROOT = Path(__file__).resolve().parents[1]
ROLES = ['admin', 'warehouse', 'purchase', 'sales', 'production', 'finance', 'viewer', 'manager', 'user']
OLD_QUERY_PATHS = {'/purchase_request', '/purchase_order', '/in_order', '/out_order',
                   '/other_in_order', '/other_out_order', '/sales', '/sales/outbound'}


class MenuLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs).get('href', ''))

    def handle_data(self, data):
        self.text.append(data)


def shell(role, locations=False, prices=False):
    source = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    html = Environment(autoescape=True).from_string(source).render(
        current_user=SimpleNamespace(is_authenticated=True, role=role, username='menu-fixture', id=1),
        csrf_token=lambda: 'fixture-csrf', config={'STATIC_VERSION': 'menu-test'},
        request=SimpleNamespace(args={}), location_management_enabled=locations,
        price_dimension_enabled=prices, inventory_alert_enabled=True,
        url_for=lambda endpoint, **values: '/static/' + values['filename'] if endpoint == 'static' else '/' + endpoint,
    )
    return MenuLinks(html)


@pytest.mark.parametrize('role', ROLES)
def test_duplicate_business_query_lists_are_not_rendered_in_any_menu(role):
    menu = shell(role)
    leaked = [link for link in menu.links if urlsplit(link).path in OLD_QUERY_PATHS]
    assert not leaked, f'{role} still exposes duplicate list queries: {leaked}'
    text = ''.join(menu.text)
    for obsolete in ['采购申请列表', '采购订单列表', '销售订单列表', '销售出库列表', '报表列表', '列表 / 报表']:
        assert obsolete not in text


@pytest.mark.parametrize('role', ['admin', 'warehouse'])
@pytest.mark.parametrize('locations,prices', [(False, False), (True, True)])
def test_forms_existing_reports_and_master_data_still_have_entries(role, locations, prices):
    links = shell(role, locations, prices).links
    paths = {urlsplit(link).path for link in links}
    assert {'/purchase_order/add', '/in_order/add', '/out_order/add', '/other_in_order/add',
            '/other_out_order/add', '/sales/add', '/sales/outbound_selection', '/after_sale_out/add',
            '/transfer', '/check', '/requisition', '/subcontract', '/supplier', '/customer'}.issubset(paths)
    assert {'/report/view/in_detail', '/report/view/out_detail', '/report/view/inventory',
            '/report/view/summary', '/report/view/check', '/report/view/ledger',
            '/report/view/warehouse_monthly', '/report/view/requisition', '/report/view/subcontract',
            '/sales/outflow_report', '/sales/report', '/purchase_report'}.issubset(paths)
    assert ('/adjustment' in paths) is locations
    assert ('/sales/price_analysis' in paths) is prices
    if role == 'admin':
        assert {'/material', '/contract', '/opening_stock', '/category', '/unit', '/warehouse',
                '/department', '/employee'}.issubset(paths)
        assert '/purchase_request/add' in paths
    else:
        assert '/purchase_request/add' not in paths


def test_finance_and_viewer_keep_report_queries_without_form_or_admin_access():
    finance = {urlsplit(link).path for link in shell('finance').links}
    assert {'/report', '/report/view/in_detail', '/report/view/out_detail', '/sales/report', '/purchase_report'}.issubset(finance)
    assert not any(path.endswith('/add') for path in finance)
    for role in ['finance', 'viewer', 'purchase', 'sales', 'production', 'user']:
        paths = {urlsplit(link).path for link in shell(role).links}
        assert '/system_settings' not in paths and '/user' not in paths
    assert '/report' in {urlsplit(link).path for link in shell('viewer').links}
    production = {urlsplit(link).path for link in shell('production').links}
    assert {'/requisition', '/subcontract', '/bom'}.issubset(production)


def test_other_business_types_have_explicit_report_queries():
    links = shell('admin').links
    for path, business_type in [('/report/view/in_detail', '其他入库'), ('/report/view/out_detail', '其他出库')]:
        assert any(urlsplit(link).path == path and parse_qs(urlsplit(link).query).get('business_type') == [business_type]
                   for link in links)
