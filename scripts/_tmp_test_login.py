import sys
from playwright.sync_api import sync_playwright

CHROME = "/root/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:18082"

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, headless=True,
                                args=["--no-sandbox"])
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(f"{BASE}/login", wait_until="networkidle")
    print("LANDED:", page.url)
    try:
        page.fill("input[name=username]", "admin")
        page.fill("input[name=password]", "admin")
        page.click("#loginBtn")
    except Exception as e:
        print("FILL ERR:", e)
    page.wait_for_timeout(3000)
    print("AFTER SUBMIT URL:", page.url)
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    print("HOMEPAGE URL:", page.url)
    print("TITLE:", page.title())
    cookies = ctx.cookies()
    http_only = [(c["name"], c["value"][:20], c.get("httpOnly")) for c in cookies]
    print("COOKIE LIST:", http_only)
    browser.close()