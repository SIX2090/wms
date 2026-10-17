# -*- coding: utf-8 -*-
"""BUG-2026-10-17-012：批量入口三处门禁回归。

F01 批量完成/反审回写来源采购订单状态；
F02 批量反审存在有效下推时拒绝（否则单据永久卡死）；
F03 批量完成出库拒绝停用仓，且 0 成功必须返回 error 契约。
"""
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    DocumentPushLine, InOrder, InOrderItem, Material, MaterialCategory,
    OutOrder, OutOrderItem, PurchaseOrder, PurchaseOrderItem, Supplier, Unit,
    User, Warehouse, db,
)

app_module.app.config['TESTING'] = True
app_module.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture(autouse=True)
def _app_context():
    ctx = app_module.app.app_context()
    ctx.push()
    try:
        yield
    finally:
        db.session.remove()
        ctx.pop()


def _reset():
    db.drop_all()
    db.create_all()
    from werkzeug.security import generate_password_hash
    db.session.add_all([
        Unit(code='PCS', name='个'),
        MaterialCategory(code='CAT', name='默认'),
        Supplier(code='S1', name='供应商'),
        Warehouse(code='WH1', name='主仓', is_default=True, status='active'),
        Warehouse(code='WH2', name='停用仓', is_default=False, status='inactive'),
        User(username='admin', password_hash=generate_password_hash('admin'),
             role='admin', must_change_password=False),
    ])
    db.session.flush()
    db.session.add(Material(code='M1', name='轴承', spec='6204', category_id=1,
                            unit_id=1, supplier_id=1, stock=100, price=10))
    db.session.commit()


def _login(client):
    page = client.get('/login').get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    client.post('/login', data={'username': 'admin', 'password': 'admin',
                                'csrf_token': m.group(1) if m else ''})


def _make_in_order(receive=10, po_qty=10):
    po = PurchaseOrder(order_no='PO-1', supplier_id=1, status='pending')
    db.session.add(po)
    db.session.flush()
    po_item = PurchaseOrderItem(purchase_order_id=po.id, material_id=1,
                                quantity=po_qty, price=10, received_quantity=0)
    db.session.add(po_item)
    db.session.flush()
    order = InOrder(order_no='IN-1', date=date.today(), business_type='采购入库',
                    warehouse='主仓', status='pending', operator_id=1)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(in_order_id=order.id, material_id=1, quantity=receive,
                               price=10, amount=receive * 10,
                               source_purchase_order_item_id=po_item.id))
    db.session.commit()
    return po, order


def test_batch_complete_writeback_purchase_order_status():
    _reset()
    client = app_module.app.test_client()
    _login(client)
    po, order = _make_in_order()
    resp = client.post('/in_order/batch_complete', json={'ids': [order.id]})
    data = resp.get_json()
    assert data['status'] == 'success' and data['completed'] == 1, data
    assert PurchaseOrder.query.get(po.id).status == 'completed'


def test_batch_revert_skips_when_active_push_exists():
    _reset()
    client = app_module.app.test_client()
    _login(client)
    _, order = _make_in_order()
    order.status = 'completed'
    db.session.add(DocumentPushLine(
        source_document_type='purchase_in_order', source_document_id=order.id,
        source_document_no=order.order_no, source_item_id=1,
        target_document_type='requisition', target_document_id=99,
        target_document_no='OU-99', pushed_quantity=10, status='active',
        request_id='auto-requisition-%s' % order.id, created_by=1))
    db.session.commit()
    resp = client.post('/in_order/batch_revert', json={'ids': [order.id]})
    data = resp.get_json()
    assert data['reverted'] == 0, data
    assert '下游' in data['msg'], data
    assert InOrder.query.get(order.id).status == 'completed'


def test_out_batch_zero_success_returns_error_contract():
    _reset()
    client = app_module.app.test_client()
    _login(client)
    resp = client.post('/out_order/batch_complete', json={'ids': [987654]})
    data = resp.get_json()
    assert resp.status_code == 400, data
    assert data['status'] == 'error' and data['completed'] == 0, data


def test_out_batch_skips_inactive_warehouse():
    _reset()
    client = app_module.app.test_client()
    _login(client)
    order = OutOrder(order_no='OU-1', date=date.today(), business_type='领料单',
                     warehouse='停用仓', status='pending', operator_id=1)
    db.session.add(order)
    db.session.flush()
    db.session.add(OutOrderItem(out_order_id=order.id, material_id=1,
                                quantity=1, price=10, amount=10))
    db.session.commit()
    resp = client.post('/out_order/batch_complete', json={'ids': [order.id]})
    data = resp.get_json()
    assert resp.status_code == 400, data
    assert data['completed'] == 0, data
    assert '仓库' in data['msg'], data
    assert OutOrder.query.get(order.id).status == 'pending'
