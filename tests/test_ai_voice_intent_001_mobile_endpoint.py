# -*- coding: utf-8 -*-
"""AI-VOICE-INTENT-001 回归：语音意图理解端点 /api/mobile/voice_intent。

背景：App 端 parseCommand 是 13 个 contains 对暗号，「我要领点螺丝」这类
口语永远「未识别到可执行指令」。新端点把 ASR 文本交给后端 LLM 意图路由
（复用 PC AI 助手的 _ai_call_llm_intent），返回移动端动作协议：
  - navigate：<screen_key>（App Screen 路由键）
  - reply：无页面映射的意图，执行后端意图拿 reply 文本由 App 展示/朗读
  - fallback_local：LLM 不可用/无映射，App 走本地 contains 兜底

边界：本端点只做「意图 → 动作建议」，不执行任何业务写操作。

覆盖：
V1. LLM 配置好 + 意图=query_material → action=navigate screen=stock_query
V2. LLM 配置好 + 建单意图 create_in_order_draft → navigate inbound
V3. LLM 挂掉（_ai_call_llm_intent 返回 None）→ action=fallback_local
V4. 无页面映射意图（analysis_low_stock）→ action=reply 带 speak 文本
V5. 参数空文本 → 400
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

# 沙箱坑（勿删）：guarded_drop_all/db 操作需要 app ctx 存活；
# 合规写法（A12/R7）：顶层只创建 ctx，push/pop 包在模块级 autouse fixture 内。
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
    """最小种子：admin 用户 + 一个仓库。"""
    from werkzeug.security import generate_password_hash
    from app import User, Warehouse
    db.drop_all()
    db.create_all()
    db.session.add(User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", status="normal"))
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


def _patch_intent(monkeypatch, payload):
    """替身 _ai_call_llm_intent：native_api 懒导入 from app import，
    所以要 patch app 模块属性。"""
    monkeypatch.setattr(app_module, "_ai_call_llm_intent",
                        lambda text, overrides=None: payload)


class TestVoiceIntentEndpoint:
    def test_v1_query_with_keyword_replies_instead_of_empty_jump(self, monkeypatch):
        """V1：查库存带了关键词，页面吃不下条件，回回复和卡片，不空跳。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, {"intent": "query_material",
                                    "params": {"keyword": "螺丝"}})

        def _fake_execute(text, payload, context=None):
            return app_module.jsonify({
                "reply": "螺丝库存 12",
                "cards": [{"title": "螺丝", "meta": "库存 12", "url": ""}],
            })

        monkeypatch.setattr(app_module, "_ai_execute_intent", _fake_execute)
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "螺丝还有多少"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "reply"
        assert data["intent"] == "query_material"
        assert "螺丝" in (data.get("speak") or "")
        assert data["cards"][0]["title"] == "螺丝"
        assert "screen" not in data

    def test_v1b_query_without_filter_navigates(self, monkeypatch):
        """没带物料、单号、日期时，仍只打开查库存页。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, {"intent": "query_material", "params": {}})
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "打开查库存"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "navigate"
        assert data["screen"] == "stock_query"

    def test_v2_llm_create_in_navigates_inbound(self, monkeypatch):
        """V2：建单意图 → navigate 对应页面（不直接建单，由 App 页面承接）。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, {"intent": "create_in_order_draft",
                                    "params": {}})
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "帮我做一张采购入库单"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "navigate"
        assert data["screen"] == "inbound"

    def test_v3_llm_down_falls_back_local(self, monkeypatch):
        """V3：LLM 不可用 → fallback_local，App 走本地 contains。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, None)
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "我要领点螺丝"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "fallback_local"
        assert data["reason"] == "llm_unavailable"

    def test_v4_analysis_intent_returns_reply(self, monkeypatch):
        """V4：无页面映射意图（analysis_low_stock）→ action=reply。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, {"intent": "analysis_low_stock",
                                    "params": {}})
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "给我低库存报告"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        # 库存预警未启用时 _ai_execute_intent 会返回提示文本 → reply；
        # 若执行异常则 fallback_local——两种都合法，但不允许 5xx
        assert data["action"] in ("reply", "fallback_local"), data
        if data["action"] == "reply":
            assert data.get("speak")

    def test_v5_empty_text_rejected(self):
        """V5：空文本 → 400（pydantic min_length）。"""
        client, hdr = _client()
        r = client.post("/api/mobile/voice_intent",
                        json={"text": ""}, headers=hdr)
        assert r.status_code == 400, r.get_data(as_text=True)

    def test_v6_requires_auth(self):
        """V6：未带 token → 401。"""
        client = app_module.app.test_client()
        r = client.post("/api/mobile/voice_intent", json={"text": "查库存"})
        assert r.status_code == 401, r.get_data(as_text=True)

    def test_v7_outbound_with_material_hands_off_draft(self, monkeypatch):
        """有物料的领料意图交给现有语音建单核对，服务端不在这里建单。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, {
            "intent": "create_out_order_draft",
            "params": {"keyword": "螺丝", "quantity": 10},
        })
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "领10个螺丝"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "voice_out_draft"
        assert data["text"] == "领10个螺丝"

    def test_v8_outbound_without_material_navigates(self, monkeypatch):
        """没说物料，仍然只打开出库页。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, {"intent": "create_out_order_draft", "params": {}})
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "我要出库"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "navigate"
        assert data["screen"] == "outbound"

    def test_v9_permission_denied_falls_back_local(self, monkeypatch):
        """没有知识库权限时不报 403，本地口令还能用。"""
        import ai.policies as policies
        monkeypatch.setattr(policies, "is_ai_capability_allowed_for_role", lambda *a, **k: False)
        client, hdr = _client()
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "打开查库存"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "fallback_local"
        assert data["reason"] == "permission_denied"

    def test_v10_draft_switch_off_does_not_hand_off(self, monkeypatch):
        """草稿开关关掉时，不把领料交给建单，只提示去出库页。"""
        client, hdr = _client()
        _patch_intent(monkeypatch, {
            "intent": "create_out_order_draft",
            "params": {"keyword": "螺丝"},
        })

        def _flag(name, default=True):
            if name == "ai_feature_drafts_enabled":
                return False
            return default

        monkeypatch.setattr(app_module, "_ai_feature_enabled", _flag)
        r = client.post("/api/mobile/voice_intent",
                        json={"text": "领螺丝"}, headers=hdr)
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()["data"]
        assert data["action"] == "reply"
        assert "出库" in (data.get("speak") or "")
