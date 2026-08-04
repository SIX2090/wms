# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-005 回归测试：spec_changed 比较在赋值之后导致永为 False

原 Bug：
  edit_material 中先执行 `material.spec = new_spec`，
  再判断 `spec_changed = (material.spec != new_spec)`，
  此时 material.spec 已等于 new_spec，比较永远为 False。
  后果：物料规格变更后，所有关联单据（采购申请/BOM）的 spec 字段不会级联更新。

  更严重：级联代码引用了 InOrderItem/OutOrderItem/InventoryCheckItem/
  SubcontractItem/BOMItem 不存在的 material_code/material_name/spec 字段，
  一旦 spec_changed 为 True 会抛 AttributeError，导致编辑物料直接 500。

修复：
  1. 在赋值前捕获 old_spec，据此计算 spec_changed。
  2. 级联代码对没有冗余字段的明细类跳过赋值（用 hasattr 守卫或直接跳过）。

测试：
  T1. 修改物料规格（不改 code/name）后，PurchaseRequestItem.spec 被级联更新
  T2. 修改物料规格后，不抛 AttributeError（编辑成功返回 200）
  T3. 不改规格时，PurchaseRequestItem.spec 保持不变
  T4. 修改物料名称后，PurchaseRequestItem.material_name 被级联更新
"""
from __future__ import annotations

import os
import sys
import re
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
from app import db, User, Material, PurchaseRequestItem, PurchaseRequest  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add(user)
    db.session.commit()


def _login(client):
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


class TestBug20260804005SpecChangedCascade:
    """物料规格变更必须级联更新关联单据的冗余 spec 字段。"""

    def test_T1_spec_change_cascades_to_purchase_request_item(self):
        """修改物料规格后，PurchaseRequestItem.spec 被级联更新。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            mat = Material(code="M001", name="轴承", spec="旧规格", price=10)
            db.session.add(mat)
            db.session.commit()
            pr = PurchaseRequest(request_no="PR001")
            db.session.add(pr)
            db.session.flush()
            item = PurchaseRequestItem(
                purchase_request_id=pr.id,
                material_id=mat.id,
                material_code="M001",
                material_name="轴承",
                spec="旧规格",
                quantity=1,
                estimated_price=10,
                estimated_amount=10,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/material/edit/{mat.id}", data={
                "code": "M001",
                "name": "轴承",
                "spec": "新规格",
                "brand": "",
                "price": "10",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", data

            db.session.expire_all()
            refreshed = db.session.get(PurchaseRequestItem, item_id)
            assert refreshed.spec == "新规格", \
                f"规格应级联更新为 '新规格'，实际为 '{refreshed.spec}'"

    def test_T2_spec_change_does_not_raise_attribute_error(self):
        """修改物料规格后不抛 AttributeError（编辑成功返回 200）。

        原 bug：spec_changed 为 True 后，级联代码访问 InOrderItem.spec
        等不存在的字段会抛 AttributeError，导致编辑 500。
        """
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            mat = Material(code="M002", name="螺母", spec="M8", price=1)
            db.session.add(mat)
            db.session.commit()

            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/material/edit/{mat.id}", data={
                "code": "M002",
                "name": "螺母",
                "spec": "M10",
                "brand": "",
                "price": "1",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", \
                f"修改规格不应抛 AttributeError：{data}"

    def test_T3_no_spec_change_keeps_purchase_request_item_spec(self):
        """不改规格时，PurchaseRequestItem.spec 保持不变。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            mat = Material(code="M003", name="螺栓", spec="M8x20", price=0.5)
            db.session.add(mat)
            db.session.commit()
            pr = PurchaseRequest(request_no="PR003")
            db.session.add(pr)
            db.session.flush()
            item = PurchaseRequestItem(
                purchase_request_id=pr.id,
                material_id=mat.id,
                material_code="M003",
                material_name="螺栓",
                spec="M8x20",
                quantity=10,
                estimated_price=0.5,
                estimated_amount=5,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

            client = app_module.app.test_client()
            _login(client)
            # 只改备注，不改规格
            resp = client.post(f"/material/edit/{mat.id}", data={
                "code": "M003",
                "name": "螺栓",
                "spec": "M8x20",
                "brand": "",
                "price": "0.5",
                "remark": "更新备注",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)

            db.session.expire_all()
            refreshed = db.session.get(PurchaseRequestItem, item_id)
            assert refreshed.spec == "M8x20", \
                f"未改规格时 spec 应保持 'M8x20'，实际为 '{refreshed.spec}'"

    def test_T4_name_change_cascades_to_purchase_request_item(self):
        """修改物料名称后，PurchaseRequestItem.material_name 被级联更新。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            mat = Material(code="M004", name="旧名称", spec="规格A", price=2)
            db.session.add(mat)
            db.session.commit()
            pr = PurchaseRequest(request_no="PR004")
            db.session.add(pr)
            db.session.flush()
            item = PurchaseRequestItem(
                purchase_request_id=pr.id,
                material_id=mat.id,
                material_code="M004",
                material_name="旧名称",
                spec="规格A",
                quantity=1,
                estimated_price=2,
                estimated_amount=2,
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/material/edit/{mat.id}", data={
                "code": "M004",
                "name": "新名称",
                "spec": "规格A",
                "brand": "",
                "price": "2",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)

            db.session.expire_all()
            refreshed = db.session.get(PurchaseRequestItem, item_id)
            assert refreshed.material_name == "新名称", \
                f"名称应级联更新为 '新名称'，实际为 '{refreshed.material_name}'"
