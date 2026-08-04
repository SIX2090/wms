# -*- coding: utf-8 -*-
"""
复现：复制物料并保存后，采购入库单是否显示该物料

流程：
  T1. 复制物料 → 保存 → GET /in_order/add → 渲染的 materials 应包含新物料
  T2. GET /material/api/all → materials 应包含新物料（前端“刷新物料”读取）
"""
from __future__ import annotations

import os
import sys
import re
import json
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


class TestReproCopyMaterialInOrder:
    def test_T1_copied_material_in_rendered_in_order(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            src = Material(code="M001", name="轴承", spec="6204", price=10)
            db.session.add(src)
            db.session.commit()
            src_id = src.id

            client = app_module.app.test_client()
            _login(client)

            copy_resp = client.post(f"/material/{src_id}/copy")
            assert copy_resp.status_code == 200, copy_resp.get_data(as_text=True)
            copy_data = copy_resp.get_json()
            suggested_code = copy_data["material"]["suggested_code"]
            suggested_name = copy_data["material"]["name"]

            add_resp = client.post("/material/add", data={
                "code": suggested_code,
                "name": suggested_name,
                "spec": "6204",
                "brand": "",
                "price": "10",
            })
            assert add_resp.status_code == 200, add_resp.get_data(as_text=True)
            assert add_resp.get_json()["status"] == "success"

            # 渲染采购入库单页面
            page = client.get("/in_order/add").get_data(as_text=True)
            m = re.search(r'const materials = (\[.*?\]);', page, re.S)
            assert m, "页面应包含 materials 变量"
            materials = json.loads(m.group(1))
            codes = [x.get("code") for x in materials]
            assert suggested_code in codes, \
                f"新物料 {suggested_code} 应出现在采购入库单渲染 materials 中，实际 {codes}"

    def test_T2_copied_material_in_material_api_all(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            src = Material(code="M001", name="轴承", spec="6204", price=10)
            db.session.add(src)
            db.session.commit()
            src_id = src.id

            client = app_module.app.test_client()
            _login(client)

            copy_resp = client.post(f"/material/{src_id}/copy")
            suggested_code = copy_resp.get_json()["material"]["suggested_code"]
            suggested_name = copy_resp.get_json()["material"]["name"]
            client.post("/material/add", data={
                "code": suggested_code,
                "name": suggested_name,
                "spec": "6204",
                "brand": "",
                "price": "10",
            })

            resp = client.get("/material/api/all")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            codes = [m["code"] for m in data["materials"]]
            assert suggested_code in codes, \
                f"新物料 {suggested_code} 应出现在 /material/api/all 中，实际 {codes}"