# -*- coding: utf-8 -*-
"""打印模板预览示例数据（PRINT-TEMPLATE-F05-A5）测试。

覆盖 build_preview_context（document/label/list/report/in_order/out_order/
未知类型回退）与 GET /{prefix}_print_template/<id>/preview_data 路由
（200 结构、未登录重定向、模板不存在 404）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)


def test_build_preview_context():
    from print_preview import build_preview_context
    ctx = build_preview_context('document', 'purchase_order')
    assert ctx['order']['order_no']
    assert ctx['order']['supplier']['name'] == '示例供应商有限公司'
    assert ctx['order']['supplier']['contact'] == '王经理'
    assert ctx['order']['operator']['username'] == '张三'
    assert len(ctx['items']) == 3
    item = ctx['items'][0]
    assert item['material']['code'] == 'M0001'
    assert item['material']['unit']['name'] == '个'
    assert item['quantity'] == 10
    assert item['price'] == 12.5
    assert ctx['total_quantity'] == 30
    assert ctx['total_amount'] == 375.0
    assert ctx['print_date']


def test_build_preview_context_label():
    from print_preview import build_preview_context
    ctx = build_preview_context('label', 'material_label')
    assert len(ctx['items']) == 3
    item = ctx['items'][0]
    assert item['code'] == 'M0001'
    assert item['barcode'].startswith('6901234')
    assert item['unit_name'] == '个'


def test_build_preview_context_list_and_report():
    from print_preview import build_preview_context
    ctx = build_preview_context('list', 'stock_query')
    assert ctx['items'][0]['warehouse'] == '主仓库'
    assert ctx['items'][0]['code'] == 'M0001'
    ctx2 = build_preview_context('report', 'report_inout')
    assert ctx2['items'][0]['order_no']
    assert ctx2['items'][0]['material_code'] == 'M0001'


def test_build_preview_context_inout_and_unknown():
    from print_preview import build_preview_context
    ctx = build_preview_context('in_order', '')
    assert ctx['order']['order_no'] == 'RK20260825001'
    assert ctx['items'][0]['material']['unit']['name'] == '个'
    assert ctx['items'][0]['barcode'].startswith('6901234')
    assert ctx['total_quantity'] == 30
    ctx2 = build_preview_context('out_order', '')
    assert ctx2['order']['customer'] == '示例客户公司'
    # 未知类型回退通用空上下文，不抛异常
    ctx3 = build_preview_context('unknown_type', 'unknown_code')
    assert ctx3['order'] == {} and ctx3['items'] == []
    assert ctx3['print_date']


# ---------- 路由级 ----------

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import ExcelPrintTemplate, Unit, User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture()
def client():
    app_module.app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add_all([
            Unit(name="个", code="PCS"),
            User(username="admin",
                 password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False),
            ExcelPrintTemplate(name='采购订单内置模板', target_type='document',
                               target_code='purchase_order',
                               excel_template_path='', is_default=True),
        ])
        db.session.commit()
    c = app_module.app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin"},
           content_type="application/x-www-form-urlencoded")
    return c


def test_route_preview_data_global(client):
    with app_module.app.app_context():
        tid = ExcelPrintTemplate.query.first().id
    resp = client.get(f'/global_print_template/{tid}/preview_data')
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload['status'] == 'success'
    assert payload['target_type'] == 'document'
    assert payload['target_code'] == 'purchase_order'
    ctx = payload['context']
    assert ctx['order']['order_no']
    assert len(ctx['items']) == 3


def test_route_preview_data_not_found(client):
    resp = client.get('/global_print_template/99999/preview_data')
    assert resp.status_code == 404


def test_route_preview_data_requires_login(client):
    anon = app_module.app.test_client()
    resp = anon.get('/global_print_template/1/preview_data')
    assert resp.status_code in (302, 401)
