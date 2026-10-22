"""Confirmation drafts must resolve a warehouse without changing inventory."""
import pytest
from flask_login import login_user

import app as wms


@pytest.mark.parametrize('scenario,expected', [
    ('default', '照片默认仓'), ('explicit', '照片副仓'),
    ('no-default', None), ('inactive-default', None),
])
def test_confirmed_other_inbound_warehouse(scenario, expected, monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    with wms.app.test_request_context('/'):
        assert wms.db.engine.url.database in (None, ':memory:')
        wms.db.drop_all()
        wms.db.create_all()
        user = wms.User(username='photo-fixture', password_hash='fixture-unusable', role='admin', must_change_password=False)
        unit = wms.Unit(code='PCS', name='个')
        a = wms.Warehouse(code='PHOTO-A', name='照片默认仓', status='inactive' if scenario == 'inactive-default' else 'active', is_default=scenario != 'no-default')
        b = wms.Warehouse(code='PHOTO-B', name='照片副仓', status='active', is_default=False)
        c = wms.Warehouse(code='PHOTO-C', name='照片第三仓', status='active', is_default=False)
        wms.db.session.add_all([user, unit, a, b, c])
        wms.db.session.flush()
        material = wms.Material(code='PHOTO-M1', name='测试料', unit_id=unit.id, stock=50, price=2)
        historical = wms.InOrder(order_no='PHOTO-HISTORY', warehouse='', status='pending', business_type='其他入库')
        wms.db.session.add_all([material, historical])
        wms.db.session.commit()
        login_user(user)
        source = '收货到 PHOTO-B' if scenario == 'explicit' else '照片人工确认入库'
        result, error = wms._ai_create_confirmed_document_draft(
            'in_order', [{'material_id': material.id, 'quantity': 2}],
            source_text=source, inbound_business_type='other_in',
        )
        if expected is None:
            assert result is None
            assert '仓库' in error
            assert wms.InOrder.query.count() == 1
            assert wms.InOrderItem.query.count() == 0
        else:
            assert error is None
            order = wms.InOrder.query.filter_by(order_no=result['order_no']).one()
            assert order.warehouse == expected
            assert order.status == 'pending'
            assert len(order.items) == 1
            assert order.items[0].material_id == material.id
            assert order.items[0].quantity == 2
            assert sum(item.quantity for item in order.items) == 2
        assert wms.db.session.get(wms.Material, material.id).stock == 50
        assert wms.StockTransaction.query.count() == 0
        assert wms.db.session.get(wms.InOrder, historical.id).warehouse == ''
