# -*- coding: utf-8 -*-
"""移动端扫码出库「领料部门 + 领料人」下拉选择回归测试（2026-09-12 用户需求）。

需求：手机 App 扫码出库界面新增两个选填下拉——领料部门（Department 表）、
领料人（Employee 表，可按部门过滤）；提交后落库到 OutOrder.department_id /
OutOrder.picker（专用字段，不再把部门借用进 purpose 文本）。

后端设计（与 PC 领料单口径统一，见 routes/mobile.py 扫码出库提交）：
- GET /api/departments：仅返回启用部门（status=active）；
- GET /api/employees：返回员工列表（含 department_id/department_name），
  支持 ?department_id= 过滤；
- POST /api/outbound：department_id 优先、department 文本按 code/name 查询兜底，
  命中部门 → department_id + customer=部门名；picker → OutOrder.picker；
  旧 payload（仅 receiver 文本）行为兼容：customer=receiver 文本。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TODAY = date.today()


def _seed():
    from app import Department, Employee, Material, Unit, User, Warehouse

    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    wh = Warehouse(code="WH01", name="材料仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    db.session.add(Material(code="MAT001", name="6204轴承", spec="20*47*14",
                            stock=100, price=1.5, unit=unit))

    dept_a = Department(code="SB", name="生产部", status="active")
    dept_b = Department(code="CB", name="仓储部", status="active")
    dept_off = Department(code="TY", name="停用部门", status="inactive")
    db.session.add_all([dept_a, dept_b, dept_off])
    db.session.flush()
    db.session.add_all([
        Employee(code="E001", name="张三", position="操作工", department_id=dept_a.id),
        Employee(code="E002", name="李四", position="班长", department_id=dept_a.id),
        Employee(code="E003", name="王五", position="仓管员", department_id=dept_b.id),
        Employee(code="E004", name="赵六", position="无部门"),  # department_id=None
    ])
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        _seed()
        db.session.remove()
    c = app_module.app.test_client()
    yield c
    with app_module.app.app_context():
        db.session.remove()


def _bearer(c):
    resp = c.post("/api/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {"Authorization": f"Bearer {resp.get_json()['data']['token']}"}


def _outbound_payload(**extra):
    payload = {
        "business_type": "领料单",
        "warehouse": "材料仓",
        "lines": [{"material_code": "MAT001", "quantity": 10}],
    }
    payload.update(extra)
    return payload


class TestDepartmentsList:
    def test_returns_active_departments(self, client):
        resp = client.get("/api/departments", headers=_bearer(client))
        assert resp.status_code == 200
        items = resp.get_json()["data"]["items"]
        names = [i["name"] for i in items]
        assert "生产部" in names and "仓储部" in names
        assert "停用部门" not in names  # inactive 过滤
        assert all({"id", "code", "name"} <= set(i) for i in items)

    def test_unauthenticated_401(self, client):
        resp = client.get("/api/departments")
        assert resp.status_code == 401


class TestEmployeesList:
    def test_returns_employees_with_department(self, client):
        resp = client.get("/api/employees", headers=_bearer(client))
        assert resp.status_code == 200
        items = resp.get_json()["data"]["items"]
        assert len(items) == 4
        zhangsan = next(i for i in items if i["name"] == "张三")
        assert zhangsan["department_name"] == "生产部"
        assert zhangsan["department_id"] is not None
        zhaoliu = next(i for i in items if i["name"] == "赵六")
        assert zhaoliu["department_id"] is None  # 无部门员工也返回

    def test_filter_by_department_id(self, client):
        from app import Department
        with app_module.app.app_context():
            dept_id = Department.query.filter_by(code="SB").first().id
        resp = client.get(f"/api/employees?department_id={dept_id}",
                          headers=_bearer(client))
        assert resp.status_code == 200
        names = [i["name"] for i in resp.get_json()["data"]["items"]]
        assert names == ["张三", "李四"]  # 按 code 排序：E001 张三、E002 李四

    def test_unauthenticated_401(self, client):
        resp = client.get("/api/employees")
        assert resp.status_code == 401


class TestOutboundWithDepartmentAndPicker:
    def _latest_order_fields(self):
        """在 app context 内取值返回 dict（避免 ORM 对象脱离上下文后懒加载报错）。"""
        from app import OutOrder
        with app_module.app.app_context():
            order = OutOrder.query.order_by(OutOrder.id.desc()).first()
            return {
                'department_id': order.department_id,
                'customer': order.customer,
                'picker': order.picker,
                'business_type': order.business_type,
                'purpose': order.purpose,
            }

    def test_department_id_and_picker_persisted(self, client):
        from app import Department
        with app_module.app.app_context():
            dept_id = Department.query.filter_by(code="SB").first().id
        resp = client.post("/api/outbound",
                           json=_outbound_payload(department_id=dept_id, picker="张三"),
                           headers=_bearer(client))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        order = self._latest_order_fields()
        assert order['department_id'] == dept_id
        assert order['customer'] == "生产部"  # 命中部门时 customer 落部门名（PC 口径）
        assert order['picker'] == "张三"
        assert order['business_type'] == "领料单"

    def test_department_text_lookup_fallback(self, client):
        """旧字段 department 文本（code 或 name）仍可命中部门。"""
        resp = client.post("/api/outbound",
                           json=_outbound_payload(department="CB", picker="王五"),
                           headers=_bearer(client))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        from app import Department
        with app_module.app.app_context():
            dept_id = Department.query.filter_by(code="CB").first().id
        order = self._latest_order_fields()
        assert order['department_id'] == dept_id
        assert order['customer'] == "仓储部"

    def test_department_text_not_found_and_receiver_compat(self, client):
        """department 文本查不到部门时不落 department_id；receiver 文本仍写 customer。"""
        resp = client.post("/api/outbound",
                           json=_outbound_payload(department="不存在的部门", receiver="张经理"),
                           headers=_bearer(client))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        order = self._latest_order_fields()
        assert order['department_id'] is None
        assert order['customer'] == "张经理"  # 兼容旧行为
        assert order['picker'] is None

    def test_legacy_payload_unchanged(self, client):
        """无新字段的旧 payload：行为完全兼容（purpose 固定、库存正常扣减）。"""
        resp = client.post("/api/outbound", json=_outbound_payload(),
                           headers=_bearer(client))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        order = self._latest_order_fields()
        assert order['department_id'] is None
        assert order['picker'] is None
        assert order['purpose'] == "Android原生端提交"
        from app import Material
        with app_module.app.app_context():
            assert Material.query.filter_by(code="MAT001").first().stock == 90
