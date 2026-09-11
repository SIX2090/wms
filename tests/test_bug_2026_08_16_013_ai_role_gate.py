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


# ─────────────────────────────────────────────────────────────────────
# AI-LLM-GATE-002（2026-09-11）：能力门禁端点回归。
#
# 根因：BUG-2026-08-16-013 扫描不全，以下 5 个内部调 _ai_call_llm_chat 的
# 端点仅 @login_required，viewer/user 可刷 LLM 计费且灰度开关无效。
# 修复：全部加 _ai_capability_allowed 门禁（供应商评估/库位推荐/需求预测
# 新登记能力键；补货建议/库存健康复用既有页面族能力键）。
#
# 断言方式与上面 403 系不同：这批端点走 _ai_permission_denied_response
# （HTTP 200 + reply 含拒绝文案，与全库 20+ 处既有门禁端点一致）。
# 灰度默认 off 模式会连 warehouse 一起拒（非 admin 全拒），因此先切
# all 模式隔离出"角色矩阵"这一层的行为。
# ─────────────────────────────────────────────────────────────────────

CAPABILITY_GATED_ENDPOINTS = [
    "/api/ai/supplier_evaluation",
    "/api/ai/replenishment_suggestions",
    "/api/ai/inventory_health",
    "/api/ai/recommend_location",
    "/api/ai/demand_forecast",
]


def _set_rollout_mode_all():
    """灰度切 all 模式，隔离角色矩阵行为（off 模式下非 admin 全拒，无法区分角色）。"""
    with app_module.app.app_context():
        app_module.set_system_setting("ai_feature_rollout_mode", "all")
        app_module.db.session.commit()


@pytest.mark.parametrize("endpoint", CAPABILITY_GATED_ENDPOINTS)
def test_capability_gate_blocks_viewer(endpoint):
    """viewer 调能力门禁端点被拒（reply 含拒绝文案）。"""
    client = _make_client("viewer")
    _set_rollout_mode_all()
    resp = client.post(endpoint, json={})
    data = resp.get_json() or {}
    assert "当前账号没有权限" in str(data), f"{endpoint}: {resp.get_data(as_text=True)}"


@pytest.mark.parametrize("endpoint", CAPABILITY_GATED_ENDPOINTS)
def test_capability_gate_blocks_user(endpoint):
    """user 调能力门禁端点被拒。"""
    client = _make_client("user")
    _set_rollout_mode_all()
    resp = client.post(endpoint, json={})
    data = resp.get_json() or {}
    assert "当前账号没有权限" in str(data), f"{endpoint}: {resp.get_data(as_text=True)}"


@pytest.mark.parametrize("endpoint", CAPABILITY_GATED_ENDPOINTS)
def test_capability_gate_allows_warehouse(endpoint):
    """warehouse 通过能力门禁（拒绝文案消失，走到后续 LLM 配置检查 400）。"""
    client = _make_client("warehouse")
    _set_rollout_mode_all()
    resp = client.post(endpoint, json={})
    data = resp.get_json() or {}
    assert "当前账号没有权限" not in str(data), f"{endpoint}: {resp.get_data(as_text=True)}"


@pytest.mark.parametrize("endpoint", CAPABILITY_GATED_ENDPOINTS)
def test_capability_gate_allows_admin(endpoint):
    """admin 直通能力门禁。"""
    client = _make_client("admin")
    _set_rollout_mode_all()
    resp = client.post(endpoint, json={})
    data = resp.get_json() or {}
    assert "当前账号没有权限" not in str(data), f"{endpoint}: {resp.get_data(as_text=True)}"


def test_capability_gate_denies_when_rollout_off():
    """灰度 off 模式下，连 warehouse 也被拒（非 admin 全拒）——证明灰度开关真实生效。"""
    client = _make_client("warehouse")
    with app_module.app.app_context():
        app_module.set_system_setting("ai_feature_rollout_mode", "off")
        app_module.db.session.commit()
    resp = client.post("/api/ai/supplier_evaluation", json={})
    data = resp.get_json() or {}
    assert "当前账号没有权限" in str(data), resp.get_data(as_text=True)