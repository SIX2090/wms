# -*- coding: utf-8 -*-
"""F2.6 / S7 回归：公开路由收紧 + APK 重定向白名单。

- label_barcode 的条码/二维码生成路由必须要求登录（匿名 302 跳登录页）。
- /mobile/app 的 WMS_ANDROID_APK_URL 重定向必须命中白名单（同源 / GitHub 发布域 /
  私网回环），拒绝任意公网第三方域（防开放重定向 / 钓鱼跳转）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from routes import mobile as mobile_routes  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


# ---------------- APK 重定向白名单（纯函数） ----------------

def test_apk_redirect_allows_same_origin():
    assert mobile_routes._apk_redirect_allowed("http://wms.local/x.apk", "wms.local:8080")
    assert mobile_routes._apk_redirect_allowed("https://wms.local/x.apk", "wms.local")


def test_apk_redirect_allows_github_release_hosts():
    for u in (
        "https://github.com/SIX2090/wms/releases/download/v1/wms.apk",
        "https://objects.githubusercontent.com/abc",
        "https://release-assets.githubusercontent.com/x",
    ):
        assert mobile_routes._apk_redirect_allowed(u, "wms.local"), u


def test_apk_redirect_allows_private_and_loopback():
    for u in (
        "http://192.168.1.10/files/wms.apk",
        "http://10.0.0.5/wms.apk",
        "http://172.16.3.4/wms.apk",
        "http://127.0.0.1:9000/wms.apk",
        "http://localhost/wms.apk",
    ):
        assert mobile_routes._apk_redirect_allowed(u, "wms.local"), u


def test_apk_redirect_rejects_public_third_party():
    for u in (
        "http://evil.example.com/wms.apk",
        "https://example.com/wms.apk",
        "http://8.8.8.8/wms.apk",
        "https://phishing.evil.org/app.apk",
    ):
        assert not mobile_routes._apk_redirect_allowed(u, "wms.local"), u


def test_apk_redirect_rejects_bad_scheme_and_empty():
    assert not mobile_routes._apk_redirect_allowed("javascript:alert(1)", "wms.local")
    assert not mobile_routes._apk_redirect_allowed("ftp://github.com/x", "wms.local")
    assert not mobile_routes._apk_redirect_allowed("", "wms.local")
    assert not mobile_routes._apk_redirect_allowed("http://", "wms.local")


# ---------------- label_barcode 公开路由收紧 ----------------

def test_barcode_image_requires_login():
    client = app_module.app.test_client()
    resp = client.get("/api/barcode/ABC123")
    # API 请求经 unauthorized() 返回 401（JSON 错误），非 API 才 302 跳登录页
    assert resp.status_code == 401, "匿名访问条码生成应被拒（401）"


def test_qrcode_image_requires_login():
    client = app_module.app.test_client()
    resp = client.get("/api/qrcode/hello")
    assert resp.status_code == 401, "匿名访问二维码生成应被拒（401）"
