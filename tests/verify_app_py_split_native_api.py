# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：原生/移动端 API + 通用数据查询（native_api）域路由迁移到
routes/native_api.py。

register-on-app 模式（register_native_api_routes(app)），endpoint 名与 URL 不变。

验收点：
A1. 核心 endpoint 已注册，且无 native_api.xxx 前缀重复。
A2. URL 路径保持不变。
A3. 拆分模块 routes/native_api.py 可正常导入并暴露 register_native_api_routes。
A4. 原生登录 /api/login 返回 token，并可用 Bearer token 访问 /api/categories。
A5. 移动端个人中心 /api/mobile/profile 登录后可访问（200）。
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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "api_csrf_refresh", "native_api_login", "native_api_inbound",
    "native_api_outbound", "native_api_stocktake", "mobile_api_dashboard",
    "mobile_api_stock_query", "mobile_api_alert_list", "mobile_api_in_order_list",
    "mobile_api_in_order_detail", "mobile_api_out_order_list",
    "mobile_api_out_order_detail", "mobile_api_profile", "api_categories",
    "api_units", "api_suppliers", "api_customers",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_base():
    from app import MaterialCategory, Unit, Warehouse
    cat = MaterialCategory(code="ACAT", name="测试分类")
    unit = Unit(code="PCS", name="个")
    # BUG-2026-08-12-004：移动端读取接口仓库必填，补默认仓库契约
    wh = Warehouse(code="WHD", name="默认仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.commit()


def _setup():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_base()
    return _make_client()


class TestNativeApiRegister:
    def test_endpoints_registered(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"native_api.{ep}" not in app_module.app.view_functions, f"native_api.{ep} 重复注册"

    def test_module_importable(self):
        # 拆分模块可正常导入且暴露注册入口（不注册到 app，避免与内联路由重复）
        import routes.native_api as native_api_module
        assert hasattr(native_api_module, "register_native_api_routes")
        assert callable(native_api_module.register_native_api_routes)

    def test_native_login_and_categories(self):
        client = _setup()
        # 原生端登录（CSRF 豁免）返回 token
        resp = client.post("/api/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success", data
        token = data["data"]["token"]
        assert token
        # 用 Bearer token 访问通用查询端点
        resp = client.get("/api/categories", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_mobile_profile(self):
        client = _setup()
        # 网页登录建立会话
        client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            content_type="application/x-www-form-urlencoded",
        )
        resp = client.get("/api/mobile/profile")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success", data
        assert data["data"]["username"] == "admin"

    def test_mobile_dashboard(self):
        client = _setup()
        client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            content_type="application/x-www-form-urlencoded",
        )
        resp = client.get("/api/mobile/dashboard")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "pending_in_orders" in data["data"]

    def test_login_when_tables_missing(self):
        """BUG-2026-08-11-001 回归：api_token/login_log 表缺失时 /api/login 不 500。"""
        client = _setup()
        with app_module.app.app_context():
            db.session.execute(db.text("DROP TABLE IF EXISTS api_token"))
            db.session.execute(db.text("DROP TABLE IF EXISTS login_log"))
            db.session.commit()
        resp = client.post("/api/login", json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200, f"缺表时登录不应 500，实际 {resp.status_code}: {resp.get_data(as_text=True)}"
        data = resp.get_json()
        assert data["status"] == "success", data
        assert data["data"]["token"]