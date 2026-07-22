"""
用 Playwright + 已装好的 google-chrome 跑真实 WMS 登录流程。
每一步截图保存到 /workspace/.wms_preview/，启动 HTTP 服务让用户在 TRAE 预览里看到。
"""
import asyncio
import os
import sys
from playwright.async_api import async_playwright

OUT = "/workspace/.wms_preview"
os.makedirs(OUT, exist_ok=True)

# 尝试多种常用密码
PASSWORDS = ["Admin@123", "admin", "Admin123", "123456", "admin123"]


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path="/usr/bin/google-chrome",
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        ctx = await browser.new_context(viewport={"width": 1366, "height": 850})
        page = await ctx.new_page()

        results = []

        # 1. 打开登录页
        print(">> 1. GET /login", flush=True)
        resp = await page.goto("http://127.0.0.1:8080/login", wait_until="domcontentloaded", timeout=15000)
        results.append(("01_login_page", resp.status if resp else "no-resp"))
        await page.screenshot(path=f"{OUT}/01_login_page.png", full_page=True)
        print(f"   status={resp.status if resp else 'n/a'} url={page.url}", flush=True)

        # 2. 尝试登录（按顺序试密码）
        logged_in = False
        for i, pwd in enumerate(PASSWORDS, 1):
            print(f">> 2.{i}. try password '{pwd}'", flush=True)
            try:
                await page.fill('input[name="username"]', "admin")
                await page.fill('input[name="password"]', pwd)
                # 截图含表单填写后的状态
                await page.screenshot(path=f"{OUT}/02_login_filled_{i}_{pwd}.png", full_page=True)
                async with page.expect_navigation(timeout=8000) as nav_info:
                    await page.click('button[type="submit"]')
                nav = await nav_info.value
                url = page.url
                print(f"   after click: status={nav.status if nav else 'n/a'} url={url}", flush=True)
                if "/login" not in url and resp is not None:
                    results.append((f"02_login_ok_{pwd}", nav.status if nav else "?"))
                    logged_in = True
                    break
                else:
                    body = await page.content()
                    snippet = body[:300].replace("\n", " ")
                    print(f"   still on login. body={snippet}", flush=True)
            except Exception as e:
                print(f"   error: {e}", flush=True)

        if not logged_in:
            print("!! ALL PASSWORDS FAILED", flush=True)
            await page.screenshot(path=f"{OUT}/99_login_failed.png", full_page=True)
            await browser.close()
            return

        # 3. 登录后截图首页
        print(">> 3. HOME page screenshot", flush=True)
        await page.wait_for_load_state("domcontentloaded", timeout=8000)
        await asyncio.sleep(1)
        await page.screenshot(path=f"{OUT}/03_home_dashboard.png", full_page=True)
        print(f"   title={await page.title()} url={page.url}", flush=True)

        # 4. 抓取当前登录用户名（页面可见）
        try:
            user_el = await page.query_selector(".navbar, .user-info, .dropdown-toggle, header")
            if user_el:
                user_text = (await user_el.inner_text())[:200]
                results.append(("user_info_snippet", user_text.strip().replace("\n", " | ")))
        except Exception:
            pass

        # 5. 遍历主要菜单页面
        menu_pages = [
            ("/purchase/request", "04_purchase_request"),
            ("/supplier", "05_supplier_list"),
            ("/product", "06_product_list"),
            ("/warehouse", "07_warehouse_list"),
            ("/stock", "08_stock_list"),
            ("/inbound/order", "09_inbound_order"),
            ("/outbound/order", "10_outbound_order"),
            ("/ai/dashboard", "11_ai_dashboard"),
        ]
        for path, name in menu_pages:
            try:
                print(f">> visiting {path}", flush=True)
                r = await page.goto(f"http://127.0.0.1:8080{path}", wait_until="domcontentloaded", timeout=10000)
                await asyncio.sleep(0.6)
                await page.screenshot(path=f"{OUT}/{name}.png", full_page=True)
                results.append((name, r.status if r else "n/a"))
                title = await page.title()
                print(f"   {path} -> status={r.status if r else 'n/a'} title={title}", flush=True)
            except Exception as e:
                results.append((name, f"ERR:{e}"))
                print(f"   ERR {path}: {e}", flush=True)

        # 6. 写报告
        with open(f"{OUT}/REPORT.txt", "w") as f:
            f.write("WMS E2E 真实浏览器测试报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"登录密码: {pwd}\n")
            f.write(f"截图数量: {len(os.listdir(OUT))-1}\n\n")
            f.write("页面访问结果:\n")
            for name, status in results:
                f.write(f"  {name}: {status}\n")
        print(">> DONE", flush=True)
        print(f">> screenshots in {OUT}", flush=True)
        for fn in sorted(os.listdir(OUT)):
            sz = os.path.getsize(f"{OUT}/{fn}")
            print(f"   {fn}  ({sz} bytes)", flush=True)

        await browser.close()


asyncio.run(run())
