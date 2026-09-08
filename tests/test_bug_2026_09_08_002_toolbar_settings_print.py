# -*- coding: utf-8 -*-
"""BUG-2026-09-08-002 回归：物料管理页全局工具栏「设置没反应、打印是网页残渣」。

两个根因：
  A. 设置秒关——openSettings 同步点击页面「列设置」按钮把面板打开后，
     用户的原始点击事件继续冒泡到 document，触发页面「点击面板外部关闭」
     监听，面板在同一次点击内被立即关掉（Playwright 实证：点全局设置后
     panel.show=False，直接点页面列设置按钮 panel.show=True）。
  B. 打印裸打网页——物料模块未配 printListUrl/detailPrintUrl，printCurrent
     兜底 window.print() 原样输出整张页面（分类树/搜索框/列设置面板/弹窗
     全部上纸，Playwright+pdftotext 实证）。

修复：
  A. app.js openSettings 委托点击前 stopPropagation（全模块通用，同类面板
     「点外部关闭」交互均受益）；物料页打印专属样式（只输出物料表格本体，
     解除祖先滚动/裁剪、单元格放开换行防长名称被裁）；
  B. custom.css 全局打印规则追加隐藏 .cb-actionbar/.modal/.dropdown-menu
     （所有列表页 window.print() 兜底不再把工具栏/弹窗/下拉面板打上纸）。

测试用例：
  T1. app.js 契约：openSettings 接收事件并在 btn.click() 前 stopPropagation；
      全局工具栏 settings 按钮把事件对象传入 openSettings
  T2. material.html 契约：打印样式隐藏功能区、解除裁剪、放开单元格换行、
      勾选列/排序图标/拖拽手柄不上纸
  T3. custom.css 契约：打印隐藏 .cb-actionbar/.modal/.dropdown-menu
  T4. app.js 全文件 node --check 语法校验
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "js" / "app.js"
MATERIAL_HTML = ROOT / "app" / "templates" / "material.html"
CUSTOM_CSS = ROOT / "app" / "static" / "css" / "custom.css"


def test_open_settings_stops_propagation_before_delegate_click():
    src = APP_JS.read_text(encoding="utf-8")
    fn_start = src.index("function openSettings(module, evt)")
    fn_body = src[fn_start:fn_start + 1200]
    # 必须在委托点击页面按钮之前阻止冒泡，否则面板被同一次点击秒关
    assert fn_body.index("stopPropagation") < fn_body.index("btn.click()")
    assert "evt.stopPropagation" in fn_body
    # 全局工具栏 settings 按钮必须把事件对象传进来
    assert "action: function(e) { openSettings(module, e); }" in src


def test_material_print_css_outputs_table_only():
    src = MATERIAL_HTML.read_text(encoding="utf-8")
    assert "BUG-2026-09-08-002" in src
    assert "@media print" in src
    # 功能区隐藏
    for selector in (".cb-actionbar", ".page-header", ".card.mb-3",
                     ".material-category-panel", ".modal",
                     ".material-col-settings-panel"):
        assert selector in src, f"打印隐藏缺失: {selector}"
    # 解除祖先滚动/裁剪（长表只打第一屏的根因）
    assert "overflow: visible !important;" in src
    assert "max-height: none !important;" in src
    # 单元格放开换行防长名称被裁
    assert "white-space: normal !important;" in src
    assert "text-overflow: clip !important;" in src
    # 勾选列/排序图标/拖拽手柄不上纸
    assert '#materialTable th[data-column-key="select"]' in src
    assert "#materialTable .sortable-header::after" in src


def test_global_print_css_hides_chrome():
    src = CUSTOM_CSS.read_text(encoding="utf-8")
    print_block_start = src.index("/* ==================== 打印优化")
    print_block = src[print_block_start:print_block_start + 900]
    for selector in (".cb-actionbar", ".modal", ".dropdown-menu"):
        assert selector in print_block, f"全局打印隐藏缺失: {selector}"


def test_app_js_syntax_ok():
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node 不可用")
    result = subprocess.run([node, "--check", str(APP_JS)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[:500]
