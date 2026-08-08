# -*- coding: utf-8 -*-
"""
手机端识物（外包装/物品表面文字 + 图形外观识别）API 回归测试（AI-MOB-REC-F01）。

覆盖：
T1. POST /mobile/api/recognize_material 端点注册。
T2. 文字识别：视觉模型提取到 code/name -> 匹配建档物料。
T3. 图形/外观识别：code/name/spec 全空，仅 description -> 用描述中的型号字母数字匹配物料。
T4. description 中文关键词回退匹配（无字母数字型号）。
T5. 完全无法识别（description 空且无法匹配）-> 返回空 matches，不报错。
T6. 未启用大模型/图片识别 -> 返回 400。
"""
from __future__ import annotations

import io
import os
import sys
import unittest
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

API_ENDPOINTS = ["mobile_recognize_material"]

# 1x1 透明 PNG，作为上传图片占位
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf"
    b"\xc0\x00\x00\x00\x03\x00\x01\x82\x9a\x97\xc6\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    # 该端点用 Flask-Login @login_required（依赖 session），需走 Web 登录表单建立会话。
    r = client.post("/login", data={
        "username": "admin",
        "password": "admin",
        "login_mode": "user",
        "usage_consent": "1",
    })
    assert r.status_code in (200, 302), r.get_data(as_text=True)
    return {}


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_material(code, name, spec="", stock=5, price=10):
    from app import Material
    with app_module.app.app_context():
        m = Material(code=code, name=name, spec=spec, stock=stock, price=price)
        db.session.add(m)
        db.session.commit()
        return m.id


def _post_image(client, headers, extracted):
    """封装修复 captured 的视觉模型返回，POST 图片到识别端点。"""
    app_module._ai_call_llm_vision = lambda prompt, images: ("识别完成", extracted, "")
    app_module._ai_llm_configured = lambda: True
    app_module._ai_llm_vision_enabled = lambda: True
    data = {
        "image": (io.BytesIO(_PNG), "material.png"),
    }
    return client.post("/mobile/api/recognize_material", data=data,
                       content_type="multipart/form-data", headers=headers)


class TestMobileRecognizeMaterialApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()

    def setUp(self):
        from app import Material
        with app_module.app.app_context():
            Material.query.delete()
            db.session.commit()
        self.client = _make_client()
        self.headers = _login(self.client)

    def test_endpoint_registered(self):
        """T1：端点注册。"""
        from app import app
        self.assertIn("/mobile/api/recognize_material",
                      [str(r.rule) for r in app.url_map.iter_rules()])

    def test_text_recognition_matches_by_code(self):
        """T2：文字识别，视觉模型给出 code -> 匹配建档物料。"""
        _seed_material("6204", "深沟球轴承", "6204")
        r = _post_image(self.client, self.headers,
                        {"code": "6204", "name": "深沟球轴承", "spec": "6204",
                         "quantity": 10, "confidence": 0.9, "description": "金属轴承"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["status"], "success", body)
        self.assertEqual(body["extracted"]["code"], "6204")
        self.assertGreaterEqual(body["match_count"], 1)
        self.assertEqual(body["matches"][0]["code"], "6204")

    def test_graphics_recognition_matches_by_description_token(self):
        """T3：图形/外观识别，code/name/spec 全空，仅 description 含型号 -> 匹配。"""
        _seed_material("6204", "深沟球轴承", "6204")
        r = _post_image(self.client, self.headers,
                        {"code": "", "name": "", "spec": "",
                         "quantity": None, "confidence": 0.6,
                         "description": "金属银色深沟球轴承 6204"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["status"], "success", body)
        self.assertGreaterEqual(body["match_count"], 1)
        self.assertEqual(body["matches"][0]["code"], "6204")

    def test_description_chinese_keyword_fallback(self):
        """T4：无字母数字型号，整段描述关键词回退匹配。"""
        _seed_material("R111", "继电器", "红色塑料外壳 24V")
        r = _post_image(self.client, self.headers,
                        {"code": "", "name": "", "spec": "",
                         "quantity": None, "confidence": 0.5,
                         "description": "红色塑料外壳继电器"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["status"], "success", body)
        self.assertGreaterEqual(body["match_count"], 1)
        self.assertEqual(body["matches"][0]["name"], "继电器")

    def test_unrecognizable_returns_empty_matches(self):
        """T5：完全无法识别 -> 返回空 matches，不报错。"""
        _seed_material("6204", "深沟球轴承", "6204")
        r = _post_image(self.client, self.headers,
                        {"code": "", "name": "", "spec": "",
                         "quantity": None, "confidence": 0.0,
                         "description": "无法识别的黑色物体"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["status"], "success", body)
        self.assertEqual(body["match_count"], 0)
        self.assertEqual(body["matches"], [])

    def test_vision_disabled_returns_400(self):
        """T6：未启用大模型/图片识别 -> 400。"""
        app_module._ai_llm_configured = lambda: False
        app_module._ai_llm_vision_enabled = lambda: False
        data = {"image": (io.BytesIO(_PNG), "material.png")}
        r = self.client.post("/mobile/api/recognize_material", data=data,
                             content_type="multipart/form-data", headers=self.headers)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn("启用", r.get_json()["msg"])


if __name__ == "__main__":
    unittest.main(verbosity=2)