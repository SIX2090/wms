# -*- coding: utf-8 -*-
"""采购入库单打印页版式回归（2026-08-22 用户反馈）。

print_in_with_excel.html 两处调整：
1. 表头「采购单号」改为「采购入库单号」（值本就是入库单号 IN…，避免与
   浏览器页眉"采购入库单 - IN…"语义错位）。
2. 「收货：」签名位从右下角（text-align:right）移到表格内 tfoot 无边框行，
   起点对齐「单价」列（colspan=6 空 + colspan=3 收货），列对齐由同一表格保证。

覆盖：
- 页面 200 且含「采购入库单号：IN…」、不含旧「采购单号：」
- tfoot 签名行存在且「收货：」位于单价列起点（colspan 6+3 结构）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as m  # noqa: E402


def _make_order_with_default_template():
    """造一张采购入库单 + excel 类型默认打印模板，返回 (client, order_id)。"""
    m.app.config['TESTING'] = True
    with m.app.app_context():
        m.db.drop_all()
        m.db.create_all()
        supplier = m.Supplier(code='S001', name='辉达')
        unit = m.Unit(code='BA', name='把')
        cat = m.MaterialCategory(code='DEFAULT', name='默认分类')
        m.db.session.add_all([supplier, unit, cat])
        m.db.session.flush()
        material = m.Material(code='208005', name='0.5-10mm端子压线钳', brand='None',
                              spec='', unit_id=unit.id, category_id=cat.id, price=0)
        from werkzeug.security import generate_password_hash
        user = m.User(username='admin', password_hash=generate_password_hash('admin'),
                      role='admin', must_change_password=False)
        m.db.session.add(material)
        m.db.session.add(user)
        m.db.session.flush()
        from datetime import date
        order = m.InOrder(order_no='IN26080175', business_type='采购入库',
                          supplier_id=supplier.id, warehouse='主仓库',
                          date=date(2026, 8, 22), status='completed',
                          operator_id=user.id)
        m.db.session.add(order)
        m.db.session.flush()
        item = m.InOrderItem(in_order_id=order.id, material_id=material.id,
                             quantity=3, price=0, amount=0)
        tpl = m.InOrderPrintTemplate(name='系统默认入库单模板', template_type='excel',
                                     is_default=True,
                                     html_template_content=m.DEFAULT_IN_ORDER_HTML_TEMPLATE)
        m.db.session.add_all([item, tpl])
        m.db.session.commit()
        order_id = order.id
    m.app.config['WTF_CSRF_ENABLED'] = False
    client = m.app.test_client()
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    return client, order_id


def test_print_page_uses_inbound_order_no_label():
    """表头显示「采购入库单号：」且不再出现旧标签「采购单号：」。"""
    client, order_id = _make_order_with_default_template()
    resp = client.get(f'/in_order/{order_id}/print')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert '采购入库单号：IN26080175' in html
    assert '采购单号：' not in html


def test_signature_row_starts_at_price_column():
    """「收货：」签名行在表格 tfoot 内，起点对齐单价列（前 6 列空、后 3 列放签名）。"""
    client, order_id = _make_order_with_default_template()
    resp = client.get(f'/in_order/{order_id}/print')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert '<td colspan="6" class="sig-cell"></td>' in html
    assert '<td colspan="3" class="sig-cell">收货：</td>' in html
    # 旧的右下角签名容器已移除
    assert 'signature-row' not in html
