#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-10-05-002 真实浏览器验证：iframe 嵌入页浮动按钮不得重叠。

需本地已启动 QA 服务器（127.0.0.1:8080，admin/admin）且安装 Playwright：
    pip install playwright && python -m playwright install chromium
    终端 1：python start_qa_server.py
    终端 2：python scripts/verify_bug_2026_10_05_002_embedded_duplicate_fab_browser.py

为何放 scripts/ 而非 tests/：
  Playwright 需额外下载浏览器二进制，CI（无图形环境）不适合安装。
  tests/test_bug_2026_09_23_001_test_deps_pinned.py 要求 tests/ 下所有三方
  import 必须钉入 app/requirements-test.txt —— 本脚本属"本地手动验证工具"，
  与既有 scripts/verify_ai_browser_e2e.py 同属一类，故置于 scripts/。

退出码：0=通过；1=发现重叠或断言失败；2=环境缺失（Playwright/服务不可达）。
"""
from __future__ import annotations

import sys
import urllib.request

BASE = "http://127.0.0.1:8080"


def _server_up() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/login", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


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


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] 未安装 Playwright：pip install playwright && python -m playwright install chromium")
        return 2

    if not _server_up():
        print(f"[SKIP] QA 服务器不可达（{BASE}）：请先运行 python start_qa_server.py")
        return 2

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

        bells = _visible_bells(pg)
        print("【首页】可见铃铛：", [(t, round(b['x']), round(b['y'])) for t, b in bells])

        # 叠加打开一个内容 iframe 页
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
        print("【展开 iframe 后】可见铃铛：", [(t, round(b['x']), round(b['y'])) for t, b in bells])
        browser.close()

    if len(bells) != 1:
        print(f"❌ FAIL：可见打印告警铃铛 {len(bells)} 个（期望 1）—— 嵌入页浮动按钮重复渲染未修复")
        return 1
    print("✅ PASS：全视口可见打印告警铃铛恰好 1 个，无重叠")
    return 0


if __name__ == "__main__":
    sys.exit(main())
