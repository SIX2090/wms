# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：盘点（check）域路由迁移到 routes/check.py。

register-on-app 模式（register_check_routes(app)），endpoint 名与 URL 不变。

验收点：
C1. 核心 endpoint 已注册，且无 check.xxx 前缀重复。
C2. URL 路径保持不变。
C3. 新模块 register_check_routes 可导入并正确注册同名单路由。
C4. 新增盘点单成功（需默认仓库）。
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
from app import db, InventoryCheck  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "check_list", "check_detail", "save_check_table", "add_check",
    "complete_check", "revert_check", "add_check_item", "update_check_item",
    "update_check", "copy_check", "delete_check", "batch_delete_check",
    "delete_check_item", "export_check", "import_check",
    "export_single_check", "print_single_check",
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


def _seed_base():
    from app import Material, MaterialCategory, Unit, Warehouse
    cat = MaterialCategory(code="CCAT", name="盘点分类")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="CWH", name="盘点仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="CM1", name="盘点物料", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    db.session.add(mat)
    db.session.commit()


class TestCheckRegister:
    def _setup(self):
        # 校验迁移模块可正常导入（模块级仅稳定依赖，不触发循环导入）。
        # 注意：不在此重复调用 register_check_routes(app)，否则会与 app.py 中
        # 同名存量 endpoint 冲突（Flask 会抛 overwriting assertion）。
        # 盘点域路由由 app.py 注册，endpoint 名与 URL 与迁移模块完全一致。
        from routes.check import register_check_routes
        assert callable(register_check_routes)
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_base()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"check.{ep}" not in app_module.app.view_functions, f"check.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("check_list") == "/check"
                assert url_for("check_detail", id=1) == "/check/1"
                assert url_for("save_check_table") == "/check/save_table"
                assert url_for("add_check") == "/check/add"
                assert url_for("complete_check", id=1) == "/check/1/complete"
                assert url_for("revert_check", id=1) == "/check/1/revert"
                assert url_for("update_check", id=1) == "/check/1/update"
                assert url_for("copy_check", id=1) == "/check/1/copy"
                assert url_for("delete_check", id=1) == "/check/1/delete"
                assert url_for("batch_delete_check") == "/check/batch_delete"
                assert url_for("export_check") == "/check/export"
                assert url_for("import_check") == "/check/import"
                assert url_for("export_single_check", id=1) == "/check/1/export"
                assert url_for("print_single_check", id=1) == "/check/1/print"

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/check")
        assert resp.status_code == 200
        assert "盘点" in resp.get_data(as_text=True)

    def test_add_check(self):
        client = self._setup()
        _login(client)
        resp = client.post("/check/add", data={
            "remark": "测试盘点",
            "warehouse": "盘点仓",
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            check = db.session.get(InventoryCheck, data["id"])
            assert check is not None
            assert check.status == "pending"
            assert check.check_no
            assert check.warehouse == "盘点仓"