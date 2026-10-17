# -*- coding: utf-8 -*-
"""BUG-2026-10-17-013-F01：多行同物料必须按合计校验库存。

审计 I2：反提交/售后/批量反审按"单次快照逐行比较"，两行 8+8 对单仓 10
会逐行通过，合计扣成负账。
"""
import re
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder, InOrderItem, Material, MaterialCategory, StockTransaction, Supplier,
    Unit, User, Warehouse, db,
)

app_module.app.config['TESTING'] = True
app_module.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture(autouse=True)
def _ctx():
    ctx = app_module.app.app_context()
    ctx.push()
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
    db.session.add(Material(code='M1', name='轴承', spec='6204', category_id=1,
                            unit_id=1, supplier_id=1, stock=10, price=10))
    db.session.flush()
    db.session.add(StockTransaction(material_id=1, transaction_type='in', quantity=10,
                                    warehouse_id=1, location='主仓',
                                    reference_type='in_order', reference_id=0,
                                    created_at=datetime.now()))
    db.session.commit()
    yield
    db.session.remove()
    ctx.pop()


def _login(client):
    page = client.get('/login').get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    client.post('/login', data={'username': 'admin', 'password': 'admin',
                                'csrf_token': m.group(1) if m else ''})


def _completed_order_with_two_lines():
    order = InOrder(order_no='IN-AGG', date=date.today(), business_type='其他入库',
                    warehouse='主仓', status='completed', operator_id=1)
    db.session.add(order)
    db.session.flush()
    for _ in range(2):
        db.session.add(InOrderItem(in_order_id=order.id, material_id=1, quantity=8,
                                   price=10, amount=80))
    db.session.commit()
    return order


def test_single_revert_rejects_when_total_exceeds_stock():
    client = app_module.app.test_client()
    _login(client)
    order = _completed_order_with_two_lines()
    resp = client.post('/in_order/%d/revert' % order.id)
    data = resp.get_json()
    assert data['status'] == 'error', data
    assert '库存不足' in data['msg'], data
    assert InOrder.query.get(order.id).status == 'completed'
    assert Material.query.get(1).stock == 10


def test_batch_revert_skips_when_total_exceeds_stock():
    client = app_module.app.test_client()
    _login(client)
    order = _completed_order_with_two_lines()
    resp = client.post('/in_order/batch_revert', json={'ids': [order.id]})
    data = resp.get_json()
    assert data['reverted'] == 0, data
    assert '库存不足' in data['msg'], data
    assert InOrder.query.get(order.id).status == 'completed'
    assert Material.query.get(1).stock == 10
