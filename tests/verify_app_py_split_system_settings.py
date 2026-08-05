# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：系统设置（system_settings）域路由迁移到 routes/system_settings.py。

register-on-app 模式（register_system_settings_routes(app)），endpoint 名与 URL 不变。

验收点：
S1. 核心 endpoint 已注册，且无 system_settings.xxx 前缀重复。
S2. URL 路径保持不变。
S3. 系统设置页可渲染（200）。
S4. 保存系统设置成功。
S5. 业务数据初始化预览（只读路径）可访问。
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
    "system_settings_page", "save_system_settings", "test_ai_llm_settings",
    "preview_init_business_data", "execute_init_business_data",
    "system_settings_add_stub", "system_settings_import_stub",
    "system_settings_export_stub",
]


def test_module_register_callable():
    """新模块可导入且 register 辅助函数可调用（registers 能力由各路由测试覆盖）。"""
    from routes.system_settings import register_system_settings_routes
    assert callable(register_system_settings_routes)


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


class TestSystemSettingsRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"system_settings.{ep}" not in app_module.app.view_functions, f"system_settings.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("system_settings_page") == "/system_settings"
                assert url_for("save_system_settings") == "/system_settings/save"
                assert url_for("test_ai_llm_settings") == "/system_settings/test_ai_llm"
                assert url_for("preview_init_business_data") == "/system_settings/init_business_data/preview"
                assert url_for("execute_init_business_data") == "/system_settings/init_business_data/execute"
                assert url_for("system_settings_add_stub") == "/system_settings/add"
                assert url_for("system_settings_import_stub") == "/system_settings/import"
                assert url_for("system_settings_export_stub") == "/system_settings/export"

    def test_settings_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/system_settings")
        assert resp.status_code == 200
        assert "系统设置" in resp.get_data(as_text=True)

    def test_save_system_settings(self):
        client = self._setup()
        _login(client)
        # 空表单：各类型字段走默认值，验证保存成功
        resp = client.post(
            "/system_settings/save",
            data={},
            content_type="application/x-www-form-urlencoded",
        )
        data = resp.get_json()
        assert data["status"] == "success", data

    def test_preview_init_business_data(self):
        client = self._setup()
        _login(client)
        resp = client.get("/system_settings/init_business_data/preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "data" in data