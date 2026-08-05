# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：用户/认证/管理员控制台/操作审计（user_auth）域路由迁移到 routes/user_auth.py。

register-on-app 模式（register_user_auth_routes(app)），endpoint 名与 URL 不变。

验收点：
A1. 核心 endpoint 已注册，且无 user_auth.xxx 前缀重复。
A2. 拆分模块 routes/user_auth.py 可正常导入并暴露 register_user_auth_routes。
A3. 登录成功后访问 /user 用户列表页返回 200（管理员）。
A4. 修改密码成功（change_own_password）。
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
from app import User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "change_own_password", "login", "logout", "admin_console",
    "admin_mobile_tokens", "revoke_mobile_token", "user_list",
    "operation_audit_page", "add_user", "edit_user", "edit_my_profile",
    "update_user_status", "delete_user", "reset_user_password",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", status="normal", must_change_password=False)
    db.session.add(u)
    db.session.commit()


class TestUserAuthRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_registered_no_duplicate(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"user_auth.{ep}" not in app_module.app.view_functions, f"user_auth.{ep} 重复注册"

    def test_module_importable(self):
        # 拆分模块可正常导入且暴露注册入口（不注册到 app，避免与内联路由重复）
        import routes.user_auth as user_auth_module
        assert hasattr(user_auth_module, "register_user_auth_routes")
        assert callable(user_auth_module.register_user_auth_routes)

    def _login(self, client, username="admin", password="admin"):
        return client.post(
            "/login",
            data={"username": username, "password": password},
            content_type="application/x-www-form-urlencoded",
        )

    def test_login_and_user_list_page(self):
        client = self._setup()
        resp = self._login(client)
        assert resp.status_code in (302, 200)
        resp = client.get("/user")
        assert resp.status_code == 200
        assert "admin" in resp.get_data(as_text=True)

    def test_change_own_password(self):
        client = self._setup()
        self._login(client)
        resp = client.post("/user/change_password", data={
            "current_password": "admin",
            "new_password": "Admin12345",
            "confirm_password": "Admin12345",
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            u = User.query.filter_by(username="admin").first()
            assert u.must_change_password is False

    def test_add_user(self):
        client = self._setup()
        self._login(client)
        resp = client.post("/user/add", data={
            "username": "operator1",
            "password": "Operator123",
            "role": "warehouse",
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert User.query.filter_by(username="operator1").first() is not None