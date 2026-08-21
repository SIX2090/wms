# -*- coding: utf-8 -*-
"""采购/领料打印模板上传保存回归测试。

回归 BUG-2026-08-21-001：create_print_template 调用 save_print_template_file
时缺少 static_folder 参数，上传 Excel 模板即抛 TypeError，模板无法落库。
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import InOrderPrintTemplate, User, db  # noqa: E402


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    app_module.app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin"},
           content_type="application/x-www-form-urlencoded")
    yield c


def _xlsx_bytes():
    from openpyxl import Workbook
    wb = Workbook()
    wb.active["A1"] = "采购入库单"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_upload_excel_template_saves_to_db_and_disk(client):
    """上传 Excel 模板应成功落库且文件写盘（BUG-2026-08-21-001 回归）。"""
    resp = client.post('/in_order_print_template/add', data={
        'name': '回归测试模板',
        'template_type': 'excel',
        'is_default': 'on',
        'excel_file': (_xlsx_bytes(), '回归模板.xlsx'),
    }, content_type='multipart/form-data')

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert '"status":"success"' in resp.get_data(as_text=True)

    with app_module.app.app_context():
        t = InOrderPrintTemplate.query.filter_by(name='回归测试模板').first()
        assert t is not None
        assert t.template_type == 'excel'
        assert t.is_default is True
        assert t.excel_template_path
        rel = t.excel_template_path.replace('/static/', '', 1)
        abs_path = os.path.join(app_module.app.static_folder, rel)
        assert os.path.exists(abs_path), abs_path


def test_upload_excel_without_file_rejected(client):
    """Excel 模板缺文件时应返回明确错误，而非 500。"""
    resp = client.post('/in_order_print_template/add', data={
        'name': '缺文件模板',
        'template_type': 'excel',
    }, content_type='multipart/form-data')

    assert resp.status_code == 400
    assert 'Excel template file is required' in resp.get_data(as_text=True)


def test_create_html_only_template_rejected(client):
    """仅提交 HTML 内容（无 Excel 文件）应被拒绝，打印模板仅允许 Excel。"""
    resp = client.post('/in_order_print_template/add', data={
        'name': 'HTML模板',
        'template_type': 'html',
        'html_content': '<h1>入库单</h1>',
    }, content_type='multipart/form-data')

    assert resp.status_code == 400
    assert 'Excel template file is required' in resp.get_data(as_text=True)

    with app_module.app.app_context():
        assert InOrderPrintTemplate.query.filter_by(name='HTML模板').first() is None


def test_create_template_ignores_html_type_saved_as_excel(client):
    """即使传入 template_type=html，只要提供 Excel 文件也应落库为 Excel 模板。"""
    resp = client.post('/in_order_print_template/add', data={
        'name': '传入HTML类型',
        'template_type': 'html',
        'html_content': '<h1>应被忽略</h1>',
        'excel_file': (_xlsx_bytes(), '传入HTML类型.xlsx'),
    }, content_type='multipart/form-data')

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert '"status":"success"' in resp.get_data(as_text=True)

    with app_module.app.app_context():
        t = InOrderPrintTemplate.query.filter_by(name='传入HTML类型').first()
        assert t is not None
        assert t.template_type == 'excel'
        assert t.excel_template_path
        assert not t.html_template_content