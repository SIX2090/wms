# -*- coding: utf-8 -*-
"""BUG-2026-08-16-013 回归：AI LLM 计费端点加角色门禁。

根因：AI 路由 30+ 端点仅 @login_required 无角色门禁，只读的 viewer/user 可调用
AI 助手/流式聊天/草稿校验/调试 LLM 端点刷计费。

修复：新增 require_ai_role 白名单（admin/warehouse/purchase/production/sales），
应用于消耗 LLM 计费的端点（/api/ai/chat/stream、/api/ai/warehouse_assistant、
/api/ai/draft_check、/api/ai/v2/llm/chat、/api/ai/v2/llm/intent）。

回归：viewer/user 调 LLM 端点返回 403；warehouse/admin 正常放行（非 403）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
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
from app import User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client(role):
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(
            username=role,
            password_hash=generate_password_hash("admin"),
            role=role, must_change_password=False,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    c.post(
        "/login",
        data={"username": role, "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    return c


LLM_ENDPOINTS = [
    "/api/ai/chat/stream",
    "/api/ai/warehouse_assistant",
    "/api/ai/draft_check",
    "/api/ai/v2/llm/chat",
    "/api/ai/v2/llm/intent",
]


@pytest.mark.parametrize("endpoint", LLM_ENDPOINTS)
def test_viewer_blocked_from_llm_endpoints(endpoint):
    """viewer 角色调任何 LLM 计费端点均被 403 拦截。"""
    client = _make_client("viewer")
    resp = client.post(endpoint, json={"message": "hi", "idempotency_key": "k"})
    assert resp.status_code == 403, f"{endpoint}: {resp.get_data(as_text=True)}"
    data = resp.get_json()
    assert data.get("status") == "error", data


@pytest.mark.parametrize("endpoint", LLM_ENDPOINTS)
def test_user_blocked_from_llm_endpoints(endpoint):
    """user 角色调任何 LLM 计费端点均被 403 拦截。"""
    client = _make_client("user")
    resp = client.post(endpoint, json={"message": "hi", "idempotency_key": "k"})
    assert resp.status_code == 403, f"{endpoint}: {resp.get_data(as_text=True)}"


@pytest.mark.parametrize("endpoint", LLM_ENDPOINTS)
def test_warehouse_allowed_llm_endpoints(endpoint):
    """warehouse 角色放行（通过角色门禁，非 403）。"""
    client = _make_client("warehouse")
    resp = client.post(endpoint, json={"message": "hi", "idempotency_key": "k"})
    assert resp.status_code != 403, f"{endpoint}: {resp.get_data(as_text=True)}"


@pytest.mark.parametrize("endpoint", LLM_ENDPOINTS)
def test_admin_allowed_llm_endpoints(endpoint):
    """admin 角色放行（通过角色门禁，非 403）。"""
    client = _make_client("admin")
    resp = client.post(endpoint, json={"message": "hi", "idempotency_key": "k"})
    assert resp.status_code != 403, f"{endpoint}: {resp.get_data(as_text=True)}"


@pytest.mark.parametrize("endpoint", ["/api/ai/conversations", "/api/ai/tools"])
def test_viewer_can_access_non_llm_auxiliary(endpoint):
    """viewer 仍可访问不消耗 LLM 计费的辅助端点（对话历史/工具元数据）。"""
    client = _make_client("viewer")
    resp = client.post(endpoint, json={}) if "/conversations" in endpoint else client.get(endpoint)
    assert resp.status_code != 403, f"{endpoint}: {resp.get_data(as_text=True)}"