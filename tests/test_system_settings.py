# -*- coding: utf-8 -*-
"""系统设置（system_settings）域路由回归测试。

SYS-AUDIT-002：原文件名为 verify_app_py_split_system_settings.py，pytest
默认不收集 verify_ 前缀文件。重命名为 test_system_settings.py 使 pytest
自动收集，并补充高风险路径测试。

测试用例：
  S1. 核心 endpoint 已注册（无 system_settings.xxx 前缀重复）
  S2. URL 路径保持不变
  S3. 系统设置页可渲染（200）
  S4. 保存系统设置成功
  S5. 业务数据初始化预览（只读路径）可访问
  S6. save_system_settings int 字段越界返回 400（SYS-AUDIT-002 新增）
  S7. save_system_settings select 字段非法值返回 400（SYS-AUDIT-002 新增）
  S8. save_system_settings secret 字段留空保留原值（SYS-AUDIT-002 新增）
  S9. execute_init_business_data 错确认短语返回 400（SYS-AUDIT-002 新增）
  S10. execute_init_business_data 缺密码返回 400（SYS-AUDIT-002 新增）
  S11. execute_init_business_data 错密码返回 403（SYS-AUDIT-002 新增）
  S12. execute_init_business_data 成功后 SystemSetting 恢复默认值（SYS-AUDIT-001 验证）
"""
from __future__ import annotations

import os
import sys
import re
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db, SystemSetting  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "system_settings_page", "save_system_settings", "test_ai_llm_settings",
    "preview_init_business_data", "execute_init_business_data",
    "system_settings_add_stub", "system_settings_import_stub",
    "system_settings_export_stub",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _seed_admin():
    u = app_module.User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    )
    db.session.add(u)
    db.session.commit()


def _seed_default_settings():
    """播种默认系统参数，确保 SystemSetting 表非空。"""
    from app import ensure_default_system_settings
    ensure_default_system_settings()


def test_module_register_callable():
    """新模块可导入且 register 辅助函数可调用。"""
    from routes.system_settings import register_system_settings_routes
    assert callable(register_system_settings_routes)


class TestSystemSettingsRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_default_settings()
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
        resp = client.get("/system_settings")
        assert resp.status_code == 200
        assert "系统设置" in resp.get_data(as_text=True)

    def test_save_system_settings(self):
        client = self._setup()
        resp = client.post(
            "/system_settings/save",
            data={},
            content_type="application/x-www-form-urlencoded",
        )
        data = resp.get_json()
        assert data["status"] == "success", data

    def test_preview_init_business_data(self):
        client = self._setup()
        resp = client.get("/system_settings/init_business_data/preview")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "data" in data


