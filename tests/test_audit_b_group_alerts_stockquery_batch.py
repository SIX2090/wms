# -*- coding: utf-8 -*-
"""BUG-2026-10-17-015：B 组小项回归（预警 NULL / 无效仓库 / 批量上限）。"""
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import app as wms  # noqa: E402
from app import (  # noqa: E402
    InOrder, Material, MaterialCategory, Supplier, Unit, User, Warehouse, db,
    set_system_setting,
)

wms.app.config['TESTING'] = True
wms.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture(autouse=True)
def _ctx():
    with wms.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        db.session.add_all([
            Unit(code='PCS', name='个'),
            MaterialCategory(code='CAT', name='默认'),
            Supplier(code='S1', name='供应商'),
            Warehouse(code='WH1', name='主仓', is_default=True, status='active'),
            User(username='admin', password_hash=generate_password_hash('admin'),
                 role='admin', must_change_password=False),
        ])
        db.session.flush()
        db.session.add(Material(code='M1', name='轴承', category_id=1, unit_id=1, supplier_id=1, stock=10))
        db.session.commit()
    yield
    with wms.app.app_context():
        db.session.remove()


def _client():
    c = wms.app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = '1'
        s['_fresh'] = True
    return c


def test_alert_status_handles_none_stock():
    with wms.app.app_context():
        set_system_setting('inventory_alert_enabled', '1')
        db.session.commit()
        assert wms._alert_status_for(None, 10, 5) == 'low'
        assert wms._alert_status_for(None, 0, 0) == 'disabled'


def test_stock_query_rejects_unknown_warehouse():
    c = _client()
    resp = c.get('/stock_query?warehouse_id=999999')
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    body = resp.get_json() or {}
    assert '仓库不存在' in body.get('msg', '')


def test_batch_complete_select_all_cap():
    with wms.app.app_context():
        rows = [InOrder(order_no=f'IN-CAP-{i}', date=date.today(), business_type='其他入库',
                        warehouse='主仓', status='pending', operator_id=1) for i in range(501)]
        db.session.add_all(rows)
        db.session.commit()
    c = _client()
    resp = c.post('/in_order/batch_complete', json={'select_all': True, 'status': 'pending'})
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    assert '500' in (resp.get_json() or {}).get('msg', '')


def test_batch_revert_ids_cap():
    c = _client()
    resp = c.post('/in_order/batch_revert', json={'ids': list(range(1, 102))})
    assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
    assert '100' in (resp.get_json() or {}).get('msg', '')


def test_dead_precision_settings_removed():
    keys = {s['key'] for g in wms.SYSTEM_SETTING_GROUPS for s in g.get('settings', [])}
    dead = {'quantity_decimal_places', 'price_decimal_places', 'amount_decimal_places'}
    assert not (dead & keys), dead & keys
    assert not hasattr(wms, 'quantity_decimal_places')
    assert not hasattr(wms, 'price_decimal_places')
    assert not hasattr(wms, 'amount_decimal_places')
