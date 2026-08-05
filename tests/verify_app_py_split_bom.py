# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：物料清单（bom）域路由迁移到 routes/bom.py。

register-on-app 模式（register_bom_routes(app)），endpoint 名与 URL 不变。

验收点：
B1. 核心 endpoint 已注册，且无 bom.xxx 前缀重复。
B2. URL 路径保持不变。
B3. 新增 BOM 成功（add_bom 走 /bom/add form 表单）。
B4. save_bom_table 保存 BOM 明细成功（需物料/单位）。
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
from app import db, BOM  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "bom_list", "bom_detail", "print_bom", "bom_add_page",
    "save_bom_table", "add_bom", "update_bom", "add_bom_item",
    "add_bom_item_alias", "delete_bom_item", "delete_bom_item_alias",
    "delete_bom", "delete_bom_alias", "batch_delete_bom",
    "calculate_bom_cost", "export_bom", "import_bom",
    "create_requisition_from_bom",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


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


_MATERIAL_ID = {"id": None}


def _seed_base():
    from app import Material, MaterialCategory, Unit
    cat = MaterialCategory(code="BCAT", name="BOM分类")
    unit = Unit(code="PCS", name="个")
    db.session.add_all([cat, unit])
    db.session.flush()
    mat = Material(code="BM1", name="BOM物料", category_id=cat.id,
                   unit_id=unit.id, stock=100, price=5)
    db.session.add(mat)
    db.session.commit()
    _MATERIAL_ID["id"] = mat.id
    _MATERIAL_ID["unit_id"] = unit.id


class TestBomRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_base()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"bom.{ep}" not in app_module.app.view_functions, f"bom.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("bom_list") == "/bom"
                assert url_for("bom_detail", id=1) == "/bom/1"
                assert url_for("print_bom", id=1) == "/bom/1/print"
                assert url_for("bom_add_page") == "/bom/add"
                assert url_for("add_bom") == "/bom/add"
                assert url_for("update_bom", id=1) == "/bom/1/update"
                assert url_for("add_bom_item", id=1) == "/bom/1/item/add"
                assert url_for("delete_bom", id=1) == "/bom/1/delete"
                assert url_for("batch_delete_bom") == "/bom/batch_delete"
                assert url_for("calculate_bom_cost", id=1) == "/bom/1/calculate_cost"
                assert url_for("export_bom") == "/bom/export"
                assert url_for("import_bom") == "/bom/import"
                assert url_for("create_requisition_from_bom", bom_id=1) == "/bom/1/create_requisition"

    def test_add_bom(self):
        # add_bom 走 /bom/add 的 form 表单（request.form）
        client = self._setup()
        _login(client)
        resp = client.post("/bom/add", data={
            "product_code": "BP001",
            "product_name": "测试成品",
            "version": "1.0",
            "remark": "BOM回归测试",
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            bom = BOM.query.filter_by(product_code="BP001").first()
            assert bom is not None
            assert bom.product_name == "测试成品"
            assert bom.status == "active"

    def test_save_bom_table(self):
        # save_bom_table 走 /bom/save_table 的 JSON 请求，需物料+单位
        client = self._setup()
        _login(client)
        resp = client.post("/bom/save_table", json={
            "order_no": "BOM-TEST-001",
            "product_code": "BP002",
            "product_name": "测试成品2",
            "version": "V1.0",
            "items": [{
                "code": "BM1",
                "quantity": 2,
                "price": 5,
            }],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            bom = db.session.get(BOM, data["id"])
            assert bom is not None
            assert bom.bom_no == "BOM-TEST-001"
            assert len(bom.items) == 1
            assert bom.items[0].quantity == 2
            assert bom.total_cost == 10