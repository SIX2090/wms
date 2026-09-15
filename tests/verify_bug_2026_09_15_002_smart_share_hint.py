# -*- coding: utf-8 -*-
"""BUG-2026-09-15-002 回归测试：智能分享提示不得指向不存在的入口。

根因（由 BUG-2026-08-05-006 的引导提示引入，R6 同根因排查）：
- in_order_add.html / out_order_add.html 的「智能分享」按钮提示
  "单据保存后可到列表页通过「智能分享」分享给协作伙伴"，
  但列表页并没有「智能分享」按钮——真正的智能分享是嵌入模式单据详情页
  全局操作栏的 smartShare()（app.js，需要具体单据 ID 生成图片）。
  用户照提示去列表页找不到任何入口，提示为误导信息。
- R6 同类点：opening_stock.html 的「智能分享」按钮提示
  "期初库存已接入库存台账和仓库月报表"，与分享功能完全无关，文不对题。

修复：
- 两个新增页提示改为指向真实能力：单据详情页「智能分享」生成图片 +
  系统管理 → 微信分享（/wechat_share）定时自动推送配置。
- 期初库存页提示改为指向 系统管理 → 微信分享 配置。

验收点：
T1. 两个新增页不再含"列表页通过「智能分享」"误导文案。
T2. 两个新增页新提示同时含「单据详情页」「智能分享」「系统管理 → 微信分享」三个要素。
T3. opening_stock.html 不再含文不对题提示，新提示指向微信分享配置。
T4. 入口真实存在：base.html 系统管理菜单确实有 /wechat_share 链接（防文案指向虚空中断）。
T5. 全模板扫描：无任何模板把智能分享入口指到"列表页"（防复发）。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "app" / "templates"

IN_ORDER_ADD = TEMPLATES_DIR / "in_order_add.html"
OUT_ORDER_ADD = TEMPLATES_DIR / "out_order_add.html"
OPENING_STOCK = TEMPLATES_DIR / "opening_stock.html"
BASE = TEMPLATES_DIR / "base.html"

MISLEADING_PHRASE = "列表页通过「智能分享」"  # 旧文案特征串：指向不存在的列表页入口
OPENING_STOCK_IRRELEVANT = "期初库存已接入库存台账和仓库月报表"  # 期初库存页文不对题提示


def _read(p: Path) -> str:
    assert p.exists(), f"模板缺失：{p}"
    return p.read_text(encoding="utf-8")


class TestSmartShareHint:
    def test_t1_misleading_phrase_removed_from_add_pages(self):
        for p in (IN_ORDER_ADD, OUT_ORDER_ADD):
            html = _read(p)
            assert MISLEADING_PHRASE not in html, (
                f"{p.name} 仍含误导文案「{MISLEADING_PHRASE}」："
                "列表页没有智能分享按钮，不得引导用户去列表页找该功能"
            )

    def test_t2_add_pages_hint_points_to_real_features(self):
        for p in (IN_ORDER_ADD, OUT_ORDER_ADD):
            html = _read(p)
            # smart-share 分支必须仍有提示（不能修成静默无反馈）
            assert "smart-share" in html, f"{p.name} smart-share 动作分支缺失"
            for element in ("单据详情页", "智能分享", "系统管理 → 微信分享"):
                assert element in html, (
                    f"{p.name} 新提示缺要素「{element}」：需同时说明详情页图片分享与微信分享配置入口"
                )

    def test_t3_opening_stock_hint_fixed(self):
        html = _read(OPENING_STOCK)
        assert OPENING_STOCK_IRRELEVANT not in html, (
            "opening_stock.html 智能分享按钮仍提示「期初库存已接入库存台账和仓库月报表」，"
            "该文案与分享功能无关（文不对题）"
        )
        # 智能分享按钮仍在，且提示指向真实入口
        assert "智能分享" in html, "opening_stock.html 智能分享按钮不应被移除"
        assert "系统管理 → 微信分享" in html, "opening_stock.html 新提示应指向 系统管理 → 微信分享"

    def test_t4_wechat_share_entry_exists_in_menu(self):
        html = _read(BASE)
        assert 'href="/wechat_share"' in html, (
            "base.html 缺少 /wechat_share 菜单入口——提示文案指向的配置页必须真实可达"
        )
        # 入口位于「系统管理」分组内（文案写的是 系统管理 → 微信分享）
        idx_flyout_title = html.find("flyout-title\">系统管理")
        idx_link = html.find('href="/wechat_share"')
        assert idx_flyout_title != -1 and idx_flyout_title < idx_link, (
            "/wechat_share 入口应位于「系统管理」菜单分组内，与提示文案一致"
        )

    def test_t5_no_template_points_smart_share_to_list_page(self):
        offenders = []
        for p in sorted(TEMPLATES_DIR.rglob("*.html")):
            text = p.read_text(encoding="utf-8")
            if MISLEADING_PHRASE in text:
                offenders.append(p.relative_to(ROOT).as_posix())
        assert not offenders, (
            f"以下模板仍把智能分享入口指到列表页（R6 同类点应一并清理）：{offenders}"
        )
