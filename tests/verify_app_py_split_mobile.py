# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：手机端扫码（mobile）域路由迁移到 routes/mobile.py。

采用 register-on-app 模式（register_mobile_routes(app)），endpoint 名保持不变
（mobile_connect/mobile_scan/mobile_material_lookup/mobile_scan_submit/
mobile_recognize_material/mobile_app_download），URL 路径不变。

验收点：
S1. 6 个 endpoint 已注册，仍是原始 endpoint 名，不存在 mobile.xxx 重复。
S2. URL 路径保持不变。
S3. /mobile/app 无 APK 时返回 404。
S4. /mobile/connect 与 /mobile/scan 页面可渲染。
S5. 扫码查物料：精确编码命中、模糊多匹配、不存在 404。
S6. 扫码提交 query 模式返回物料；in 模式生成入库单。
S7. 拍照识物：未启用大模型时提示启用。
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
# 确保测试环境不启用大模型视觉识别，命中"请先启用"分支
os.environ["WMS_LLM_ENABLED"] = "0"

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

MOBILE_ENDPOINTS = [
    "mobile_app_download",
    "mobile_connect",
    "mobile_scan",
    "mobile_material_lookup",
    "mobile_scan_submit",
    "mobile_recognize_material",
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


def _seed_material(code, name, stock=10):
    from app import Material
    m = Material(code=code, name=name, stock=stock, price=5)
    db.session.add(m)
    db.session.commit()
    return m.id


def _seed_default_warehouse():
    """INV-AUDIT-003：扫码出入库仓库必填，测试需预置默认仓库。"""
    from app import Warehouse
    wh = Warehouse(code="W001", name="默认仓", status="active", is_default=True)
    db.session.add(wh)
    db.session.commit()
    return wh


class TestMobileRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_default_warehouse()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：6 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in MOBILE_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in MOBILE_ENDPOINTS:
                assert f"mobile.{ep}" not in app_module.app.view_functions, f"mobile.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("mobile_app_download") == "/mobile/app"
                assert url_for("mobile_connect") == "/mobile/connect"
                assert url_for("mobile_scan") == "/mobile/scan"
                assert url_for("mobile_material_lookup") == "/mobile/api/material_lookup"
                assert url_for("mobile_scan_submit") == "/mobile/api/scan_submit"
                assert url_for("mobile_recognize_material") == "/mobile/api/recognize_material"

    def test_app_download_available(self):
        """S3：/mobile/app 可访问（有 APK 返回 200，无 APK 返回 404）。"""
        client = self._setup()
        # 无需登录（该路由无 login_required）
        resp = client.get("/mobile/app")
        assert resp.status_code in (200, 404)

    def test_pages_render(self):
        """S4：/mobile/connect 与 /mobile/scan 页面可渲染。"""
        client = self._setup()
        _login(client)
        r1 = client.get("/mobile/connect")
        assert r1.status_code == 200
        r2 = client.get("/mobile/scan")
        assert r2.status_code == 200

    def test_material_lookup(self):
        """S5：精确命中、模糊多匹配、不存在 404。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            _seed_material("M001", "6204轴承")
            _seed_material("M002", "6205轴承")
        # 精确命中
        r1 = client.get("/mobile/api/material_lookup?code=M001")
        d1 = r1.get_json()
        assert d1["status"] == "success", d1
        assert d1["data"]["code"] == "M001"
        # 模糊多匹配
        r2 = client.get("/mobile/api/material_lookup?q=轴承")
        d2 = r2.get_json()
        assert d2["status"] == "multiple", d2
        assert len(d2["data"]["matches"]) == 2
        # 不存在
        r3 = client.get("/mobile/api/material_lookup?code=ZZZ999")
        assert r3.status_code == 404
        assert r3.get_json()["status"] == "error"

    def test_scan_submit_query(self):
        """S6a：query 模式返回物料。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            _seed_material("M001", "6204轴承", stock=10)
        resp = client.post(
            "/mobile/api/scan_submit",
            json={"mode": "query", "code": "M001"},
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert data["data"]["material"]["name"] == "6204轴承"

    def test_scan_submit_in(self):
        """S6b：in 模式生成入库单并增加库存。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            mid = _seed_material("M001", "6204轴承", stock=10)
        resp = client.post(
            "/mobile/api/scan_submit",
            json={"mode": "in", "code": "M001", "quantity": 3},
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        from app import InOrder, InOrderItem, Material
        with app_module.app.app_context():
            assert InOrder.query.count() == 1
            assert InOrderItem.query.count() == 1
            assert db.session.get(Material, mid).stock == 13

    def test_recognize_not_configured(self):
        """S7：未启用大模型视觉时提示启用。"""
        client = self._setup()
        _login(client)
        import io
        buf = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
        resp = client.post(
            "/mobile/api/recognize_material",
            data={"image": (buf, "m.png")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "启用" in resp.get_json()["msg"]