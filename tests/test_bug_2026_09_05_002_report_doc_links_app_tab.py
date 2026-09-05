# -*- coding: utf-8 -*-
"""BUG-2026-09-05-002 回归测试：报表单据链接在应用内新标签页打开，报表页保持不动。

需求（2026-09-05，用户实测反馈）：从「库存台账」点单据编号（如 IN26080009）进入
入库单详情时，库存台账页面不要有任何变化——筛选条件、查询结果、页码原样保留。
BUG-2026-08-25-002 曾统一改为 target="_blank" 新浏览器标签页兜底：原报表页虽
不被替换，但会跳出应用标签工作区、整壳重载，体验割裂。

修复：app/templates/report_view.html（库存台账 / 入库明细 / 领料明细 / 盘点 /
采购明细 / 委外 / 工单领料等全部通用报表共用此模板）新增 bindReportDocLinks()——
报表页运行在标签工作区 iframe 中（父窗口存在 WmsTabs）时，拦截单据链接点击，
改用 window.parent.WmsTabs.open 在应用标签栏新开标签页；
Ctrl/Cmd/Shift+点击或独立浏览器打开时仍按 target="_blank" 新开浏览器标签页
（BUG-2026-08-25-002 兜底行为保留，锚点 target/rel 属性不得移除）。

测试用例：
  T1. 单据链接锚点仍带 target="_blank" + rel="noopener"（兜底行为不回退）
  T2. 定义 bindReportDocLinks 且使用 window.parent.WmsTabs.open，
      并在 renderTable 渲染后调用
  T3. Ctrl/Cmd/Shift+点击放行默认 _blank（event.preventDefault 不执行）
  T4. 链接渲染带 data-doc-title（应用内标签页命名，如「入库单 IN26080009」）
"""
from __future__ import annotations

import re
from pathlib import Path

TPL = (
    Path(__file__).resolve().parent.parent
    / "app" / "templates" / "report_view.html"
).read_text(encoding="utf-8")


def test_t1_blank_fallback_retained():
    """单据链接锚点必须保留 target=_blank + rel=noopener 兜底。"""
    m = re.search(r'<a class="report-doc-link"[^>]*>', TPL)
    assert m, "report_view.html 未找到 report-doc-link 锚点"
    tag = m.group(0)
    assert 'target="_blank"' in tag, f"锚点缺 target=_blank 兜底：{tag}"
    assert 'rel="noopener"' in tag, f"锚点缺 rel=noopener：{tag}"


def test_t2_bind_report_doc_links_uses_wms_tabs():
    """必须定义 bindReportDocLinks，走 window.parent.WmsTabs.open，且渲染后调用。"""
    assert "function bindReportDocLinks()" in TPL, "缺少 bindReportDocLinks 定义"
    assert "window.parent.WmsTabs" in TPL, "未检测父窗口 WmsTabs（应用标签工作区）"
    assert "parentTabs.open(href, title)" in TPL, "未改用应用内标签页打开"
    # 必须在 renderTable 渲染完成后绑定（表格为 innerHTML 动态渲染，需每次渲染后接管）
    render = re.search(
        r"tableBody\.innerHTML = html;(?P<body>.*?)applyReportFieldSettings\(\);",
        TPL,
        re.S,
    )
    assert render, "renderTable 中未找到 innerHTML 渲染与字段设置调用序列"
    assert "bindReportDocLinks();" in render.group("body"), (
        "renderTable 渲染后未调用 bindReportDocLinks"
    )


def test_t3_modifier_keys_keep_blank_default():
    """Ctrl/Cmd/Shift+点击必须放行默认 _blank（用户显式要新浏览器标签页）。"""
    fn = re.search(
        r"function bindReportDocLinks\(\).*?\n}\n", TPL, re.S
    )
    assert fn, "未提取到 bindReportDocLinks 函数体"
    body = fn.group(0)
    assert "event.ctrlKey" in body and "event.metaKey" in body and "event.shiftKey" in body, (
        "修饰键放行逻辑缺失"
    )
    # preventDefault 只能出现在修饰键判断之后
    assert body.index("event.ctrlKey") < body.index("event.preventDefault()"), (
        "preventDefault 先于修饰键判断，会拦截 Ctrl+点击"
    )


def test_t4_doc_title_for_app_tab():
    """链接渲染必须带 data-doc-title，供应用内标签页命名。"""
    assert "data-doc-title=" in TPL, "锚点缺 data-doc-title（应用标签页命名依据）"
    # 台账行优先用单据类型标签（入库单/领料单等），其他报表回退列标题
    assert "row.reference_type" in TPL and "column.title" in TPL, (
        "doc-title 取值逻辑（reference_type 优先 / column.title 兜底）缺失"
    )
