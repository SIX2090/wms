#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-10-05-002 回归守护：iframe 嵌入页不得重复渲染右下角浮动按钮。

## 缺陷（真机截图 + Playwright 真实浏览器实证）

用户截图右下角出现**两个打印告警铃铛叠在一起**（各带角标「8」），
点击任意一个都跳 `/print_alerts`。

真实浏览器（Chromium 1440x900）实测定位：
- 外层主页面任一页：`.print-alert-bell` x=1364 y=756（base.html 渲染）
- 内嵌 iframe 页 `/?embedded=1`：`.print-alert-bell` x=1349 y=741
两者仅差约 15px，48x48 圆按钮严重重叠 → 视觉上就是"两个铃铛"。

## 根因

`base.html` 的 `body.embedded-page` 隐藏规则覆盖了 `.sidebar`、
`.app-wrapper`、`.main-content`、`.tab-workspace`，**唯独遗漏了
右下角悬浮按钮**（`.print-alert-bell` / `.ai-assistant-button` /
`.ai-assistant-panel`）。iframe 内的 base.html 因而又渲染了一整套
fixed 定位的浮动按钮，与外层完全重叠。

## 修复约定（本测试锁死）

`base.html` 必须存在 `body.embedded-page` 对上述三个选择器的
`display: none !important` 隐藏规则；嵌入页浮动按钮由外层统一提供。

## 为什么是静态断言 + 真实浏览器双轨

- 静态断言：锁死 CSS 契约，CI（无浏览器）也能守住；
- 真实浏览器：本地/沙箱可跑，确认渲染后可见铃铛恰好 1 个（见
  tests/verify_bug_2026_10_05_002_embedded_duplicate_fab_browser.py，
  无 Playwright 时自动 skip）。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_HTML = REPO_ROOT / "app" / "templates" / "base.html"
BASELINE = REPO_ROOT / "WMS_BUG_BASELINE.md"

# 嵌入页必须隐藏的浮动按钮选择器
EMBED_HIDDEN_SELECTORS = [
    ".print-alert-bell",
    ".ai-assistant-button",
    ".ai-assistant-panel",
]


def _read(p: Path) -> str:
    assert p.exists(), f"文件不存在：{p}"
    return p.read_text(encoding="utf-8")


def _embedded_page_css_block(src: str) -> str:
    """截取 base.html <style> 中所有 body.embedded-page 规则段，用于精确断言。"""
    # 取每个 `body.embedded-page ... { ... }` 的完整声明块
    blocks = re.findall(
        r"body\.embedded-page[^{]*\{[^}]*\}",
        src,
        re.S,
    )
    assert blocks, "base.html 未找到任何 body.embedded-page 规则段"
    return "\n".join(blocks)


def _embedded_hidden_selectors(src: str) -> set:
    """解析所有 `body.embedded-page .xxx { display:none !important }` 命中的选择器名。

    支持合并选择器（逗号分隔的多行选择器共用同一 `{ display:none !important }` 块），
    例如：
        body.embedded-page .print-alert-bell,
        body.embedded-page .ai-assistant-button,
        body.embedded-page .ai-assistant-panel {
            display: none !important;
        }
    """
    hidden: set = set()
    # 先剥离 CSS 注释，避免注释正文里的 `body.embedded-page` 干扰选择器解析
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    # 匹配「选择器组 { 声明 }」，逐块判断声明里是否含 display:none !important
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", src, re.S):
        decls, body = m.group(1), m.group(2)
        if not re.search(r"display\s*:\s*none\s*!important", body):
            continue
        for part in decls.split(","):
            part = part.strip()
            if part.startswith("body.embedded-page"):
                # 取 .xxx 选择器名
                sel = part[len("body.embedded-page"):].strip()
                if sel:
                    hidden.add(sel)
    return hidden


def test_embedded_page_hides_print_alert_bell() -> None:
    """嵌入页必须隐藏打印告警铃铛（核心回归锁）。"""
    src = _read(BASE_HTML)
    hidden = _embedded_hidden_selectors(src)
    assert ".print-alert-bell" in hidden, (
        "base.html 缺少 `body.embedded-page .print-alert-bell { display:none !important }`——"
        "iframe 内会再渲染一个铃铛，与外层 fixed 定位重叠成「两个打印告警」"
    )


def test_embedded_page_hides_ai_assistant_button() -> None:
    """嵌入页必须隐藏 AI 助手浮动按钮与面板（同类根因，防只修一半）。"""
    src = _read(BASE_HTML)
    hidden = _embedded_hidden_selectors(src)
    for sel in (".ai-assistant-button", ".ai-assistant-panel"):
        assert sel in hidden, (
            f"base.html 缺少 `body.embedded-page {sel} {{ display:none !important }}`——"
            "AI 浮动按钮同样会在 iframe 内重复渲染并重叠"
        )


def test_embedded_hide_rule_is_grouped_with_existing_hidden_rules() -> None:
    """隐藏规则须与既有 embedded-page 隐藏规则同处（防止散落被误删）。"""
    src = _read(BASE_HTML)
    # 既有规则 .sidebar 与 .tab-workspace 必须仍存在
    assert re.search(r"body\.embedded-page\s+\.sidebar\s*\{[^}]*display\s*:\s*none", src, re.S)
    assert re.search(r"body\.embedded-page\s+\.tab-workspace\s*\{[^}]*display\s*:\s*none", src, re.S)
    # 新增的三个选择器必须出现在同一个 <style> 块内、且靠后（紧随 tab-workspace 之后）
    tw = src.find("body.embedded-page .tab-workspace")
    bell = src.find("body.embedded-page .print-alert-bell")
    assert bell > tw, "铃铛隐藏规则应紧随既有的 .tab-workspace 隐藏规则之后"


def test_outer_page_still_renders_bell_once() -> None:
    """非嵌入页（外层）仍必须渲染铃铛 —— 防止误把外部铃铛也删掉。"""
    src = _read(BASE_HTML)
    # 铃铛模板标签仍存在且仅一处
    cnt = src.count('class="print-alert-bell')
    assert cnt == 1, f"base.html 中 print-alert-bell 模板标签出现 {cnt} 次（应为 1）"
    # 不得对非嵌入页隐藏铃铛
    assert not re.search(
        r"(?<!embedded-page\s)\.print-alert-bell\s*\{[^}]*display\s*:\s*none\s*!important",
        src,
        re.S,
    ), "非嵌入页不得隐藏打印告警铃铛"


def test_bug_registered_with_confirmation_field() -> None:
    """BUG-2026-10-05-002 必须登记台账且含「生效确认」字段（A13）。"""
    content = _read(BASELINE)
    assert "BUG-2026-10-05-002" in content, "BUG-2026-10-05-002 未登记进 WMS_BUG_BASELINE.md"
    m = re.search(
        r"(##[^\n]*BUG-2026-10-05-002[^\n]*\n.*?)(?=\n##\s|\Z)",
        content,
        re.S,
    )
    assert m, "无法定位 BUG-2026-10-05-002 条目段落"
    assert "生效确认" in m.group(1), "BUG-2026-10-05-002 条目缺少「生效确认」字段（A13）"
