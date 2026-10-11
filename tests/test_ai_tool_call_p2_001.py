# -*- coding: utf-8 -*-
"""FIX-2026-10-11 P2：Tool Calling 调度层（失败注入测试）。

要求：
1. validate_tool_call：合法调用通过；非法 JSON / 未知工具 / 缺必填参数 /
   参数类型错误被拒绝
2. 调度层：LLM 输出 tool=none 或非法输出时返回 None（落回原链路）
3. 调度层：合法调用路由到正确 handler，message 带结构化条件
4. LLM 不可用时返回 None，机械回退不受影响

独立模式：内存库 + 打桩。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

import pytest  # noqa: E402

_ctx = app_module.app.app_context()


@pytest.fixture(autouse=True, scope="module")
def _push_ctx():
    _ctx.push()
    yield
    _ctx.pop()

from ai.query_tools import AI_QUERY_TOOLS, validate_tool_call, build_tool_call_prompt  # noqa: E402


class TestValidateToolCall:
    def test_valid_stock_call(self):
        tool, params = validate_tool_call({"tool": "query_stock", "params": {"material_name": "铜排"}})
        assert tool == "query_stock"
        assert params["material_name"] == "铜排"

    def test_valid_flow_call_with_optional(self):
        tool, params = validate_tool_call({
            "tool": "query_flow",
            "params": {"material_name": "铜排", "time_range": "最近7天"},
        })
        assert tool == "query_flow"
        assert params["time_range"] == "最近7天"

    def test_reject_non_dict(self):
        tool, err = validate_tool_call("not a dict")
        assert tool is None and err

    def test_reject_unknown_tool(self):
        tool, err = validate_tool_call({"tool": "delete_everything", "params": {}})
        assert tool is None and "未知工具" in err

    def test_reject_missing_required(self):
        tool, err = validate_tool_call({"tool": "query_stock", "params": {"spec": "6*10"}})
        assert tool is None and "必填" in err

    def test_reject_bad_qty_type(self):
        tool, err = validate_tool_call({
            "tool": "check_sufficiency",
            "params": {"material_name": "铜排", "required_qty": "很多"},
        })
        assert tool is None and "类型" in err

    def test_accept_numeric_qty(self):
        tool, params = validate_tool_call({
            "tool": "check_sufficiency",
            "params": {"material_name": "铜排", "required_qty": 50},
        })
        assert tool == "check_sufficiency"

    def test_registry_readonly(self):
        """注册表只含查询类工具（只读边界）。"""
        assert set(AI_QUERY_TOOLS) == {"query_stock", "query_flow", "check_sufficiency"}

    def test_prompt_contains_tools_and_schema(self):
        prompt = build_tool_call_prompt("铜排库存")
        assert "query_stock" in prompt and "query_flow" in prompt
        assert "material" in prompt  # Schema 摘要已注入


class TestDispatchLayer:
    def _run(self, llm_reply, message="铜排库存还有多少"):
        captured = {}

        def fake_llm(prompt, force_model=None):
            captured["prompt"] = prompt
            return llm_reply

        handler_calls = []

        def fake_handler(msg, context=None):
            handler_calls.append(msg)
            return MagicMock(get_json=lambda: {"reply": "ok", "status": "success"})

        with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
             patch.object(app_module, "_voice_llm_chat", side_effect=fake_llm), \
             patch.object(app_module, "_ai_stock_query_response", side_effect=fake_handler):
            resp = app_module._ai_tool_call_dispatch_response(message)
        return resp, handler_calls

    def test_none_tool_returns_none(self):
        resp, _ = self._run('{"tool": "none"}')
        assert resp is None

    def test_invalid_json_returns_none(self):
        resp, _ = self._run("这不是JSON")
        assert resp is None

    def test_unknown_tool_returns_none(self):
        resp, _ = self._run('{"tool": "hack", "params": {}}')
        assert resp is None

    def test_valid_call_routes_to_handler(self):
        resp, calls = self._run('{"tool": "query_stock", "params": {"material_name": "铜排", "spec": "6*10"}}')
        assert resp is not None
        assert len(calls) == 1
        # enriched message 带结构化条件
        assert "物料：铜排" in calls[0]
        assert "规格：6*10" in calls[0]
        assert "铜排库存还有多少" in calls[0]

    def test_llm_unavailable_returns_none(self):
        with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
             patch.object(app_module, "_voice_llm_chat", return_value=None):
            assert app_module._ai_tool_call_dispatch_response("铜排库存还有多少") is None

    def test_short_message_skipped(self):
        ctx = app_module.app.test_request_context('/assistant/chat', method='POST')
        ctx.push()
        try:
            with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
                 patch.object(app_module, "_voice_llm_chat") as m:
                assert app_module._ai_tool_call_dispatch_response("好") is None
                m.assert_not_called()
        finally:
            ctx.pop()

    def test_warehouse_insights_chain_intact(self):
        """链路顺序：调度层在最前，返回 None 时落回原 handler。"""
        with patch.object(app_module, "_ai_tool_call_dispatch_response", return_value=None) as mock_disp, \
             patch.object(app_module, "_ai_stock_query_response", return_value="STOCK_RESP") as mock_stock:
            resp = app_module._ai_warehouse_insights_response("铜排库存还有多少")
        mock_disp.assert_called_once()
        mock_stock.assert_called()
        assert resp == "STOCK_RESP"
