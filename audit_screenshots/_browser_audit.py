# -*- coding: utf-8 -*-
"""Playwright 浏览器审计: 登录UI、JS控制台错误、关键页面截图留证。"""
import sys, io, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
SHOTS = r"c:\Users\Administrator\Desktop\wms\audit_screenshots"
PAGES = [
    ("/", "home"), ("/material", "material"), ("/in_order", "in_order"),
    ("/in_order/add", "in_order_add"), ("/stock_query", "stock_query"),
    ("/sales", "sales"), ("/out_order", "out_order"), ("/report", "report"),
    ("/ai/warehouse_workbench", "ai_warehouse"), ("/ai/replenishment_live", "ai_replenishment_live"),
    ("/ai/inventory_health_live", "ai_inventory_health_live"),
    ("/admin/console", "admin_console"), ("/operation_audit", "operation_audit"),
    ("/user", "user"), ("/system_settings", "system_settings"),
]

console_errors = {}
page_errors = {}

with sync_playwright() as p:
    b = p.chromium.launch(headless=True,
        executable_path=r"C:\Users\Administrator\chrome-cft\chrome-win64\chrome.exe")
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()

    # 登录页截图
    page.goto(BASE + "/login", wait_until="load")
    page.screenshot(path=SHOTS + r"\qa_login.png")
    # 登录
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "AAAA1234")
    try:
        page.check('input[name="usage_consent"]')
    except Exception:
        pass
    page.click('button[type="submit"], .btn-primary')
    page.wait_for_load_state("load")
    time.sleep(1)
    page.screenshot(path=SHOTS + r"\qa_home_after_login.png")
    print("登录后 URL:", page.url, "标题:", page.title())

    for path, name in PAGES:
        errs = []
        def on_console(msg, errs=errs):
            if msg.type == "error":
                errs.append(msg.text[:200])
        page.on("console", on_console)
        try:
            resp = page.goto(BASE + path, wait_until="load", timeout=20000)
            time.sleep(1.2)
            status = resp.status if resp else -1
            page.screenshot(path=f"{SHOTS}\\qa_{name}.png", full_page=False)
            if errs:
                console_errors[path] = errs[:3]
            if status >= 500:
                page_errors[path] = status
            print(f"{path} -> {status} console_errors={len(errs)}")
        except Exception as e:
            page_errors[path] = str(e)[:150]
            print(f"{path} -> EXC {str(e)[:120]}")
        page.remove_listener("console", on_console)

    b.close()

print("\n===== 浏览器审计汇总 =====")
print("HTTP>=500:", json.dumps(page_errors, ensure_ascii=False))
print("JS控制台错误:")
for k, v in console_errors.items():
    print(f"  {k}:")
    for e in v:
        print(f"    - {e}")
