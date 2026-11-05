# -*- coding: utf-8 -*-
"""
工单领料单单据表头新增"领料人(picker)"字段的回归测试。

验收点：
P1. 新增领料单（/requisition/add）保存 picker 字段。
P2. 领料单详情/编辑页渲染"领料人"输入框并回填 picker 值。
P3. 表格保存（/requisition/save_table）持久化 picker 字段。
"""
from __future__ import annotations

import os
import sys
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import Material, ProductionRequisition, Unit, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_basics():
    from app import Warehouse
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100)
    db.session.add(mat)
    db.session.commit()
    return wh, mat


class TestRequisitionPicker:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            wh, mat = _seed_basics()
        client = app_module.app.test_client()
        _login(client)
        return client, mat

    def test_P1_add_saves_picker(self):
        client, _ = self._setup()
        resp = client.post("/requisition/add", data={"purpose": "测试领料", "picker": "张三", "remark": ""})
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            req = db.session.get(ProductionRequisition, data["id"])
            assert req is not None
            assert req.picker == "张三"

    def test_P2_form_renders_picker(self):
        client, _ = self._setup()
        with app_module.app.app_context():
            req = ProductionRequisition(req_no="REQ-P2-001", picker="李四", status="pending")
            db.session.add(req)
            db.session.commit()
            req_id = req.id
        html = client.get(f"/requisition/{req_id}").get_data(as_text=True)
        assert 'name="picker"' in html, "编辑页必须渲染 name=picker 的领料人输入框"
        assert 'value="李四"' in html, "领料人输入框必须回填已保存的 picker 值"

    def test_P3_save_table_persists_picker(self):
        client, mat = self._setup()
        payload = {
            "order_no": "REQ-P3-001",
            "date": "2026-08-06",
            "header": {"purpose": "测试", "picker": "王五", "warehouse": "默认仓"},
            "items": [{"code": "M001", "quantity": 5}],
        }
        resp = client.post("/requisition/save_table", json=payload)
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            req = db.session.get(ProductionRequisition, data["id"])
            assert req is not None
            assert req.picker == "王五"

    @pytest.mark.parametrize('existing_picker, typed_picker', [
        (None, '张三'), ('王五', '李四'), ('王五', ''),
    ])
    def test_actual_form_header_roundtrip(self, existing_picker, typed_picker):
        """BUG-2026-10-20-002: execute rendered JS before posting its real header."""
        node = shutil.which('node')
        if not node:
            pytest.skip('Node.js required for the real form header callback')
        client, _ = self._setup()
        order_id = None
        if existing_picker is not None:
            response = client.post('/requisition/save_table', json={
                'order_no': 'REQ-PICKER-EDIT',
                'header': {'warehouse': '默认仓', 'picker': existing_picker},
                'items': [{'code': 'M001', 'quantity': 5}],
            })
            assert response.get_json()['status'] == 'success', response.get_json()
            order_id = response.get_json()['id']
        response = client.get(f'/requisition/{order_id}' if order_id else '/requisition/add')
        assert response.status_code == 200
        html = response.get_data(as_text=True)

        class Fields(HTMLParser):
            def __init__(self):
                super().__init__()
                self.values = {}
                self.select = None

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == 'input' and attributes.get('name'):
                    self.values[attributes['name']] = attributes.get('value', '')
                if tag == 'select':
                    self.select = attributes.get('name')
                if tag == 'option' and self.select and 'selected' in attributes:
                    self.values[self.select] = attributes.get('value', '')

            def handle_endtag(self, tag):
                if tag == 'select':
                    self.select = None

        fields = Fields()
        fields.feed(html)
        assert 'picker' in fields.values
        fields.values['picker'] = typed_picker
        function = 'function collectHeader() {' + html.split('function collectHeader() {', 1)[1].split(
            '\nfunction submitForm', 1)[0]
        script = 'const docType="requisition"; const fields=' + json.dumps(fields.values) + ';'
        script += '''const document={querySelector(s){
            const name=s.match(/name="([^"]+)"/)[1];
            return name in fields ? {value:fields[name]} : null;
        }};'''
        script += function + '\nprocess.stdout.write(JSON.stringify(collectHeader()));'
        output = subprocess.run([node, '-e', script], text=True, encoding='utf-8',
                                capture_output=True, check=True)
        header = json.loads(output.stdout)
        assert header.get('picker') == typed_picker
        response = client.post('/requisition/save_table', json={
            'order_id': order_id, 'order_no': fields.values['order_no'],
            'date': fields.values['date'], 'header': header,
            'items': [{'code': 'M001', 'quantity': 5}],
        })
        data = response.get_json()
        assert data['status'] == 'success', data
        with app_module.app.app_context():
            assert db.session.get(ProductionRequisition, data['id']).picker == typed_picker
        html = client.get(f"/requisition/{data['id']}").get_data(as_text=True)
        assert f'name="picker" value="{typed_picker}"' in html
