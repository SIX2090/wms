# -*- coding: utf-8 -*-
"""WMS-AI-GATE-001 / WMS-AI-DEGRADE-001 回归测试（2026-10-03）。

背景（AI 功能实用性审计发现）：
- 需求预测/智能库位推荐/智能补货建议/库存健康度/供应商评估 5 个统计型端点
  被 `if not _ai_llm_configured(): return api_error('请先在系统设置中配置大模型API')`
  硬门禁误锁——统计计算本身不需要大模型，且各端点尾部本就有
  `ai_analysis or 'AI分析暂不可用…'` 降级文案；未配置 LLM 时整个功能报废。
  修复：移除硬门禁，仅保留 _ai_capability_allowed 能力门禁（防刷计费）。
- AI 浮窗此前在大模型未配置时静默降级本地规则，用户无感知。
  修复：上下文处理器注入 ai_llm_active，浮窗标题栏显示「本地规则模式」徽章。

测试用例：
  T1. app.py 中统计型端点不再含「请先在系统设置中配置大模型API」硬门禁
  T2. base.html 浮窗含按 ai_llm_active 条件渲染的「本地规则模式」徽章
  T3. 功能验证：未配置 LLM 时 /api/ai/inventory_health 与 /api/ai/demand_forecast
      返回 success + 降级文案（而非配置错误）
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
APP_PY = APP_DIR / "app.py"

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


class TestAiLlmGateRemoval:
    def test_t1_no_hard_llm_gate_in_stats_endpoints(self):
        """T1：统计型端点的「请先配置大模型」硬门禁必须清零。"""
        src = APP_PY.read_text(encoding="utf-8")
        assert "请先在系统设置中配置大模型API" not in src, (
            "统计型端点仍存在 _ai_llm_configured 硬门禁（WMS-AI-GATE-001 回退）"
        )
        # 能力门禁（防刷计费）必须保留
        for cap in ("demand_forecast", "location_recommendation", "supplier_evaluation"):
            assert f"_ai_capability_allowed('{cap}')" in src, f"能力门禁 {cap} 被误删"

    def test_t2_float_window_local_rules_badge(self):
        """T2：浮窗徽章按 not ai_llm_active 条件渲染。"""
        html = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8")
        m = re.search(
            r"\{%\s*if\s+not\s+ai_llm_active\s*%\}.*?本地规则模式.*?\{%\s*endif\s*%\}",
            html,
            re.S,
        )
        assert m, "base.html 浮窗缺少按 ai_llm_active 条件渲染的「本地规则模式」徽章"
        src = APP_PY.read_text(encoding="utf-8")
        assert "'ai_llm_active': _ai_llm_configured()" in src, "上下文处理器未注入 ai_llm_active"

    def test_t3_stats_endpoints_work_without_llm(self):
        """T3：未配置 LLM 时统计端点返回 success + 降级文案。"""
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
            db.session.commit()
            # 确保无任何 LLM 配置（测试环境默认即未配置，显式兜底）
            assert not app_module._ai_llm_configured()

        c = app_module.app.test_client()
        c.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            content_type="application/x-www-form-urlencoded",
        )

        for url in ("/api/ai/inventory_health", "/api/ai/demand_forecast"):
            resp = c.post(url, json={})
            body = resp.get_json(silent=True) or {}
            assert resp.status_code == 200, f"{url} 应 200，实际 {resp.status_code}: {body}"
            assert body.get("status") == "success", f"{url} 应 success: {body}"
            assert "请先在系统设置中配置大模型API" not in str(body), f"{url} 仍被硬门禁拦截"
