#!/usr/bin/env python3
"""通过 CDP 连接已启动的 Chrome，登录 WMS"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/workspace/audit_screenshots/trae_demo")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    # 连接到已启动的 Chrome 调试实例
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9223")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.new_page()

    print("[1] 打开 WMS 登录页")
    page.goto("http://127.0.0.1:8080/login", wait_until="networkidle", timeout=15000)
    page.screenshot(path=str(OUT / "01_login.png"))
    print(f"  标题: {page.title()}")

    print("[2] 填写 admin/admin")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.screenshot(path=str(OUT / "02_filled.png"))

    print("[3] 点击登录")
    page.locator('button[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=10000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "03_after_login.png"), full_page=True)
    print(f"  URL: {page.url}")
    print(f"  标题: {page.title()}")

    # 检查是否需要改密码
    if "change_password" in page.url:
        print("[!] 首次登录需要改密码")
        # 填新密码 admin@2026
        page.fill('input[name="new_password"]', "admin@2026")
        page.fill('input[name="confirm_password"]', "admin@2026")
        page.screenshot(path=str(OUT / "04_change_pwd.png"))
        page.locator('button[type="submit"]').first.click()
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(1)
        page.screenshot(path=str(OUT / "05_after_change.png"), full_page=True)
        print(f"  改密后 URL: {page.url}")

    print("[4] 截图主页")
    page.screenshot(path=str(OUT / "06_home.png"), full_page=True)

    print("\n完成！截图：")
    for f in sorted(OUT.iterdir()):
        print(f"  {f.name} ({f.stat().st_size:,} bytes)")

    browser.close()
