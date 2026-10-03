# -*- coding: utf-8 -*-
"""WMS-AI-THINK-001 回归测试：思考型模型参数适配（2026-10-03）。

背景：实测用户模型 cn:kimi-k3-1 为思考型（reasoning_content 分离）——
简单问答 reasoning 消耗 181 tokens。WMS 旧默认值在此类模型下会导致 AI 静默降级：
- _ai_call_llm_chat 的 max_tokens 上限 420 → content 被推理耗尽返回空 → 降级本地规则
- 最大输出默认 300 → 同上
- 请求超时默认 8s → 思考+视觉调用普遍超时 → 降级

修复：chat 上限 420→2000、最大输出默认 300→1500、超时默认 8s→20s（设置页可下调）。

测试用例：
  T1. _ai_call_llm_chat 的 max_tokens 上限为 2000（静态扫描，防回退）
  T2. 无配置时 _ai_llm_max_tokens()=1500、_ai_llm_timeout_seconds()=20.0（功能验证）
  T3. 系统设置页默认值与 remark 同步提示思考型模型（静态扫描）
"""
from __future__ import annotations

import os
import re
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
# 防止外部环境变量污染默认值断言
os.environ.pop("WMS_LLM_MAX_TOKENS", None)
os.environ.pop("WMS_LLM_TIMEOUT_SECONDS", None)

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True

SRC = (APP_DIR / "app.py").read_text(encoding="utf-8")


class TestThinkingModelDefaults:
    def test_t1_chat_max_tokens_cap_raised(self):
        """T1：chat 上限 2000 且不再是 420。"""
        assert "min(max(_ai_llm_max_tokens(), 120), 2000)" in SRC
        assert "min(max(_ai_llm_max_tokens(), 120), 420)" not in SRC

    def test_t2_runtime_defaults(self):
        """T2：无系统设置/环境变量时的运行时默认值。"""
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            assert app_module._ai_llm_max_tokens() == 1500
            assert app_module._ai_llm_timeout_seconds() == 20.0

    def test_t3_settings_page_defaults_synced(self):
        """T3：设置页默认显示与 remark 提示同步。"""
        assert "WMS_LLM_MAX_TOKENS', 1500)" in SRC
        assert "WMS_LLM_TIMEOUT_SECONDS', 20)" in SRC
        m = re.search(r"思考型模型（带推理过程）会额外消耗 tokens", SRC)
        assert m, "设置页 remark 缺少思考型模型提示"
        assert "通常 300 足够" not in SRC, "旧 remark 残留"
