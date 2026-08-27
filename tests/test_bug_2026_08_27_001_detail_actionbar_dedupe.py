# -*- coding: utf-8 -*-
"""
BUG-2026-08-27-001 回归：嵌入模式下单据详情页出现两个「删除」、两个「打印」。

根因：
- `app/static/js/app.js` 的 `insertGlobalActionBar()` 在嵌入（Tab iframe）模式下
  无条件注入全局工具栏（新增/保存/删除/设置/打印/导入/导出/模板/分享）。
- 各单据详情页（领料单/入库单/采购订单/销售订单/采购申请/售后出库/委外）头部
  自带状态感知的操作按钮：草稿显示「删除」、已完成显示「反提交」、另有打印/
  发送打印。两套按钮叠加 -> 一个单据两个删除、两个打印。
- 更严重的是：已完成单据上页面只显示「反提交」，但全局工具栏仍显示通用「删除」，
  点击后必然被后端拒绝（"只有待处理的单据可以删除"），造成"反提交/删除有问题"
  的错觉。

修复（仅前端，app.js insertGlobalActionBar）：
- URL 形如 /xxx/<数字> 的详情页上，检测页面自带的删除/反提交（onclick 含
  delete/revert）与打印（onclick 含 printOrder( 或 href 以 /print 结尾）按钮；
  页面已提供对应动作时，跳过全局工具栏的重复「删除」/「打印」按钮，并清理多余
  分隔线。列表页、新增页不受影响；页面未提供对应动作的（如委外详情无打印）
  全局按钮保留。

验收点：
T1. app.js 含详情页判定（/\\d+ 结尾）与 pageHasOwnDelete/pageHasOwnPrint 检测。
T2. 检测到自带动作后过滤 delete/print 键，并清理连续/首尾分隔线。
T3. 主要单据详情模板确实自带对应按钮（删除/反提交/打印），去重后功能不缺失。
T4. base.html 侧边栏打印类导航链接均不以 "/print" 结尾（不会触发打印误判）。
T5. 详情页行级删除按钮走 class 委托（delProductBtn / data-id），不带 inline
    onclick="delete..."，不会被误判为页面级删除按钮。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "app" / "static" / "js" / "app.js"
TEMPLATES = ROOT / "app" / "templates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_t1_appjs_has_detail_page_dedupe_guard():
    js = _read(APP_JS)
    assert "BUG-2026-08-27-001" in js, "app.js 缺少本 BUG 的修复注释锚点"
    # 详情页判定：路径以 /数字 结尾
    assert re.search(r"/\\\\/\\\\d\+\(\\\\/\)\?\$/.test\(window.location.pathname\)", js) or \
        r"/\/\d+\/?$/.test(window.location.pathname)" in js, \
        "缺少详情页 URL 判定（/\\d+ 结尾）"
    assert "pageHasOwnDelete" in js and "pageHasOwnPrint" in js, \
        "缺少页面自带删除/打印动作检测"


def test_t2_appjs_filters_duplicate_buttons_and_dividers():
    js = _read(APP_JS)
    assert "item.key === 'delete' && pageHasOwnDelete" in js, "缺少全局删除按钮去重"
    assert "item.key === 'print' && pageHasOwnPrint" in js, "缺少全局打印按钮去重"
    # 分隔线清理：去掉首尾与连续分隔线
    assert "item.divider" in js and "arr[index - 1].divider" in js, \
        "缺少分隔线清理逻辑"


def test_t3_detail_templates_provide_own_actions():
    """详情页自带按钮存在，全局按钮去重后页面功能不缺失。"""
    cases = {
        # 模板: (必须含有的页面级动作特征)
        "out_order_detail.html": ('onclick="deleteOrder(', 'onclick="revertOrder(', 'onclick="printOrder()'),
        "in_order_detail.html": ('onclick="deleteOrder(', 'onclick="revertOrder(', 'onclick="printOrder()'),
        "after_sale_out_detail.html": ('onclick="deleteOrder(', 'onclick="revertOrder(', "url_for('print_after_sale_out'"),
        "purchase_order_detail.html": ('onclick="deletePurchaseOrder(', "url_for('print_purchase_order'"),
        "sales_order_detail.html": ('delete', "url_for('print_sales_order'"),
        "purchase_request_detail.html": ("url_for('print_purchase_request'",),
        "subcontract_detail.html": ('onclick="deleteOrder(',),
    }
    for tpl, markers in cases.items():
        content = _read(TEMPLATES / tpl)
        for marker in markers:
            assert marker in content, f"{tpl} 缺少页面级动作标记 {marker!r}"


def test_t4_sidebar_print_nav_not_ending_with_print():
    """侧边栏打印类导航（/print_routing 等）不以 /print 结尾，避免误触发去重。"""
    base = _read(TEMPLATES / "base.html")
    false_positive = re.findall(r'href="[^"]*/print"', base)
    assert not false_positive, \
        f"base.html 存在以 /print 结尾的导航链接，会导致打印误判: {false_positive}"


def test_t5_row_level_delete_uses_class_delegation():
    """行级（明细行）删除不带 inline onclick delete，不会误判为页面级删除。"""
    for tpl in ("out_order_detail.html", "in_order_detail.html", "subcontract_detail.html"):
        content = _read(TEMPLATES / tpl)
        for line in content.splitlines():
            if "delProductBtn" in line or "delItemBtn" in line:
                assert "onclick" not in line, \
                    f"{tpl} 行级删除按钮不应使用 inline onclick（会干扰页面级检测）: {line.strip()[:80]}"
