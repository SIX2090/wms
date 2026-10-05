#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-10-05-002 真实浏览器验证：iframe 嵌入页浮动按钮不得重叠。

需本地已启动 QA 服务器（127.0.0.1:8080，admin/admin）且安装 Playwright。
无 Playwright 或服务不可达时自动 skip，不阻塞 CI。

运行：
    # 终端 1
    python start_qa_server.py
    # 终端 2
    python -m pytest tests/verify_bug_2026_10_05_002_embedded_duplicate_fab_browser.py -v
"""

from __future__ import annotations

import pytest

try:
    from playwright.sync_api import sync_playwright  # noqa: F401
    HAS_PW = True
except Exception:
    HAS_PW = False

BASE = "http://127.0.0.1:8080"


def _server_up() -> bool:
    import urllib.request
    try:
        with urllib.request.urlopen(f"{BASE}/login", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not HAS_PW or not _server_up(),
    reason="需 Playwright 且本地 QA 服务器(127.0.0.1:8080)运行中",
)


def _visible_bells(page):
    out = []
    for b in page.query_selector_all(".print-alert-bell"):
        box = b.bounding_box()
        if box and b.is_visible():
            out.append(("outer", box))
    for fr in page.frames[1:]:
        try:
            for b in fr.query_selector_all(".print-alert-bell"):
                box = b.bounding_box()
                if box and b.is_visible():
                    out.append(("iframe", box))
        except Exception:
            pass
    return out


def test_only_one_visible_print_alert_bell_after_iframe_open():
    """真实浏览器：外层 + iframe 全部可见铃铛必须恰好 1 个。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        pg = ctx.new_page()
        pg.goto(f"{BASE}/login", wait_until="domcontentloaded")
        pg.fill('input[name="username"]', "admin")
        pg.fill('input[name="password"]', "admin")
        pg.click('button[type="submit"]')
        pg.wait_for_load_state("networkidle")
        pg.wait_for_timeout(2500)

        # 首页（默认已内嵌 iframe 首页）
        bells = _visible_bells(pg)
        assert len(bells) == 1, (
            f"首页可见铃铛 {len(bells)} 个（期望 1）："
            + str([(t, round(b['x']), round(b['y'])) for t, b in bells])
        )

        # 叠加打开一个内容页 iframe
        pg.evaluate(
            """() => {
                const wrap = document.getElementById('tabFrameWrap');
                if (wrap) {
                    const f = document.createElement('iframe');
                    f.className = 'tab-frame';
                    f.src = '/out_order?embedded=1';
                    f.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;border:0;';
                    wrap.appendChild(f);
                }
            }"""
        )
        pg.wait_for_timeout(3000)
        bells = _visible_bells(pg)
        assert len(bells) == 1, (
            f"打开 iframe 内容页后可见铃铛 {len(bells)} 个（期望 1）："
            + str([(t, round(b['x']), round(b['y'])) for t, b in bells])
        )
        browser.close()
