#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整演示：用 URL 直接导航 + 截图"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/workspace/audit_screenshots/full_demo2")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # 登录
    page.goto("http://127.0.0.1:8080/login", wait_until="networkidle", timeout=15000)
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.locator('button[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=10000)
    time.sleep(1)
    print("✓ 登录成功")

    # 用 URL 直接访问各模块
    pages_to_visit = [
        ("/material", "物料档案"),
        ("/category", "物料分类"),
        ("/unit", "计量单位"),
        ("/supplier", "供应商管理"),
        ("/warehouse", "仓库档案"),
        ("/in_order", "入库单"),
        ("/out_order", "出库单"),
        ("/report", "报表中心"),
    ]

    for i, (path, name) in enumerate(pages_to_visit, 1):
        url = f"http://127.0.0.1:8080{path}"
        print(f"\n[步骤 {i}] 访问 {name}: {url}")
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=10000)
            time.sleep(0.5)
            status = resp.status if resp else 0
            title = page.title()
            shot = OUT / f"{i:02d}_{path.strip('/').replace('/', '_')}.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"  ✓ HTTP {status} | {title} | 截图 {shot.name}")
        except Exception as e:
            print(f"  ✗ 失败: {e}")

    browser.close()
    print("\n\n全部完成。")
