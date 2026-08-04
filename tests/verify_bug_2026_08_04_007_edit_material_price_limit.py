# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-007 回归测试：编辑物料价格上限与新增不一致

原 Bug：
  add_material 使用 MAX_REASONABLE_PRICE = 99_999_999.99 作为价格上限，
  但 edit_material 使用 MAX_TRANSACTION_PRICE = 1_000_000_000_000（1 万亿），
  导致用户可以先低价新增物料，再编辑改成天价，绕过新增时的价格上限。

修复：
  edit_material 改用 MAX_REASONABLE_PRICE，与 add_material 保持一致。

测试：
  T1. 编辑物料价格 = 100,000,000（超出 99,999,999.99 上限）→ 400 拒绝
  T2. 编辑物料价格 = 99,999,999.99（恰好上限）→ 200 成功
  T3. 编辑物料价格 = 50（正常值）→ 200 成功
  T4. 新增物料价格 = 100,000,000（超出上限）→ 400 拒绝（验证新增侧仍正确）
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
from app import db, User, Material  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

MAX_REASONABLE_PRICE = 99_999_999.99


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


class TestBug20260804007EditMaterialPriceLimit:
    """编辑物料价格上限必须与新增一致（MAX_REASONABLE_PRICE）。"""

    def test_T1_edit_price_above_limit_rejected(self):
        """编辑物料价格 = 100,000,000（超出上限）→ 400 拒绝。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            mat = Material(code="M001", name="轴承", spec="6204", price=10)
            db.session.add(mat)
            db.session.commit()

            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/material/edit/{mat.id}", data={
                "code": "M001",
                "name": "轴承",
                "spec": "6204",
                "brand": "",
                "price": "100000000",  # > 99,999,999.99
            })
            assert resp.status_code == 400, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "error"
            # 确认价格未被修改
            db.session.expire_all()
            refreshed = db.session.get(Material, mat.id)
            assert refreshed.price == 10, "超限价格不应被写入"

    def test_T2_edit_price_at_limit_accepted(self):
        """编辑物料价格 = 99,999,999.99（恰好上限）→ 200 成功。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            mat = Material(code="M001", name="轴承", spec="6204", price=10)
            db.session.add(mat)
            db.session.commit()

            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/material/edit/{mat.id}", data={
                "code": "M001",
                "name": "轴承",
                "spec": "6204",
                "brand": "",
                "price": str(MAX_REASONABLE_PRICE),
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", data
            db.session.expire_all()
            refreshed = db.session.get(Material, mat.id)
            assert float(refreshed.price) == MAX_REASONABLE_PRICE

    def test_T3_edit_normal_price_accepted(self):
        """编辑物料价格 = 50（正常值）→ 200 成功。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            mat = Material(code="M001", name="轴承", spec="6204", price=10)
            db.session.add(mat)
            db.session.commit()

            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/material/edit/{mat.id}", data={
                "code": "M001",
                "name": "轴承",
                "spec": "6204",
                "brand": "",
                "price": "50",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", data
            db.session.expire_all()
            refreshed = db.session.get(Material, mat.id)
            assert float(refreshed.price) == 50

    def test_T4_add_price_above_limit_rejected(self):
        """新增物料价格 = 100,000,000（超出上限）→ 400 拒绝。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()

            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/material/add", data={
                "code": "M002",
                "name": "螺母",
                "spec": "M8",
                "brand": "",
                "price": "100000000",  # > 99,999,999.99
                "stock": "0",
            })
            assert resp.status_code == 400, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "error"
            # 确认物料未被创建
            assert Material.query.filter_by(code="M002").first() is None
