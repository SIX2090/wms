# -*- coding: utf-8 -*-
"""AI 菜单入口治理回归测试（2026-10-03，WMS-AI-MENU-001）。

背景（AI 功能实用性审计发现）：
- 巡检 Agent 6 条规则默认在跑，但结果页 /ai/agent_tasks 主导航零链接
  （与 AI-CI-GREEN-005-F03 注释自述的「/alert 全仓零链接等于白做」同型复发）；
- 菜单两处同名「补货建议（规则）」指向 /ai/replenishment 与 /ai/replenishment_smart
  两个不同页面，用户无法区分；
- 智能库位推荐依赖库位管理数据，库位管理关闭时入口无意义，应按
  location_management_enabled 条件隐藏（与 inventory_alert_enabled 同款做法）。

测试用例：
  T1. base.html 必须含指向 /ai/agent_tasks 的菜单链接（巡检报告入口）
  T2. 两个补货入口标签必须可区分：/ai/replenishment=补货建议（安全库存），
      /ai/replenishment_smart=补货建议（周转分析）（不得含「智能」字样——
      命名真实性 tests/verify_ai_naming_truthfulness.py T8 约束：规则页不得自称智能）；
      全模板不得再出现旧标签「补货建议（规则）」
  T3. /ai/location_recommendation 菜单链接必须包裹在
      {% if location_management_enabled %} 条件块内
"""
from __future__ import annotations

import re
from pathlib import Path

TPL_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"
BASE = TPL_DIR / "base.html"


def _base() -> str:
    return BASE.read_text(encoding="utf-8")


class TestAiMenuGovernance:
    def test_t1_patrol_tasks_menu_link_exists(self):
        """T1：主导航必须有 /ai/agent_tasks 入口。"""
        html = _base()
        assert 'href="/ai/agent_tasks"' in html, "base.html 缺少 /ai/agent_tasks 菜单链接（巡检结果页不可达）"

    def test_t2_replenishment_labels_distinct(self):
        """T2：两个补货入口标签必须不同且全模板无旧标签残留。"""
        html = _base()
        m1 = re.search(r'href="/ai/replenishment"[^>]*>.*?</a>', html, re.S)
        m2 = re.search(r'href="/ai/replenishment_smart"[^>]*>.*?</a>', html, re.S)
        assert m1 and m2, "base.html 两个补货入口必须都存在"
        assert "补货建议（安全库存）" in m1.group(0), f"/ai/replenishment 标签错误: {m1.group(0)}"
        assert "补货建议（周转分析）" in m2.group(0), f"/ai/replenishment_smart 标签错误: {m2.group(0)}"
        assert "智能补货" not in m2.group(0), "规则页标签不得自称智能（命名真实性约束）"
        for tpl in TPL_DIR.glob("*.html"):
            assert "补货建议（规则）" not in tpl.read_text(encoding="utf-8"), f"{tpl.name} 仍残留旧标签「补货建议（规则）」"

    def test_t3_location_recommendation_gated(self):
        """T3：智能库位推荐入口必须按 location_management_enabled 条件渲染。"""
        html = _base()
        m = re.search(
            r"\{%\s*if\s+location_management_enabled\s*%\}\s*"
            r'<a class="flyout-link" href="/ai/location_recommendation".*?</a>\s*'
            r"\{%\s*endif\s*%\}",
            html,
            re.S,
        )
        assert m, "智能库位推荐入口未包裹在 location_management_enabled 条件块内"
