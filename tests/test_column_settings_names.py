"""BUG-2026-11-05-101: one name for the existing column-settings dialog."""
from html.parser import HTMLParser

import app as wms
import pytest


class ColumnSettingsLabels(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = []
        self.in_menu = False
        self.active = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'details' and attrs.get('id') == 'columnSettingsBtn':
            self.in_menu = True
        if ((tag == 'button' and attrs.get('id') == 'columnSettingsBtn') or
                (tag == 'summary' and self.in_menu)):
            self.active = []

    def handle_data(self, data):
        if self.active is not None:
            self.active.append(data)

    def handle_endtag(self, tag):
        if tag in ('button', 'summary') and self.active is not None:
            self.labels.append(''.join(''.join(self.active).split()))
            self.active = None
        if tag == 'details':
            self.in_menu = False


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        assert wms.db.engine.url.database in (None, '', ':memory:')
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        user = wms.User(username='column-settings-fixture', role='admin',
                        password_hash='fixture-only', must_change_password=False)
        warehouse = wms.Warehouse(code='COL-W', name='栏目测试仓',
                                  status='active', is_default=True)
        customer = wms.Customer(code='COL-C', name='栏目测试客户')
        wms.db.session.add_all([user, warehouse, customer])
        wms.db.session.flush()
        order = wms.SalesOrder(order_no='COL-S', customer_id=customer.id,
                               warehouse=warehouse.name, warehouse_id=warehouse.id,
                               status='draft', operator_id=user.id)
        wms.db.session.add(order)
        wms.db.session.commit()
        wms.set_system_setting('price_dimension_enabled', '1')
        wms.db.session.commit()
        user_id = user.id
    client = wms.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['_fresh'] = True
    yield client
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()


@pytest.mark.parametrize('path', [
    '/in_order', '/in_order/add', '/out_order', '/out_order/add',
    '/sales/add', '/sales/1/edit', '/report/view/in_detail', '/stock_query',
    '/sales/report', '/sales/outflow_report', '/sales/trend_report',
    '/sales/execution_report', '/sales/price_analysis', '/sales/reconciliation',
])
def test_column_settings_entry_has_one_consistent_name(client, path):
    response = client.get(path + '?embedded=1&warehouse_id=1')
    assert response.status_code == 200
    parser = ColumnSettingsLabels()
    parser.feed(response.get_data(as_text=True))
    assert parser.labels == ['栏目设置']
