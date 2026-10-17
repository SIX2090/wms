# -*- coding: utf-8 -*-
"""BUG-2026-10-17-013-F02：旧 /api/subcontract/quick_issue 必须防重放。

审计 §5.4：旧端点无写锁/无幂等，网络重试会重复创建发料单并重复扣库存。
修复后：加写锁 + 10 秒内相同明细视为重放，返回已创建单据。
"""
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Material, MaterialCategory, StockTransaction, SubcontractIssue,
    SubcontractOrder, Supplier, Unit, User, Warehouse, db,
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
    db.session.add(Material(code='M-SC', name='委外料', spec='S', category_id=1,
                            unit_id=1, supplier_id=1, stock=10, price=1))
    db.session.flush()
    db.session.add(StockTransaction(material_id=1, transaction_type='in', quantity=10,
                                    warehouse_id=1, location='主仓',
                                    reference_type='in_order', reference_id=0,
                                    created_at=datetime.now()))
    order = SubcontractOrder(order_no='SC-1', supplier_id=1, warehouse='主仓', status='pending')
    db.session.add(order)
    db.session.commit()
    yield
    db.session.remove()
    ctx.pop()


def _login(client):
    page = client.get('/login').get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    client.post('/login', data={'username': 'admin', 'password': 'admin',
                                'csrf_token': m.group(1) if m else ''})


def _issue(client):
    order = SubcontractOrder.query.first()
    return client.post('/api/subcontract/quick_issue',
                       json={'order_id': order.id,
                             'items': [{'material_id': 1, 'quantity': 4}]})


def test_repeat_submit_is_replayed_and_stock_deducted_once():
    client = app_module.app.test_client()
    _login(client)
    first = _issue(client)
    assert first.status_code == 200 and first.get_json()['status'] == 'success'
    second = _issue(client)
    body = second.get_json()
    assert second.status_code == 200
    assert body.get('replayed') is True, body
    assert SubcontractIssue.query.count() == 1
    assert Material.query.get(1).stock == 6
