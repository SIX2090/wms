# -*- coding: utf-8 -*-
"""WMS-VOICE-LLM-001 回归测试：语音指令 LLM 解析（2026-10-03）。

背景：手机端语音建单此前只有正则解析（_parse_voice_out_text），对自然口语
「有点弱智」（用户原话）。大模型已配置后，新增 LLM 优先解析
（_parse_voice_out_text_llm），失败/不确定一律回退正则（R5：不猜、不编造）。

测试用例：
  T1. LLM 返回合法 JSON → 字段正确抽取，parse_source='llm'
  T2. LLM 返回垃圾/空/非法数量/缺字段 → 返回 None（回退契约）
  T3. 真实端到端提示词拼装：指令文本进入 prompt 且含关键规则约束
  T4. 未配置 LLM 时 _voice_llm_chat 返回 None（不炸、可回退）
  T5. 正则解析结果携带 parse_source='rules'；路由入口为 LLM 优先 + 正则兜底
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")


def _load_module():
    import db  # noqa: F401 —— native_api 顶部依赖
    spec = importlib.util.spec_from_file_location(
        "_na_voice_llm", ROOT / "app" / "routes" / "native_api.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()


class TestVoiceLlmParse:
    def test__parse_voice_out_text_llm(self):
        """T1：合法 LLM JSON → 同构 dict 且标记 llm。"""
        fake = lambda prompt: '{"keyword":"内六角螺丝","spec_hint":"8*25","quantity":20,"unit":"盒"}'
        r = M._parse_voice_out_text_llm("帮我领8*25的内六角螺丝20盒", chat_fn=fake)
        assert r is not None
        assert r["keyword"] == "内六角螺丝"
        assert r["spec_hint"] == "8*25"
        assert r["quantity"] == 20.0
        assert r["unit"] == "盒"
        assert r["parse_source"] == "llm"
        # 中文数字规格场景
        fake2 = lambda prompt: '{"keyword":"轴承","spec_hint":"6204","quantity":null,"unit":""}'
        r2 = M._parse_voice_out_text_llm("领6204轴承", chat_fn=fake2)
        assert r2["quantity"] is None and r2["keyword"] == "轴承"

    def test_llm_parse_fallback_contract(self):
        """T2：各类异常输出全部返回 None（回退正则，不猜）。"""
        parse = M._parse_voice_out_text_llm
        assert parse("领螺丝", chat_fn=lambda p: None) is None  # LLM 无响应
        assert parse("领螺丝", chat_fn=lambda p: "") is None  # 空内容
        assert parse("领螺丝", chat_fn=lambda p: "这不是JSON") is None  # 非 JSON
        assert parse("领螺丝", chat_fn=lambda p: '{"keyword":"","spec_hint":""}') is None  # 全空
        assert parse("领螺丝", chat_fn=lambda p: '["数组不是对象"]') is None  # 非 dict
        # 非法数量 → quantity 归 None 但保留其余字段
        r = parse("领螺丝", chat_fn=lambda p: '{"keyword":"螺丝","quantity":"abc"}')
        assert r is not None and r["quantity"] is None
        r2 = parse("领螺丝", chat_fn=lambda p: '{"keyword":"螺丝","quantity":-5}')
        assert r2 is not None and r2["quantity"] is None
        # 空指令
        assert parse("", chat_fn=lambda p: '{"keyword":"x"}') is None

    def test_llm_prompt_contains_rules(self):
        """T3：prompt 携带指令文本与防张冠李戴规则。"""
        seen = {}

        def spy(prompt):
            seen["p"] = prompt
            return None

        M._parse_voice_out_text_llm("领8*25螺丝100个", chat_fn=spy)
        assert "领8*25螺丝100个" in seen["p"]
        assert "规格里的数字" in seen["p"] and "量词" in seen["p"]

    def test__voice_llm_chat(self):
        """T4：未配置 LLM 时返回 None（走 lazy import 真实配置）。"""
        # 测试环境无任何 LLM 配置 → _ai_llm_configured() 为 False
        assert M._voice_llm_chat("测试") is None

    def test_rules_parse_source_and_wiring(self):
        """T5：正则结果标记 rules；入口为 LLM 优先 + 正则兜底。"""
        r = M._parse_voice_out_text("领8*25螺丝1000个")
        assert r["parse_source"] == "rules"
        assert r["keyword"] == "螺丝" and r["quantity"] == 1000.0  # 正则能力未退化
        src = (ROOT / "app" / "routes" / "native_api.py").read_text(encoding="utf-8")
        assert "_parse_voice_out_text_llm(req.text) or _parse_voice_out_text(req.text)" in src
