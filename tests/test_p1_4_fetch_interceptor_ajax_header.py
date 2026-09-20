# -*- coding: utf-8 -*-
"""P1-4 回归：session 过期后业务页面 fetch 统一 401 跳登录，不再静默失败。

问题链：业务页面 raw fetch 打"伪 API"路径（/warehouse/api/list、
/material/api/all 等），浏览器默认不带 X-Requested-With 头 →
wants_json_error_response() 不命中 → 未登录时后端按页面请求 302 到登录页 →
前端 r.json() 解析 HTML 失败 → 静默（计划点名 in_order_add.html:1920 /
out_order_add.html:1479）。

解法（不改 233 处前端、不改后端路由契约，单点治本）：
base.html 全局 fetch 拦截器对所有**同源**请求统一注入
X-Requested-With: XMLHttpRequest —— 未登录 AJAX 统一拿到 401 JSON，
由拦截器既有 401/419 全局处理 confirm 跳登录。

测试分两层：
1. 行为契约（pytest 可执行）：未登录伪 API 请求带头 → 401 JSON；不带 → 302。
2. 结构断言（无 JS 引擎，锁拦截器源码口径）：注入逻辑/同源判断/两种
   headers 形态兼容/已有头不覆盖/CSRF 与 401 处理保留。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

import app as app_module  # noqa: E402
from app import db  # noqa: E402

BASE_HTML = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")


@pytest.fixture()
def anon_client():
    """未登录的测试客户端（只建空库，不创建用户不登录）。"""
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
    yield app_module.app.test_client()


# ---------------------------------------------------------------------------
# 行为契约：未登录伪 API 请求的头 → 状态码映射
# ---------------------------------------------------------------------------

def test_pseudo_api_returns_401_json_with_ajax_header(anon_client):
    """带 X-Requested-With 的未登录伪 API 请求 → 401 JSON（拦截器跳登录的依据）。"""
    resp = anon_client.get(
        "/warehouse/api/list",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 401, resp.status_code
    body = resp.get_json()
    assert body is not None and body.get("status") == "error", body


def test_pseudo_api_redirects_302_without_ajax_header(anon_client):
    """不带头的未登录伪 API 请求 → 302 登录页（证明缺口的真实性与头的必要性）。"""
    resp = anon_client.get("/warehouse/api/list")
    assert resp.status_code == 302, resp.status_code
    assert "/login" in (resp.headers.get("Location") or ""), resp.headers.get("Location")


def test_material_api_all_same_contract(anon_client):
    """另一伪 API（/material/api/all）遵守同一头 → 401 契约。"""
    resp = anon_client.get(
        "/material/api/all",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert resp.status_code == 401, resp.status_code
    assert (resp.get_json() or {}).get("status") == "error", resp.get_json()


# ---------------------------------------------------------------------------
# 结构断言：base.html 拦截器源码口径（pytest 无 JS 引擎，锁结构不锁实现细节）
# ---------------------------------------------------------------------------

def test_interceptor_injects_x_requested_with():
    """拦截器必须含 X-Requested-With 注入逻辑。"""
    assert "'X-Requested-With'" in BASE_HTML
    assert "XMLHttpRequest" in BASE_HTML


def test_interceptor_skips_external_urls():
    """注入只针对同源请求：必须含外部 URL 判断（避免跨域 preflight 变更）。"""
    assert "isExternal" in BASE_HTML
    assert "window.location.origin" in BASE_HTML


def test_interceptor_supports_both_header_forms():
    """Headers 实例与普通对象两种形态都必须兼容（与 CSRF 段同款双形态）。"""
    assert "init.headers instanceof Headers" in BASE_HTML
    assert "init.headers.has('X-Requested-With')" in BASE_HTML
    assert "init.headers['X-Requested-With']" in BASE_HTML


def test_interceptor_does_not_override_existing_header():
    """已有 X-Requested-With 头时不覆盖（保留调用方自定义）。"""
    assert "!init.headers.has('X-Requested-With')" in BASE_HTML
    assert "!init.headers['X-Requested-With']" in BASE_HTML


def test_interceptor_keeps_csrf_and_401_handling():
    """既有 CSRF 注入（非 GET）与 401/419 全局处理不得被破坏。"""
    assert "X-CSRFToken" in BASE_HTML
    assert "resp.status === 401 || resp.status === 419" in BASE_HTML
    assert "__wmsSessionExpiredShown" in BASE_HTML
