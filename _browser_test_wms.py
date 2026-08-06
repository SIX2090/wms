# -*- coding: utf-8 -*-
"""用 Playwright 在真实浏览器里登录 WMS，测试领料单相关页面，捕获页面/JS/网络错误。"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18099"
pages_to_test = ["/out_order", "/requisition", "/out_order/add", "/in_order", "/in_order/add"]

errors = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("pageerror", lambda e: errors.append(f"[PAGEERROR] {e}"))
    page.on("console", lambda m: errors.append(f"[CONSOLE:{m.type}] {m.text}") if m.type == "error" else None)
    page.on("requestfailed", lambda r: errors.append(f"[REQFAILED] {r.url} {r.failure}"))

    # 登录
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill("input[name='username']", "admin")
    page.fill("input[name='password']", "admin")
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle")
    print(f"[登录] URL={page.url} TITLE={page.title()}")

    for path in pages_to_test:
        errs_before = len(errors)
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        title = page.title()
        content_txt = page.content()
        has_500 = "服务器内部错误" in content_txt or "Internal Server Error" in content_txt
        new_errors = errors[errs_before:]
        print(f"[{path}] HTTP状态不可直接读, TITLE={title!r}, 含500文案={has_500}, 新增错误数={len(new_errors)}")
        for e in new_errors:
            print(f"    {e}")
        # 截图
        try:
            page.screenshot(path=f"/workspace/qa_screenshots/pw_{path.strip('/').replace('/', '_')}.png")
        except Exception as ex:
            print(f"    [截图失败] {ex}")

    browser.close()

print("\n===== 汇总 =====")
if errors:
    print(f"共 {len(errors)} 条错误/告警:")
    seen = set()
    for e in errors:
        if e not in seen:
            seen.add(e)
            print("  " + e)
else:
    print("无任何页面/JS/网络错误")