class TestSaveSystemSettingsValidation:
    """SYS-AUDIT-002：save_system_settings 字段校验测试。"""

    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_default_settings()
        return _make_client()

    def test_int_out_of_range_returns_400(self):
        """int 字段越界返回 400。"""
        client = self._setup()
        # 找一个 int 类型且有 min/max 约束的设置项
        from app import SYSTEM_SETTING_DEFINITIONS
        int_key = None
        int_def = None
        for key, defn in SYSTEM_SETTING_DEFINITIONS.items():
            if defn.get('type') == 'int' and defn.get('max') is not None:
                int_key = key
                int_def = defn
                break
        if not int_key:
            pytest.skip("无 int 类型带 max 的设置项")
        bad_value = int(int_def['max']) + 1
        resp = client.post(
            "/system_settings/save",
            data={int_key: str(bad_value)},
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "不能大于" in body.get("msg", "") or "整数" in body.get("msg", "")

    def test_select_invalid_value_returns_400(self):
        """select 字段非法值返回 400。"""
        client = self._setup()
        from app import SYSTEM_SETTING_DEFINITIONS
        sel_key = None
        sel_def = None
        for key, defn in SYSTEM_SETTING_DEFINITIONS.items():
            if defn.get('type') == 'select' and defn.get('options'):
                sel_key = key
                sel_def = defn
                break
        if not sel_key:
            pytest.skip("无 select 类型设置项")
        resp = client.post(
            "/system_settings/save",
            data={sel_key: "__invalid_option__"},
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "选项" in body.get("msg", "")

    def test_secret_empty_preserves_original(self):
        """secret 字段留空时保留原值。"""
        client = self._setup()
        from app import (SYSTEM_SETTING_DEFINITIONS, SystemSetting, _secret_decrypt,
                         get_system_setting)
        secret_key = None
        for key, defn in SYSTEM_SETTING_DEFINITIONS.items():
            if defn.get('type') == 'secret':
                secret_key = key
                break
        if not secret_key:
            pytest.skip("无 secret 类型设置项")
        # 先设一个值
        original = "test_secret_value_12345"
        client.post(
            "/system_settings/save",
            data={secret_key: original},
            content_type="application/x-www-form-urlencoded",
        )
        with app_module.app.app_context():
            stored = get_system_setting(secret_key, "")
            assert stored != original, "secret 不得以明文存储"
            assert stored.startswith("enc:"), "secret 应使用 enc: 前缀密文存储"
            assert _secret_decrypt(stored) == original
        # 留空提交，应保留原密文，不触发重新加密。
        client.post(
            "/system_settings/save",
            data={secret_key: ""},
            content_type="application/x-www-form-urlencoded",
        )
        with app_module.app.app_context():
            stored_after_empty_submit = SystemSetting.query.filter_by(key=secret_key).first().value
            assert stored_after_empty_submit == stored
            assert _secret_decrypt(stored_after_empty_submit) == original


class TestSetSystemSettingWriteLock:
    """SYS-AUDIT-011：set_system_setting 加写锁后仍能正常工作。"""

    def test_set_system_setting_with_for_update_works(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_default_settings()
            from app import set_system_setting, get_system_setting
            # 加锁后设置值应正常写入
            set_system_setting('ai_llm_enabled', '1')
            db.session.commit()
            assert get_system_setting('ai_llm_enabled', '0') == '1'
            # 再次更新
            set_system_setting('ai_llm_enabled', '0')
            db.session.commit()
            assert get_system_setting('ai_llm_enabled', '0') == '0'


class TestExecuteInitBusinessDataValidation:
    """SYS-AUDIT-002：execute_init_business_data 失败路径测试。"""

    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_default_settings()
        return _make_client()

    def test_wrong_confirm_phrase_returns_400(self):
        """错确认短语返回 400。"""
        client = self._setup()
        resp = client.post(
            "/system_settings/init_business_data/execute",
            data={"admin_password": "admin", "confirm_phrase": "WRONG_PHRASE", "include_master_data": "1"},
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "确认短语" in body.get("msg", "")

    def test_missing_password_returns_400(self):
        """缺密码返回 400（pydantic 校验失败）。"""
        client = self._setup()
        from app import INIT_CONFIRM_PHRASE
        resp = client.post(
            "/system_settings/init_business_data/execute",
            data={"confirm_phrase": INIT_CONFIRM_PHRASE, "include_master_data": "1"},
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 400, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "error"
        # pydantic 校验失败消息或"密码"关键词
        msg = body.get("msg", "")
        assert "参数校验失败" in msg or "密码" in msg, msg

    def test_wrong_password_returns_403(self):
        """错密码返回 403。"""
        client = self._setup()
        from app import INIT_CONFIRM_PHRASE
        resp = client.post(
            "/system_settings/init_business_data/execute",
            data={"admin_password": "wrong_password", "confirm_phrase": INIT_CONFIRM_PHRASE, "include_master_data": "1"},
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 403, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "密码" in body.get("msg", "")


class TestExecuteInitBusinessDataRestoresSettings:
    """SYS-AUDIT-001：init 成功后 SystemSetting 恢复默认值。"""

    def test_init_restores_default_settings(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_default_settings()
            from app import INIT_CONFIRM_PHRASE, SystemSetting, ensure_default_system_settings
            # 确认初始有默认设置
            before_count = SystemSetting.query.count()
            assert before_count > 0, "默认设置应已播种"

        client = _make_client()
        from app import INIT_CONFIRM_PHRASE
        resp = client.post(
            "/system_settings/init_business_data/execute",
            data={
                "admin_password": "admin",
                "confirm_phrase": INIT_CONFIRM_PHRASE,
                "include_master_data": "1",
            },
            content_type="application/x-www-form-urlencoded",
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        # SYS-AUDIT-001：消息应说明系统参数已重置为默认值
        assert "重置为默认值" in body.get("msg", ""), body.get("msg", "")

        # 验证 SystemSetting 表在 init 后仍有默认设置（非空）
        with app_module.app.app_context():
            after_count = SystemSetting.query.count()
            assert after_count > 0, f"init 后 SystemSetting 应恢复默认值（非空），实际 {after_count}"
