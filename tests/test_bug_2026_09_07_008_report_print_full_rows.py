# -*- coding: utf-8 -*-
"""BUG-2026-09-07-008 回归：报表打印输出当前筛选的全部结果。

背景：报表页「打印」按钮原是 window.print() 直接打印屏幕——只含当前页
20/50/100 行，用户要打印完整查询结果只能逐页打印或导出 Excel 再打印。

修复：打印按钮先按 R1 规则（显式大 page_size + total_pages 循环）拉取当前
筛选的全部数据，渲染到屏幕隐藏的 #printArea（含报表标题、打印时间、筛选
条件、汇总、全量表格），再 window.print()；@media print 只显示打印区；
超 MAX_PRINT_ROWS(10000) 提示改用导出 Excel。

断言（模板锚点）：
  T1. #printArea 容器存在且屏幕隐藏（display:none + @media print 显示）。
  T2. 打印逻辑按 total_pages 循环拉取、page_size=500、渲染后 window.print()。
  T3. @media print 隐藏屏幕区块（reportTableSection 等），只显示打印区。
  T4. 不再存在「点击直接 window.print()」的旧绑定；无 alert 调试残留（A4）。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = (ROOT / "app" / "templates" / "report_view.html").read_text(encoding="utf-8")


class TestBug20260907008:
    def test_T1_print_area_container(self):
        assert 'id="printArea"' in TPL, "缺打印专用容器"
        assert '#printArea {' in TPL and 'display: none;' in TPL, "打印区必须屏幕隐藏"

    def test_T2_print_fetches_all_pages(self):
        assert 'MAX_PRINT_ROWS = 10000' in TPL, "缺打印行数上限保护"
        assert "params.set('page_size', '500')" in TPL, "打印必须显式大 page_size（R1）"
        assert 'while (page <= totalPages)' in TPL, "必须按 total_pages 循环拉取全部页"
        assert 'renderPrintArea(columns, allRows, truncated)' in TPL, "拉取后必须渲染打印区"
        assert 'window.print();' in TPL, "渲染后必须触发打印"
        assert '完整数据请导出 Excel' in TPL, "超上限必须提示改用导出"

    def test_T3_print_css_hides_screen_blocks(self):
        assert '#reportTableSection' in TPL, "报表区必须有 id 供打印隐藏"
        for selector in ('#filterPanel', '#summaryCards', '#reportTableSection'):
            assert selector in TPL, f"@media print 必须隐藏 {selector}"
        assert '#printArea {' in TPL and 'display: block !important;' in TPL, "打印时必须显示打印区"
        assert '筛选条件：' in TPL and '打印时间：' in TPL, "打印区必须含筛选条件与打印时间"

    def test_T4_no_legacy_direct_print_binding(self):
        old_binding = "printBtn.addEventListener('click', () => {\n    window.print();\n});"
        assert old_binding not in TPL, "旧的直接 window.print() 绑定必须移除"
        assert 'alert(' not in TPL, "A4：不得使用 alert（错误提示走页面 alert 条）"
