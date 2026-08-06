# -*- coding: utf-8 -*-
"""
采购入库单下推领料单：领料部门(department_id)与领料人(picker)字段的回归测试。

验收点：
P1. 下推页面 (in_order_push.html) 渲染"领料部门"下拉框与"领料人"输入框。
P2. 下推创建接口 (POST /in_order/<id>/push) 将 department_id 与 picker 保存到 OutOrder。
P3. 领料单新增/保存接口 (POST /out_order/add) 持久化 picker 字段。
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
from app import (  # noqa: E402
    Department, InOrder, InOrderItem, Material, OutOrder, Unit, Warehouse, db,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    from app import User
    unit = Unit(code="U1", name="个")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    dept = Department(code="D001", name="生产部", status="active")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100, price=10)
    db.session.add_all([unit, wh, dept, user, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "dept": dept, "user": user}


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _make_completed_in_order(mat, qty=10):
    order = InOrder(
        order_no="IN-PUSH-001", business_type="采购入库",
        status="completed", warehouse="仓库A", total_amount=qty * 10,
    )
    db.session.add(order)
    db.session.flush()
    item = InOrderItem(
        in_order_id=order.id, material_id=mat.id,
        quantity=qty, price=10, amount=qty * 10,
    )
    db.session.add(item)
    db.session.commit()
    return order


class TestOutOrderPushPicker:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            dept_id = seeds["dept"].id
            order = _make_completed_in_order(seeds["mat"])
            order_id = order.id
        client = app_module.app.test_client()
        _login(client)
        return client, seeds, order_id, dept_id

    def test_P1_push_page_renders_department_and_picker(self):
        client, seeds, order_id, dept_id = self._setup()
        html = client.get(f"/in_order/{order_id}/push?target=requisition").get_data(as_text=True)
        assert 'id="departmentId"' in html, "下推页必须渲染领料部门下拉框"
        assert 'id="picker"' in html, "下推页必须渲染领料人输入框"
        assert "生产部" in html, "领料部门下拉框应包含可选部门"

    def test_P2_push_creates_out_order_with_department_and_picker(self):
        client, seeds, order_id, dept_id = self._setup()
        payload = {
            "target_type": "requisition",
            "request_id": "req-test-001",
            "department_id": str(dept_id),
            "picker": "张三",
            "purpose": "领料用途",
            "items": [{"source_item_id": order_id, "quantity": 5}],
        }
        # source_item_id 是来源明细 id，需先查出来
        with app_module.app.app_context():
            item_id = InOrderItem.query.filter_by(in_order_id=order_id).first().id
        payload["items"] = [{"source_item_id": item_id, "quantity": 5}]
        resp = client.post(f"/in_order/{order_id}/push", json=payload)
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            out = OutOrder.query.filter_by(order_no=data["order_no"]).first()
            assert out is not None
            assert out.department_id == dept_id
            assert out.picker == "张三"

    def test_P3_add_out_order_persists_picker(self):
        client, seeds, _, dept_id = self._setup()
        payload = {
            "business_type": "领料单",
            "department_id": str(dept_id),
            "picker": "李四",
            "warehouse": "仓库A",
            "items": [{"code": "M001", "quantity": 3}],
        }
        resp = client.post("/out_order/add", json=payload)
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            out = db.session.get(OutOrder, data["id"])
            assert out is not None
            assert out.picker == "李四"