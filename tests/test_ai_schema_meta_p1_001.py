# -*- coding: utf-8 -*-
"""FIX-2026-10-11 P1：Schema 元数据注入 LLM 提示词（失败注入测试）。

依据调研报告：为 LLM 提供表结构/字段语义/查询模式，准确率 +30%。
要求三个 LLM 调用点（库存意图解析、库存回复生成、流水回复生成）的
prompt 都包含 Schema 摘要；机械回退路径不受影响。

独立模式：内存库 + 打桩，不依赖真实库。
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

from ai.schema_meta import get_schema_meta, MATERIAL_SCHEMA, STOCK_TRANSACTION_SCHEMA  # noqa: E402


@pytest.fixture(scope="module")
def seeded_db():
    db.drop_all()
    db.create_all()
    from models.master_data import Material, Unit

    unit = Unit(name="条", code="T")
    db.session.add(unit)
    db.session.flush()
    m = Material(code="LPY0001", name="铜排", spec="140*6", unit_id=unit.id, stock=10.0)
    db.session.add(m)
    db.session.commit()
    yield
    db.session.remove()
    db.drop_all()


class TestSchemaMetaModule:
    """schema_meta 模块本身的行为。"""

    def test_stock_meta_contains_key_fields(self):
        meta = get_schema_meta("stock")
        assert "material" in meta
        assert "reorder_point" in meta  # 安全库存列名约定必须写对
        assert "6*10" in meta  # 规格边界示例

    def test_flow_meta_contains_transaction_semantics(self):
        meta = get_schema_meta("flow")
        assert "stock_transaction" in meta
        assert "transaction_type" in meta

    def test_unknown_type_returns_all(self):
        meta = get_schema_meta("nonexistent")
        assert MATERIAL_SCHEMA in meta and STOCK_TRANSACTION_SCHEMA in meta


class TestSchemaInjection:
    """三个 LLM 调用点的 prompt 必须包含 Schema 摘要。"""

    def test_stock_intent_prompt_contains_schema(self, seeded_db):
        captured = {}

        def fake_llm(prompt, force_model=None):
            captured["prompt"] = prompt
            return '{"name": "铜排", "color": null, "spec": null, "brand": null}'

        with patch.object(app_module, "_voice_llm_chat", side_effect=fake_llm):
            result = app_module._ai_llm_parse_stock_intent("铜排库存还有多少")
        assert result is not None and result["name"] == "铜排"
        assert "reorder_point" in captured["prompt"]
        assert "【系统数据说明】" in captured["prompt"]

    def test_stock_reply_prompt_contains_schema(self, seeded_db):
        captured = {}

        def fake_llm(prompt, force_model=None):
            captured["prompt"] = prompt
            return "铜排库存充足。"

        material_info = {
            "code": "LPY0001", "name": "铜排", "spec": "140*6", "unit": "条",
            "current_stock": 10.0, "warehouse": "默认仓", "category": "电气",
            "supplier": "", "min_stock": None, "safety_stock": None,
        }
        with patch.object(app_module, "_voice_llm_chat", side_effect=fake_llm):
            prompt = app_module._build_stock_query_llm_prompt("铜排够不够用", material_info, None)
        assert "【系统数据说明】" in prompt
        assert "reorder_point" in prompt
        # 用户问题与实时数据段仍然保留
        assert "铜排够不够用" in prompt
        assert "10.0" in prompt

    def test_mechanical_fallback_unaffected(self, seeded_db):
        """机械回退（LLM 不可用）行为不变：仍输出够/不够结论。"""
        mock_wh = MagicMock()
        mock_wh.name = "默认仓"
        ctx = app_module.app.test_request_context('/assistant/chat', method='POST')
        ctx.push()
        try:
            with patch.object(app_module, "_voice_llm_chat", return_value=None):
                with patch.object(app_module, "_ai_llm_parse_stock_intent", return_value=None):
                    with patch.object(app_module, "_ai_capability_allowed", return_value=True):
                        with patch.object(app_module, "get_default_warehouse", return_value=mock_wh):
                            with patch.object(app_module, "get_warehouse_stock_quantities", return_value={1: 5.0}):
                                resp = app_module._ai_stock_query_response("铜排库存还有多少")
        finally:
            ctx.pop()
        assert resp is not None
        payload = resp.get_json() if hasattr(resp, "get_json") else resp
        text = str(payload)
        assert "铜排" in text and "LPY0001" in text
