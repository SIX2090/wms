# -*- coding: utf-8 -*-
"""AI-ASSISTANT-MOBILE-001 回归：App 端 AI 助手对话端点 /api/mobile/assistant_chat。

背景：AI 助手此前只有 PC web 入口，App 40 个端点无任何 AI 对话入口。
新端点与 PC 共用 _ai_handle_warehouse_assistant_request（意图路由/查库存/
建单草稿/分析问答全链路），并把每轮对话落 ai_conversation/ai_message。

覆盖：
V1. 查库存意图（monkeypatch _ai_call_llm_intent）→ reply 带库存卡片、cards 透传
V2. 纯文本意图（today_summary）→ reply 文本、conversation_id 非空
V3. 对话历史落库：连续两轮后 ai_message 有 4 条（2 user + 2 assistant）
V4. AI 全局关闭 → 返回「AI 功能当前已由管理员关闭」提示文本
V5. 空文本 → 400
V6. 未登录 → 401
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

import pytest  # noqa: E402

# A12/R7 合规：顶层只创建 ctx，push/pop 包在模块级 autouse fixture 内。
_ctx = app_module.app.app_context()


@pytest.fixture(autouse=True, scope="module")
def _release_app_ctx_after_module():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _seed():
    from werkzeug.security import generate_password_hash
    from app import User, Warehouse
    db.drop_all()
    db.create_all()
    db.session.add(User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", status="normal"))
    db.session.add(User(username="keeper",
                        password_hash=generate_password_hash("keeper"),
                        role="warehouse", status="normal"))
    db.session.add(Warehouse(code="WH1", name="主仓"))
    db.session.commit()


def _client():
    _seed()
    client = app_module.app.test_client()
    r = client.post("/api/login", json={"username": "admin",
                                        "password": "admin"})
    assert r.status_code == 200, r.get_data(as_text=True)
    token = r.get_json()["data"]["token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_v1_query_material_intent_returns_reply_and_cards(monkeypatch):
    """V1：查库存意图 → reply + cards 透传（PC 同款物料卡片）。"""
    monkeypatch.setattr(
        app_module, "_ai_call_llm_intent",
        lambda text, overrides=None: {"intent": "query_material",
                                      "params": {"keyword": "A001"}})
    client, headers = _client()

    # 造物料要放在 _seed 的 drop_all/create_all 之后
    from app import Material, Unit
    unit = Unit(code="ge", name="个")
    db.session.add(unit)
    db.session.flush()
    db.session.add(Material(code="A001", name="内六角螺丝", spec="M8*25",
                            stock=1000, unit_id=unit.id))
    db.session.commit()
    r = client.post("/api/mobile/assistant_chat",
                    json={"text": "A001 还有多少库存"}, headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert data["action"] == "reply"
    assert "A001" in data["reply"] or "内六角螺丝" in data["reply"]
    assert isinstance(data["cards"], list) and len(data["cards"]) >= 1
    assert data["conversation_id"]


def test_v2_today_summary_returns_text_reply(monkeypatch):
    """V2：今日概况意图 → 纯文本 reply + conversation_id。"""
    monkeypatch.setattr(
        app_module, "_ai_call_llm_intent",
        lambda text, overrides=None: {"intent": "today_summary", "params": {}})
    client, headers = _client()
    r = client.post("/api/mobile/assistant_chat",
                    json={"text": "今天概况"}, headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert data["action"] == "reply"
    assert data["reply"]
    assert data["conversation_id"]


def test_v3_history_persisted_to_ai_message(monkeypatch):
    """V3：两轮对话后 ai_message 落 4 条（user/assistant 交替）。"""
    monkeypatch.setattr(
        app_module, "_ai_call_llm_intent",
        lambda text, overrides=None: {"intent": "today_summary", "params": {}})
    client, headers = _client()
    r1 = client.post("/api/mobile/assistant_chat",
                     json={"text": "今天概况"}, headers=headers)
    conv_id_1 = r1.get_json()["data"]["conversation_id"]
    r2 = client.post("/api/mobile/assistant_chat",
                     json={"text": "今天入库了多少"}, headers=headers)
    conv_id_2 = r2.get_json()["data"]["conversation_id"]
    # 无外部会话中断 → 同一会话
    assert conv_id_1 and conv_id_2

    from app import AIConversation, AIMessage
    conv = AIConversation.query.filter(
        AIConversation.user_id.isnot(None)).first()
    assert conv is not None, "应存在 ai_conversation 记录"
    msgs = AIMessage.query.filter_by(conversation_id=conv.id).order_by(
        AIMessage.created_at.asc()).all()
    roles = [m.role for m in msgs]
    assert roles.count("user") == 2, f"应有 2 条 user 消息，实际 {roles}"
    assert roles.count("assistant") == 2, f"应有 2 条 assistant 消息，实际 {roles}"
    assert roles[0] == "user" and roles[1] == "assistant"


def test_v4_ai_disabled_returns_notice(monkeypatch):
    """V4：AI 全局关闭 → 明确提示，不 500。"""
    monkeypatch.setattr(app_module, "_ai_global_enabled", lambda: False)
    client, headers = _client()
    r = client.post("/api/mobile/assistant_chat",
                    json={"text": "今天概况"}, headers=headers)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert "管理员" in data["reply"] or "关闭" in data["reply"]


def test_v5_empty_text_rejected():
    """V5：空文本 → 400。"""
    client, headers = _client()
    r = client.post("/api/mobile/assistant_chat",
                    json={"text": "  "}, headers=headers)
    assert r.status_code == 400
    r2 = client.post("/api/mobile/assistant_chat", json={}, headers=headers)
    assert r2.status_code == 400


def test_v6_requires_auth():
    """V6：未登录 → 401。"""
    _seed()
    client = app_module.app.test_client()
    r = client.post("/api/mobile/assistant_chat",
                    json={"text": "今天概况"})
    assert r.status_code == 401
