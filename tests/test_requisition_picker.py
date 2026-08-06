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
from pathlib import Path

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