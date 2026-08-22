# -*- coding: utf-8 -*-
"""打印模板管理页回归（2026-08-22 用户反馈）。

1. 字段代码说明补全：页面字段表须覆盖 print_fill 引擎支持的全量占位符
   （单据级 order.*、明细级 item.*、合计 total_*/print_date），
   修复前仅 8~10 项，用户无法知晓品牌/规格/单位/合同编号等字段。
2. 入库单模板管理页移除右上角「页面导航」浮窗（遮挡内容，用户要求去掉）。

覆盖：
- /in_order_print_template 200 且字段表含全量关键占位符、无页面导航浮窗
- /out_order_print_template 200 且字段表含全量关键占位符
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

IN_ORDER_TOKENS = (
    '{order.order_no}', '{order.date}', '{order.supplier.name}',
    '{order.supplier.contact}', '{order.supplier.phone}', '{order.supplier.address}',
    '{order.warehouse}', '{order.purpose}', '{order.remark}',
    '{order.operator.username}',
    '{item.material.code}', '{item.material.name}', '{item.material.brand}',
    '{item.material.spec}', '{item.material.unit.name}',
    '{item.quantity}', '{item.price}', '{item.amount}',
    '{item.contract_no}', '{item.project_name}', '{item.remark}',
    '{total_quantity}', '{total_amount}', '{print_date}',
)

OUT_ORDER_TOKENS = (
    '{order.order_no}', '{order.date}', '{order.customer}', '{order.picker}',
    '{order.purpose}', '{order.warehouse}', '{order.remark}',
    '{order.operator.username}',
    '{item.material.code}', '{item.material.name}', '{item.material.brand}',
    '{item.material.spec}', '{item.material.unit.name}',
    '{item.quantity}', '{item.price}', '{item.amount}',
    '{item.contract_no}', '{item.project_name}', '{item.remark}',
    '{total_quantity}', '{total_amount}', '{print_date}',
)


def _client():
    m.app.config['TESTING'] = True
    with m.app.app_context():
        m.db.drop_all()
        m.db.create_all()
        from werkzeug.security import generate_password_hash
        m.db.session.add(m.User(username='admin', password_hash=generate_password_hash('admin'),
                                role='admin', must_change_password=False))
        m.db.session.commit()
    m.app.config['WTF_CSRF_ENABLED'] = False
    client = m.app.test_client()
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    return client


def test_in_order_template_page_full_field_list():
    client = _client()
    resp = client.get('/in_order_print_template')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    for token in IN_ORDER_TOKENS:
        assert token in html, f'入库单模板页字段表缺 {token}'


def test_in_order_template_page_no_navigation_hint():
    """页面导航浮窗已移除（JS 创建函数、CSS 类、调用均不存在）。"""
    client = _client()
    resp = client.get('/in_order_print_template')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert '页面导航' not in html
    assert 'navigation-hint' not in html
    assert 'addNavigationMenu' not in html


def test_out_order_template_page_full_field_list():
    client = _client()
    resp = client.get('/out_order_print_template')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    for token in OUT_ORDER_TOKENS:
        assert token in html, f'领料单模板页字段表缺 {token}'
