#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整演示：登录 WMS → 点菜单 → 填表单 → 截图"""
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/workspace/audit_screenshots/full_demo")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    print("=" * 60)
    print("第 1 步：打开 WMS 登录页")
    print("=" * 60)
    page.goto("http://127.0.0.1:8080/login", wait_until="networkidle", timeout=15000)
    page.screenshot(path=str(OUT / "01_login_page.png"))
    print(f"  ✓ URL = {page.url}")
    print(f"  ✓ 标题 = {page.title()}")

    print("\n" + "=" * 60)
    print("第 2 步：自动填写 admin/admin 并点击登录")
    print("=" * 60)
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.screenshot(path=str(OUT / "02_login_filled.png"))
    page.locator('button[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=10000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "03_after_login.png"), full_page=True)
    print(f"  ✓ 跳转 URL = {page.url}")
    print(f"  ✓ 登录成功 = {'/login' not in page.url}")

    print("\n" + "=" * 60)
    print("第 3 步：点击左侧菜单 [基础资料] → [物料档案]")
    print("=" * 60)
    # 找物料档案菜单项
    material_link = page.locator('a:has-text("物料档案"), a[href*="material"]').first
    if material_link.count() > 0:
        material_link.click()
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(1)
        page.screenshot(path=str(OUT / "04_material_list.png"), full_page=True)
        print(f"  ✓ 当前 URL = {page.url}")
        print(f"  ✓ 标题 = {page.title()}")

    print("\n" + "=" * 60)
    print("第 4 步：点击 [新增物料] 按钮")
    print("=" * 60)
    add_btn = page.locator('button:has-text("新增"), a:has-text("新增")').first
    if add_btn.count() > 0:
        add_btn.click()
        page.wait_for_load_state("networkidle", timeout=10000)
        time.sleep(1)
        page.screenshot(path=str(OUT / "05_add_material_form.png"), full_page=True)
        print(f"  ✓ 当前 URL = {page.url}")
        print(f"  ✓ 标题 = {page.title()}")

        # 填表
        print("\n" + "=" * 60)
        print("第 5 步：填写物料表单（编码/名称/规格/单位）")
        print("=" * 60)
        # 尝试常见字段
        for field_name, value in [
            ("code", "DEMO-001"),
            ("name", "演示物料-轴承6204"),
            ("spec", "6204-2RS"),
            ("unit", "个"),
        ]:
            field = page.locator(f'input[name="{field_name}"], textarea[name="{field_name}"]').first
            if field.count() > 0:
                field.fill(value)
                print(f"  ✓ 填写 {field_name} = {value}")
        page.screenshot(path=str(OUT / "06_add_material_filled.png"), full_page=True)

    print("\n" + "=" * 60)
    print("完成。所有截图：")
    print("=" * 60)
    for f in sorted(OUT.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name:40s} {size:>10,} bytes")

    browser.close()
