#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Playwright 操作浏览器登录 WMS 并截图"""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/workspace/audit_screenshots/login_demo")
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    print("[1] 打开登录页 ...")
    page.goto("http://127.0.0.1:8080/login", wait_until="networkidle", timeout=15000)
    page.screenshot(path=str(OUT / "01_login.png"), full_page=True)
    print(f"   标题: {page.title()}")
    print(f"   URL:  {page.url}")

    print("[2] 填写账号密码 ...")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.screenshot(path=str(OUT / "02_filled.png"), full_page=True)

    print("[3] 点击登录按钮 ...")
    # 找登录按钮
    btn = page.get_by_role("button", name="登录")
    if btn.count() == 0:
        btn = page.locator('button[type="submit"]')
    btn.first.click()

    print("[4] 等待跳转 ...")
    page.wait_for_load_state("networkidle", timeout=10000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "03_after_login.png"), full_page=True)
    print(f"   跳转后 URL: {page.url}")
    print(f"   跳转后标题: {page.title()}")

    # 验证是否登录成功（URL 不应再含 /login）
    login_ok = "/login" not in page.url and "/change_password" not in page.url
    print(f"[5] 登录结果: {'✅ 成功' if login_ok else '❌ 失败'}")

    # 截一张主页截图
    if login_ok:
        page.screenshot(path=str(OUT / "04_home.png"), full_page=True)

    browser.close()
    print(f"\n截图保存至: {OUT}")
    for f in sorted(OUT.iterdir()):
        size = f.stat().st_size
        print(f"  {f.name}  ({size} bytes)")
