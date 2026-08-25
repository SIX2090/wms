# -*- coding: utf-8 -*-
"""PRINT-TEMPLATE-F04（A5）回归测试：统一打印模板设计中心。

需求（2026-08-25）：单据/报表/列表/标签打印模板统一在模板中心在线设计
（参考简道云打印模板），支持「在线新建」免上传直接在线编辑。

测试用例：
  T1. 中心页含标签分类、在线新建入口与入库/出库/标签设计器统一入口
  T2. create_blank 权限：未登录跳转、非 admin 拒绝
  T3. create_blank 参数校验：非法分类/非法编码/未注册编码 → 400
  T4. create_blank 单据模板：生成文件+建行+跳转在线编辑器
  T5. create_blank 标签模板：生成含条码占位符的可编辑模板
  T6. create_blank 报表模板（report_inventory）：动态列定义生成模板
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


def _client(role='admin', with_warehouse=True):
    m.app.config['TESTING'] = True
    m.app.config['WTF_CSRF_ENABLED'] = False
    with m.app.app_context():
        m.db.drop_all()
        m.db.create_all()
        from werkzeug.security import generate_password_hash
        m.db.session.add(m.User(
            username='admin', password_hash=generate_password_hash('admin'),
            role='admin', must_change_password=False))
        m.db.session.add(m.User(
            username='worker', password_hash=generate_password_hash('worker'),
            role='user', must_change_password=False))
        if with_warehouse:
            m.db.session.add(m.Warehouse(
                code='WH001', name='材料仓', status='active', is_default=True))
        m.db.session.commit()
    client = m.app.test_client()
    account = 'admin' if role == 'admin' else 'worker'
    client.post('/login', data={'username': account, 'password': account})
    return client


def test_center_page_shows_label_and_create_blank():
    client = _client()
    resp = client.get('/print_templates')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert '标签打印' in html
    assert '/print_templates/create_blank' in html
    assert '/in_order_print_template' in html
    assert '/out_order_print_template' in html
    assert '/label_template' in html
    assert 'report_inventory' in html  # 报表编码联动选项


def test_create_blank_requires_login_and_admin():
    m.app.config['TESTING'] = True
    with m.app.app_context():
        m.db.drop_all()
        m.db.create_all()
        from werkzeug.security import generate_password_hash
        m.db.session.add(m.User(
            username='worker', password_hash=generate_password_hash('worker'),
            role='user', must_change_password=False))
        m.db.session.commit()
    anon = m.app.test_client()
    resp = anon.post('/print_templates/create_blank', data={
        'name': 'x', 'target_type': 'document', 'target_code': 'check'})
    assert resp.status_code in (301, 302, 401)
    worker = m.app.test_client()
    worker.post('/login', data={'username': 'worker', 'password': 'worker'})
    resp2 = worker.post('/print_templates/create_blank', data={
        'name': 'x', 'target_type': 'document', 'target_code': 'check'})
    assert resp2.status_code in (302, 401, 403)


def test_create_blank_validation():
    client = _client()
    # 非法分类
    assert client.post('/print_templates/create_blank', data={
        'name': 'x', 'target_type': 'nope', 'target_code': 'check',
    }).status_code == 400
    # 非法编码字符
    assert client.post('/print_templates/create_blank', data={
        'name': 'x', 'target_type': 'document', 'target_code': 'BAD CODE!',
    }).status_code == 400
    # 未注册编码
    assert client.post('/print_templates/create_blank', data={
        'name': 'x', 'target_type': 'document', 'target_code': 'not_registered',
    }).status_code == 400
    # 名称为空
    assert client.post('/print_templates/create_blank', data={
        'name': '  ', 'target_type': 'document', 'target_code': 'check',
    }).status_code == 400


def test_create_blank_document_template():
    client = _client()
    resp = client.post('/print_templates/create_blank', data={
        'name': '我的盘点模板', 'target_type': 'document',
        'target_code': 'check'})
    assert resp.status_code == 302
    with m.app.app_context():
        tpl = m.ExcelPrintTemplate.query.filter_by(
            target_type='document', target_code='check',
            name='我的盘点模板').first()
        assert tpl is not None
        assert tpl.is_default is False
        from print_fill import template_file_abspath
        path = template_file_abspath(tpl.excel_template_path,
                                     m.app.static_folder)
        assert os.path.exists(path)
        assert resp.headers['Location'].endswith(
            f'/global_print_template/{tpl.id}/edit')


def test_create_blank_label_template():
    client = _client()
    resp = client.post('/print_templates/create_blank', data={
        'name': '我的标签模板', 'target_type': 'label',
        'target_code': 'material_label'})
    assert resp.status_code == 302
    with m.app.app_context():
        tpl = m.ExcelPrintTemplate.query.filter_by(
            target_type='label', target_code='material_label',
            name='我的标签模板').first()
        assert tpl is not None
        from print_fill import template_file_abspath, validate_template_file
        path = template_file_abspath(tpl.excel_template_path,
                                     m.app.static_folder)
        with open(path, 'rb') as f:
            assert validate_template_file(f.read()) == ''


def test_create_blank_report_template():
    client = _client()
    resp = client.post('/print_templates/create_blank', data={
        'name': '我的库存报表模板', 'target_type': 'report',
        'target_code': 'report_inventory'})
    assert resp.status_code == 302
    with m.app.app_context():
        tpl = m.ExcelPrintTemplate.query.filter_by(
            target_type='report', target_code='report_inventory',
            name='我的库存报表模板').first()
        assert tpl is not None
        from print_fill import template_file_abspath
        path = template_file_abspath(tpl.excel_template_path,
                                     m.app.static_folder)
        assert os.path.exists(path)
