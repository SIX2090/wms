# -*- coding: utf-8 -*-
"""F2.7 / S9 回归：安全响应头补齐（CSP + HSTS）。"""
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
from config import ProductionConfig  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def test_production_config_defines_csp():
    csp = ProductionConfig.SECURITY_HEADERS.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "base-uri 'self'" in csp


def test_production_config_defines_hsts():
    hsts = ProductionConfig.SECURITY_HEADERS.get("Strict-Transport-Security", "")
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts


def test_security_headers_applied_to_response():
    """after_request 把 SECURITY_HEADERS 落到真实响应上。"""
    original = app_module.app.config.get("SECURITY_HEADERS")
    app_module.app.config["SECURITY_HEADERS"] = dict(ProductionConfig.SECURITY_HEADERS)
    try:
        resp = app_module.app.test_client().get("/login")
        assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
        assert "max-age=" in resp.headers.get("Strict-Transport-Security", "")
    finally:
        if original is None:
            app_module.app.config.pop("SECURITY_HEADERS", None)
        else:
            app_module.app.config["SECURITY_HEADERS"] = original


def test_nginx_conf_has_hsts_header():
    conf = (APP_DIR / "nginx_wms_server_block.conf").read_text(encoding="utf-8")
    assert "Strict-Transport-Security" in conf
    assert "max-age=31536000" in conf
