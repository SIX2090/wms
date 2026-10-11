# -*- coding: utf-8 -*-
"""FIX-2026-10-12 P3：规则快速路径 + LLM 兜底双路并行（失败注入测试）。

要求：
1. 模式化问题（库存/够不够/流水问法）走快速路径，不调 LLM 调度层
2. 快速路径异常时兜底到 P2 调度层（不 500）
3. 非模式化问题不走快速路径，直接进 P2 调度层
4. 链路顺序：快速路径 → P2 调度 → 原 handler 链

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


_RESP = MagicMock(get_json=lambda: {"reply": "ok", "status": "success"})


class TestFastRoute:
    def _ctx_and_perm(self):
        ctx = app_module.app.test_request_context('/assistant/chat', method='POST')
        ctx.push()
        return ctx

    def test_stock_question_skips_llm_dispatch(self):
        """模式化库存问题：快速路径命中，P2 调度层 LLM 不被调用。"""
        ctx = self._ctx_and_perm()
        try:
            with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
                 patch.object(app_module, "_ai_stock_query_response", return_value=_RESP) as mock_stock, \
                 patch.object(app_module, "_ai_tool_call_dispatch_response") as mock_llm:
                resp = app_module._ai_warehouse_insights_response("6*10的铜排库存还有多少")
            mock_llm.assert_not_called()
            mock_stock.assert_called_once()
            assert resp is _RESP
        finally:
            ctx.pop()

    def test_flow_question_skips_llm_dispatch(self):
        ctx = self._ctx_and_perm()
        try:
            with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
                 patch.object(app_module, "_ai_flow_query_response", return_value=_RESP) as mock_flow, \
                 patch.object(app_module, "_ai_tool_call_dispatch_response") as mock_llm:
                resp = app_module._ai_warehouse_insights_response("最近铜排进了多少")
            mock_llm.assert_not_called()
            mock_flow.assert_called_once()
            assert resp is _RESP
        finally:
            ctx.pop()

    def test_sufficiency_question_skips_llm_dispatch(self):
        ctx = self._ctx_and_perm()
        try:
            with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
                 patch.object(app_module, "_ai_stock_query_response", return_value=_RESP) as mock_stock, \
                 patch.object(app_module, "_ai_tool_call_dispatch_response") as mock_llm:
                resp = app_module._ai_warehouse_insights_response("铜排够不够用")
            mock_llm.assert_not_called()
            mock_stock.assert_called_once()
            assert resp is _RESP
        finally:
            ctx.pop()

    def test_non_pattern_question_falls_to_llm_dispatch(self):
        """非模式化问题：快速路径未命中，走 P2 调度层。"""
        ctx = self._ctx_and_perm()
        try:
            with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
                 patch.object(app_module, "_ai_stock_query_response") as mock_stock, \
                 patch.object(app_module, "_ai_flow_query_response") as mock_flow, \
                 patch.object(app_module, "_ai_tool_call_dispatch_response", return_value=_RESP) as mock_llm:
                resp = app_module._ai_warehouse_insights_response("帮我分析一下仓库整体周转情况")
            mock_llm.assert_called_once()
            mock_stock.assert_not_called()
            mock_flow.assert_not_called()
            assert resp is _RESP
        finally:
            ctx.pop()

    def test_fast_route_exception_falls_back(self):
        """快速路径内部异常：兜底走 P2 调度层，不向上抛 500。"""
        ctx = self._ctx_and_perm()
        try:
            with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
                 patch.object(app_module, "_ai_is_flow_query_question",
                              side_effect=RuntimeError("boom")), \
                 patch.object(app_module, "_ai_tool_call_dispatch_response", return_value=_RESP) as mock_llm:
                resp = app_module._ai_warehouse_insights_response("仓库整体情况怎么样")
            mock_llm.assert_called_once()
            assert resp is _RESP
        finally:
            ctx.pop()

    def test_no_handler_match_returns_none(self):
        """三层都未命中：返回 None（落回更外层通用链路）。"""
        ctx = self._ctx_and_perm()
        try:
            with patch.object(app_module, "_ai_capability_allowed", return_value=True), \
                 patch.object(app_module, "_ai_tool_call_dispatch_response", return_value=None):
                resp = app_module._ai_warehouse_insights_response("你好呀")
            assert resp is None
        finally:
            ctx.pop()
