"""BUG-2026-11-01-026: displayed warehouse selection matches query scope."""
from html.parser import HTMLParser

import pytest
import app as wms
from app import db
from tests.test_document_create_number_conflicts import case  # noqa: F401


class WarehouseSelect(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.active = False
        self.done = False
        self.options = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'select':
            self.active = not self.done and attrs.get('name') == 'warehouse_id'
        elif tag == 'option' and self.active:
            self.options.append(attrs)

    def handle_endtag(self, tag):
        if tag == 'select' and self.active:
            self.done = True
            self.active = False


@pytest.mark.parametrize('path,model_name,number_field', [
    ('/check', 'InventoryCheck', 'check_no'),
    ('/adjustment', 'AdjustmentOrder', 'adjustment_no'),
    ('/in_order', 'InOrder', 'order_no'),
    ('/out_order', 'OutOrder', 'order_no'),
])
@pytest.mark.parametrize('scope', ['missing', 'invalid', 'default', 'explicit'])
def test_unresolved_warehouse_is_not_silently_displayed_as_first_warehouse(case, path, model_name, number_field, scope):
    client, ids = case[0][0], case[1]
    with wms.app.app_context():
        for index, warehouse in enumerate(wms.Warehouse.query.order_by(wms.Warehouse.id)):
            warehouse.is_default = scope == 'default' and index == 0
            attrs = {number_field: 'SCOPE-DOCUMENT-'+str(index), 'status': 'pending',
                     'warehouse': warehouse.code if index == 1 else warehouse.name}
            if model_name == 'OutOrder':
                attrs['business_type'] = '领料单'
            if model_name == 'AdjustmentOrder':
                attrs['adjustment_type'] = 'surplus'
            db.session.add(getattr(wms, model_name)(**attrs))
        db.session.commit()
    url = path + ('?warehouse_id=999999' if scope == 'invalid' else
                  '?warehouse_id='+str(ids['b']) if scope == 'explicit' else '')
    response = client.get(url)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    selected = [o.get('value') for o in WarehouseSelect(html).options if 'selected' in o]
    if scope in ('missing', 'invalid'):
        assert selected == [''], 'an unapplied warehouse must not appear selected'
        assert '请选择仓库' in html
        assert 'SCOPE-DOCUMENT-' not in html
    else:
        index = int(scope == 'explicit')
        assert selected == [str(ids['b'] if index else ids['a'])]
        assert 'SCOPE-DOCUMENT-'+str(index) in html
        assert 'SCOPE-DOCUMENT-'+str(1-index) not in html
