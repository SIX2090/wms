# -*- coding: utf-8 -*-
"""BUG-2026-09-15-005 回归：期初库存台账工具栏按钮精简修正。

用户反馈"这些工具栏很多无效或不对"（opening_stock.html 顶部工具栏 + 行工具栏）。

根因：opening_stock.html 工具栏是从单据卡片页模板套用过来的，但本页是
"期初库存台账（批量录入网格）"，不是带单号、可流转的单据——大量按钮因此
无效 / 不对 / 冗余：
- 首/上/下/末张：硬编码 disabled 且无 onclick；期初库存不在
  DOCUMENT_NAVIGATION_MODULES 可导航单据清单内，根本无可导航"单据"，
  页面又已有自己的查询结果分页——4 键永久无效；
- 智能分享：仅弹 toast 占位（BUG-2026-09-15-002 曾把文案指向 微信分享配置）；
- 导入：与"批量导入"指向完全相同的 /batch_import?type=opening_stock，重复；
- 设置：跳与本页无关的 /system_settings；
- 查找单据：跳"库存台账报表" /report/view/ledger，而非"查单据"；
- 删除：clearSelectedRows() 逻辑错乱（过滤空行 + pop 最后一行数据），
  页面无"选中"概念，与"删除"语义不符；
- 行工具栏 最近使用/存为模板/批量修改/字段设置：4 个均为 toast 占位假功能。

修复（精简 + 修正）：
- 删除无法实现的：首/上/下/末张、重复的"导入"、无关的"设置"；
- 智能分享改为指向 /wechat_share 的真实链接（title 保留"系统管理 → 微信分享"，
  兼容 BUG-2026-09-15-002 的文案断言）；
- 查找单据改为页内查询面板锚点 #opening-query-panel；
- 删除重定义为 clearEntryRows()（清空当前录入明细，confirm 防误触）；
- 行工具栏移除 4 个占位按钮与静态"选择模板"下拉。

验收点：
T1. 顶部工具栏不再含 4 个永久禁用的单据导航键（首/上/下/末张）。
T2. 「导入」不再与「批量导入」重复（batch_import?type=opening_stock 仅出现一次）。
T3. 「设置」不再跳转到与本页无关的 /system_settings。
T4. 「智能分享」为指向 /wechat_share 的真实链接（不再是 toast 占位）。
T5. 「查找单据」指向页内查询面板锚点（不再跳无关的库存台账报表）。
T6. 「删除」重定义为 clearEntryRows（不再沿用错乱的 clearSelectedRows）。
T7. 行工具栏移除 4 个 toast 占位按钮（最近使用/存为模板/批量修改/字段设置）。
T8. 查询面板具备锚点 id 供「查找单据」定位。
T9. 既有能力不受影响：新增/保存/批量导入/打印/导出/导入导出模板/
    添加物料/复制上一行/粘贴导入/刷新物料 仍在。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPENING_STOCK = ROOT / "app" / "templates" / "opening_stock.html"


def _read() -> str:
    assert OPENING_STOCK.exists(), f"模板缺失：{OPENING_STOCK}"
    return OPENING_STOCK.read_text(encoding="utf-8")


class TestOpeningStockTopToolbar:
    """顶部工具栏精简修正。"""

    def test_t1_card_nav_buttons_removed(self):
        html = _read()
        for label in ("首张", "上一张", "下一张", "末张"):
            assert label not in html, f"期初台账页无可导航单据，「{label}」永久无效，应移除"
        # 单据导航图标不应再出现（硬编码 disabled 的 4 键已删除）
        assert "bi-chevron-bar-left" not in html, "首张导航图标残留"
        assert "bi-chevron-bar-right" not in html, "末张导航图标残留"

    def test_t2_duplicate_import_button_removed(self):
        html = _read()
        count = html.count("/batch_import?type=opening_stock")
        assert count == 1, (
            f"「批量导入」与「导入」原指向同一 URL 重复，应只保留一个，当前出现 {count} 次"
        )

    def test_t3_irrelevant_settings_button_removed(self):
        html = _read()
        assert "/system_settings" not in html, (
            "「设置」跳转到与本页无关的通用系统设置，应移除"
        )

    def test_t4_smart_share_is_real_link(self):
        html = _read()
        assert 'href="/wechat_share"' in html, (
            "「智能分享」应改为指向 /wechat_share 的真实链接，不再是 toast 占位"
        )
        assert "微信定时自动分享请到" not in html, "「智能分享」仍是 toast 占位提示"
        # 按钮与兼容文案仍在（BUG-2026-09-15-002 断言依赖）
        assert "智能分享" in html, "「智能分享」按钮不应被移除"
        assert "系统管理 → 微信分享" in html, "应保留「系统管理 → 微信分享」指向文案"

    def test_t5_find_document_points_to_query_panel(self):
        html = _read()
        assert "/report/view/ledger" not in html, (
            "「查找单据」不应再跳无关的库存台账报表"
        )
        assert 'href="#opening-query-panel"' in html, (
            "「查找单据」应指向页内查询面板锚点 #opening-query-panel"
        )

    def test_t6_delete_redefined_as_clear_entry_rows(self):
        html = _read()
        assert "clearSelectedRows" not in html, (
            "错乱的 clearSelectedRows()（过滤空行+pop 最后一行）应被替换"
        )
        assert "function clearEntryRows()" in html, "应定义 clearEntryRows() 清空当前录入明细"
        assert "onclick=\"clearEntryRows()\"" in html, "「删除」按钮应绑定 clearEntryRows()"

    def test_t8_query_panel_has_anchor_id(self):
        html = _read()
        assert 'id="opening-query-panel"' in html, (
            "查询面板应具备 id=\"opening-query-panel\" 供「查找单据」锚点定位"
        )


class TestOpeningStockLineToolbar:
    """行工具栏占位按钮清理。"""

    def test_t7_placeholder_buttons_removed(self):
        html = _read()
        for label in ("最近使用", "存为模板", "批量修改", "字段设置", "选择模板"):
            assert label not in html, f"行工具栏占位假功能「{label}」应移除"


class TestOpeningStockToolbarKeepsWorkingButtons:
    """既有有效按钮不受影响。"""

    def test_t9_working_buttons_kept(self):
        html = _read()
        for snippet in (
            "resetDocument()",                 # 新增
            "saveDocument()",                  # 保存
            "/batch_import?type=opening_stock",  # 批量导入
            "window.print()",                  # 打印
            "exportRows()",                    # 导出
            "/opening_stock/import/template",  # 导入导出模板
            "addRow()",                        # 添加物料
            "copyPreviousRow()",               # 复制上一行
            "pasteImport()",                   # 粘贴导入
            "pasteImportModal",                # 粘贴导入 modal
        ):
            assert snippet in html, f"既有有效能力缺失：{snippet}"
