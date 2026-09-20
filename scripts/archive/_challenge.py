#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""挑战演示：登录 → 进入物料档案 → 新增物料 → 填表 → 提交 → 验证 DB"""
import time
import sqlite3
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/workspace/audit_screenshots/challenge")
OUT.mkdir(parents=True, exist_ok=True)

# 找数据库
db_path = None
for p in [
    "/workspace/wms.db",
    "/workspace/instance/wms.db",
    "/workspace/app/wms.db",
    "/workspace/data/wms.db",
]:
    if Path(p).exists():
        db_path = p
        break
print(f"数据库位置: {db_path}")

def get_material_count():
    if not db_path:
        return -1
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM material")
        n = cur.fetchone()[0]
        conn.close()
        return n
    except Exception as e:
        return f"err: {e}"

print(f"操作前物料总数: {get_material_count()}")
print("=" * 60)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome",
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()

    # 登录
    print("\n[1] 登录")
    page.goto("http://127.0.0.1:8080/login", wait_until="networkidle", timeout=15000)
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.locator('button[type="submit"]').first.click()
    page.wait_for_load_state("networkidle", timeout=10000)
    time.sleep(1)
    print(f"  ✓ 登录后 URL: {page.url}")
    page.screenshot(path=str(OUT / "01_home.png"))

    # 进入物料档案
    print("\n[2] 进入物料档案")
    page.goto("http://127.0.0.1:8080/material", wait_until="networkidle", timeout=10000)
    time.sleep(1)
    page.screenshot(path=str(OUT / "02_material_list.png"), full_page=True)
    print(f"  ✓ 当前 URL: {page.url}")

    # 找新增按钮
    print("\n[3] 找新增按钮")
    add_btn = page.locator('button:has-text("新增"), a:has-text("新增")').first
    btn_count = page.locator('button:has-text("新增"), a:has-text("新增")').count()
    print(f"  找到 {btn_count} 个'新增'按钮")
    if btn_count > 0:
        try:
            add_btn.click(force=True, timeout=5000)
            time.sleep(2)
            page.screenshot(path=str(OUT / "03_after_click_add.png"), full_page=True)
            print(f"  ✓ 点击后 URL: {page.url}")

            # 看页面有什么 input
            inputs = page.locator('input[type="text"], input:not([type])').all()
            print(f"  页面 input 数量: {len(inputs)}")
            for i, inp in enumerate(inputs[:10]):
                name = inp.get_attribute("name") or "(no name)"
                ph = inp.get_attribute("placeholder") or ""
                print(f"    [{i}] name={name} placeholder={ph}")

            page.screenshot(path=str(OUT / "04_form.png"), full_page=True)
        except Exception as e:
            print(f"  ✗ 点击失败: {e}")

    # 看看有没有 modal
    modal = page.locator('.modal, [role="dialog"]').count()
    print(f"\n  弹窗/modal 数量: {modal}")

    browser.close()

print("\n" + "=" * 60)
print(f"操作后物料总数: {get_material_count()}")
print("\n截图：")
for f in sorted(OUT.iterdir()):
    print(f"  {f.name} ({f.stat().st_size:,} bytes)")
