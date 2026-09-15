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
T1. 顶部工具栏的 4 个单据导航键（首/上/下/末张）必须真实存在且绑定
    navigateOpeningDoc() 跳转——ARCH-OS-DOC-01 把期初库存变成真正的多单据
    实体后，用户要求「首 上下末功能要有」，约束由"必须移除"反转为"必须有且接通"。
T2. 「导入」不再与「批量导入」重复（batch_import?type=opening_stock 仅出现一次）。
T3. 「设置」不再跳转到与本页无关的 /system_settings。
T4. 「智能分享」为指向 /wechat_share 的真实链接（不再是 toast 占位）。
T5. 「查找单据」入口真实可达（不跳无关报表、不是永久无效按钮）。
T6. 「删除」重定义为 clearEntryRows（不再沿用错乱的 clearSelectedRows）。
T7. 行工具栏移除 4 个 toast 占位按钮（最近使用/存为模板/批量修改/字段设置）。
T8. 查询面板具备锚点 id 供定位。
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

    def test_t1_card_nav_buttons_are_real_and_wired(self):
        """ARCH-OS-DOC-01 使期初库存成为真正的多单据实体，导航键必须"有且接通"。

        本用例原先断言 4 个导航键**不存在**——那是期初库存还不是单据、导航键
        硬编码 disabled 永久无效时的正确约束。多单据化后用户明确要求
        「首 上下末功能要有」，约束随之反转为：按键存在，且必须绑定真实跳转，
        不能又变成 disabled 死按钮。
        """
        html = _read()
        for label in ("首张", "上一张", "下一张", "末张"):
            assert label in html, f"多单据化后应重新提供「{label}」导航"
        for target in ("first", "prev", "next", "last"):
            assert f"navigateOpeningDoc('{target}')" in html, (
                f"「{target}」导航键必须绑定 navigateOpeningDoc('{target}') 真实跳转"
            )
        assert "navigateOpeningDoc(" in html and "function navigateOpeningDoc(" in html, (
            "导航函数 navigateOpeningDoc 必须已定义，不能只留按钮壳"
        )
        # 不得再出现硬编码 disabled 的假导航（改造前的病症）
        assert 'data-opening-nav="first" disabled' not in html, "导航键不应是 disabled 死按钮"
        assert "disabled>首张" not in html, "导航键不应是 disabled 死按钮"

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
        """「查找单据」入口必须真实可达。

        ARCH-OS-DOC-01 后工具栏右侧改成 4 个导航键（首/上/下/末），
        原来指向 #opening-query-panel 的页内锚点链接被替换成真正的单据
        导航（后端 /api/document_navigation/opening_stock 驱动跨页跳转）。
        查询面板本身仍在，锚点 id 仍保留（T8 校验），本用例改为断言：
        既不再跳无关报表，也不再是永久无效按钮。
        """
        html = _read()
        assert "/report/view/ledger" not in html, (
            "「查找单据」不应再跳无关的库存台账报表"
        )
        assert "navigateOpeningDoc(" in html, (
            "工具栏右侧应提供真实单据导航，而不是永久无效的占位按钮"
        )

    def test_t6_delete_redefined_as_clear_entry_rows(self):
        html = _read()
        assert "clearSelectedRows" not in html, (
            "错乱的 clearSelectedRows()（过滤空行+pop 最后一行）应被替换"
        )
        assert "function clearEntryRows()" in html, "应定义 clearEntryRows() 清空当前录入明细"
        assert "onclick=\"clearEntryRows()\"" in html, "「删除」按钮应绑定 clearEntryRows()"

    def test_t8_query_panel_has_anchor_id(self):
        # BUG-2026-09-15-009 单据列表+编辑分离后：查询面板（含锚点）已从编辑器
        # opening_stock.html 迁到单据列表页 opening_stock_list.html，编辑器不再内嵌台账面板。
        editor_html = _read()
        assert 'id="opening-query-panel"' not in editor_html, (
            "编辑器（单据编辑页）不应再内嵌台账查询面板"
        )
        list_html = (ROOT / "app" / "templates" / "opening_stock_list.html").read_text(encoding="utf-8")
        assert 'id="opening-query-panel"' in list_html, (
            "查询面板锚点 id=\"opening-query-panel\" 应随面板迁到单据列表页保留"
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
