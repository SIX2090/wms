"""验证修复：截图两个 AI live 页面"""
from playwright.sync_api import sync_playwright
import re, urllib.request, urllib.parse, http.cookiejar
import os

BASE = 'http://127.0.0.1:8080'
OUT = r'c:\Users\Administrator\Desktop\wms\audit_screenshots'

# HTTP 登录获取 cookie
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + '/login', timeout=10).read().decode('utf-8', 'ignore')
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
op.open(BASE + '/login', data=urllib.parse.urlencode({
    'username': 'admin', 'password': 'AAAA1234', 'usage_consent': '1',
    'login_mode': 'admin', 'csrf_token': csrf
}).encode())

# 提取 cookie 字典
cookies = {c.name: c.value for c in cj if c.domain in ('127.0.0.1', '.127.0.0.1', '')}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True,
        executable_path=r'C:\Users\Administrator\chrome-cft\chrome-win64\chrome.exe')
    ctx = browser.new_context()
    ctx.add_cookies([{'name': k, 'value': v, 'domain': '127.0.0.1', 'path': '/'} for k, v in cookies.items()])

    for page_name, url_path in [('qa_fix_replenishment', '/ai/replenishment_live'),
                                 ('qa_fix_inventory_health', '/ai/inventory_health_live')]:
        page = ctx.new_page()
        js_errors = []
        page.on('pageerror', lambda err: js_errors.append(err.message))
        page.goto(BASE + url_path, timeout=15000, wait_until='networkidle')
        page.screenshot(path=os.path.join(OUT, f'{page_name}.png'), full_page=True)
        status = 'OK' if not js_errors else f'JS_ERRORS: {js_errors}'
        title = page.title()
        print(f'{url_path} -> screenshot={page_name}.png | title={title} | {status}')
        page.close()

    browser.close()

print('Done: both fix verification screenshots captured.')
