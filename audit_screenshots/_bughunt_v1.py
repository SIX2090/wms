"""
WMS 浏览器+接口深度 BUG 扫描器
目标：登录 WMS，遍历所有页面，识别尽可能多的 BUG。
"""
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://127.0.0.1:8080"
OUT_DIR = Path("/workspace/audit_screenshots/bughunt_20260729")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Findings collected
findings = []  # list of dicts
console_errors = []  # list of {page, type, text}
network_errors = []  # list of {page, status, url}


def add_finding(category, severity, page, summary, evidence=None):
    findings.append({
        "id": f"BUG-{len(findings)+1:03d}",
        "category": category,
        "severity": severity,
        "page": page,
        "summary": summary,
        "evidence": evidence or "",
        "ts": datetime.now().isoformat(timespec="seconds"),
    })


def save_screenshot(page, name):
    try:
        page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=False, timeout=8000)
    except Exception as e:
        print(f"  [shot fail] {name}: {e}")


def get_routes(app_url_map):
    """Extract all GET routes from Flask app."""
    import sys as _sys
    _sys.path.insert(0, '/workspace/app')
    _sys.path.insert(0, '/workspace')
    from app import app as flask_app
    routes = []
    for rule in flask_app.url_map.iter_rules():
        if 'GET' in rule.methods and not rule.rule.startswith('/static'):
            routes.append(rule.rule)
    return sorted(set(routes))


def main():
    print("[*] WMS 浏览器+接口深度 BUG 扫描启动")
    print("=" * 60)

    # ===== Phase 1: Get all routes =====
    print("\n[Phase 1] 提取 Flask 路由...")
    routes = get_routes(None)
    print(f"  发现 {len(routes)} 个 GET 路由")

    # Save routes
    with open(OUT_DIR / "routes.json", "w", encoding="utf-8") as f:
        json.dump(routes, f, ensure_ascii=False, indent=2)

    # ===== Phase 2: Login =====
    print("\n[Phase 2] 启动浏览器登录 WMS...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        ctx = browser.new_context(
            viewport={'width': 1366, 'height': 800},
            ignore_https_errors=True,
            locale='zh-CN',
        )

        # Capture console + network
        def on_console(msg):
            try:
                if msg.type in ('error', 'warning'):
                    console_errors.append({
                        'page': page.url if 'page' in dir() else 'unknown',
                        'type': msg.type,
                        'text': msg.text[:500],
                    })
            except Exception:
                pass

        def on_response(resp):
            try:
                if resp.status >= 400:
                    network_errors.append({
                        'page': page.url if 'page' in dir() else 'unknown',
                        'status': resp.status,
                        'url': resp.url[:200],
                    })
            except Exception:
                pass

        page = ctx.new_page()
        page.on("console", on_console)
        page.on("response", on_response)

        # Try multiple passwords
        login_ok = False
        must_change = False
        for pwd in ['admin', 'Admin@123', 'AAAA1234', 'admin123', 'NewAdm!n2026']:
            print(f"  尝试密码: {pwd}")
            try:
                page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=15000)
                # Fill form
                page.fill('input[name="username"]', 'admin')
                page.fill('input[name="password"]', pwd)
                # Submit
                page.click('button[type="submit"]', timeout=5000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                cur = page.url
                if '/change_password' in cur or '首次登录' in page.title():
                    must_change = True
                    print(f"  [+] 登录成功但需修改密码 ({pwd}), URL={cur}")
                    # Change password
                    try:
                        page.fill('input[name="current_password"]', pwd)
                        page.fill('input[name="new_password"]', 'NewAdm!n2026')
                        page.fill('input[name="confirm_password"]', 'NewAdm!n2026')
                        page.click('button[type="submit"]', timeout=5000)
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                        if '/change_password' not in page.url:
                            login_ok = True
                            print(f"  [+] 密码修改完成, URL={page.url}")
                            break
                        else:
                            print(f"  [!] 修改密码后仍在 change_password 页")
                            # Check body
                            body = page.evaluate('() => document.body.innerText.slice(0, 300)')
                            print(f"  body: {body}")
                            break
                    except Exception as e:
                        print(f"  [!] 修改密码失败: {e}")
                elif '/login' not in cur:
                    login_ok = True
                    print(f"  [+] 登录成功 (password={pwd}), URL={cur}")
                    save_screenshot(page, "00_after_login")
                    break
                else:
                    print(f"  [-] 登录失败")
            except Exception as e:
                print(f"  [!] 异常: {e}")

        if not login_ok:
            print("  [!] 所有密码尝试失败，退出")
            browser.close()
            return

        # Save home page
        save_screenshot(page, "01_home")

        # ===== Phase 3: Crawl all routes (HTTP status check + console errors) =====
        print("\n[Phase 3] 爬取所有路由...")
        visited = []
        page_500s = []
        page_404s = []
        slow_pages = []

        for i, route in enumerate(routes):
            url = f"{BASE}{route}"
            try:
                t0 = time.time()
                resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
                elapsed = time.time() - t0
                status = resp.status if resp else 0
                final_url = page.url
                title = page.title()
                # Check for error markers
                body_text = page.evaluate("() => document.body && document.body.innerText.slice(0, 2000) || ''") or ""

                has_error = False
                if status >= 500:
                    page_500s.append((route, status, final_url))
                    has_error = True
                if status == 404:
                    page_404s.append((route, status, final_url))
                # Check for traceback / Error markers
                if ('Traceback' in body_text) or ('UndefinedError' in body_text) or body_text.strip() == 'Error':
                    has_error = True
                    if status not in (500,):
                        page_500s.append((route, status, final_url + ' (UndefError in body)'))

                if elapsed > 3.0:
                    slow_pages.append((route, round(elapsed, 2)))

                visited.append({
                    'route': route,
                    'status': status,
                    'final_url': final_url,
                    'title': title[:80],
                    'elapsed': round(elapsed, 2),
                    'has_error': has_error,
                })
            except PWTimeout:
                visited.append({
                    'route': route, 'status': -1, 'final_url': url, 'title': 'TIMEOUT',
                    'elapsed': -1, 'has_error': True
                })
                page_500s.append((route, -1, url + ' (TIMEOUT)'))
            except Exception as e:
                visited.append({
                    'route': route, 'status': -2, 'final_url': url, 'title': 'EXC',
                    'elapsed': -1, 'has_error': True, 'exc': str(e)[:100]
                })

            if (i + 1) % 25 == 0:
                print(f"  进度 {i+1}/{len(routes)}")

        print(f"  完成 {len(visited)} 个路由")
        print(f"  5xx 错误: {len(page_500s)}")
        print(f"  404 错误: {len(page_404s)}")
        print(f"  慢加载 (>3s): {len(slow_pages)}")

        # Save visited
        with open(OUT_DIR / "visited.json", "w", encoding="utf-8") as f:
            json.dump(visited, f, ensure_ascii=False, indent=2)

        # Record 5xx as BUGs
        for r, st, url in page_500s:
            add_finding("HTTP 5xx", "P1", r, f"页面返回 {st} 或渲染异常", f"final_url={url}")
            save_screenshot(page, f"err_5xx_{re.sub(r'[^a-zA-Z0-9_]', '_', r)}")

        # Record 404s only for routes that should exist
        for r, st, url in page_404s:
            add_finding("HTTP 404", "P2", r, f"页面返回 404", f"final_url={url}")

        # Record slow pages
        for r, t in slow_pages:
            add_finding("性能", "P3", r, f"页面加载耗时 {t}s (>3s)", "")

        # ===== Phase 4: Test admin pages & important features =====
        print("\n[Phase 4] 重点页面交互测试...")

        # Test all menus
        menu_groups = {
            "基础数据": ["/material", "/category", "/unit", "/supplier", "/customer",
                         "/warehouse", "/employee", "/department", "/contract", "/bom",
                         "/label_template", "/opening_stock"],
            "业务单据": ["/purchase_request", "/purchase_order", "/in_order",
                         "/sales_order", "/out_order", "/other_out_order",
                         "/after_sale_out", "/transfer", "/subcontract",
                         "/check", "/adjustment", "/requisition"],
            "报表": ["/report", "/report_dashboard", "/stock_query",
                     "/purchase_report", "/sales_report", "/sales_dashboard",
                     "/sales_outflow_report", "/sales_execution_report",
                     "/sales_reconciliation_report", "/sales_exceptions",
                     "/sales_trend_report", "/sales_price_analysis"],
            "AI": ["/ai", "/ai/replenishment", "/ai/replenishment_live",
                   "/ai/inventory_health", "/ai/inventory_health_live",
                   "/ai/material_alias", "/ai/location_recommendation",
                   "/ai/demand_forecast", "/ai/supplier_evaluation",
                   "/ai/document_jobs", "/ai/document_confirm",
                   "/ai/document_job_detail", "/ai/agent_tasks",
                   "/ai/ops_dashboard", "/ai/business_quality",
                   "/ai/data_retention", "/ai/acceptance",
                   "/ai/prelaunch", "/ai/sales_workbench",
                   "/ai/purchase_workbench", "/ai/warehouse_workbench"],
            "系统": ["/admin_console", "/user", "/system_settings",
                     "/backup", "/approval", "/operation_audit",
                     "/my_profile", "/change_password", "/alert"],
        }

        for group, paths in menu_groups.items():
            for path in paths:
                if path not in routes:
                    add_finding("路由缺失", "P2", path, f"菜单 {group} 中的路径在路由表中不存在", "")
                    continue
                try:
                    resp = page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=10000)
                    body = page.evaluate("() => document.body && document.body.innerText.slice(0, 2000) || ''") or ""
                    if 'Traceback' in body or body.strip() == 'Error' or 'UndefinedError' in body:
                        add_finding("模板渲染错误", "P1", path, "页面内容包含 Traceback 或 UndefinedError",
                                    body[:300])
                        save_screenshot(page, f"err_render_{re.sub(r'[^a-zA-Z0-9_]', '_', path)}")
                except Exception as e:
                    add_finding("菜单访问异常", "P2", path, f"访问异常: {str(e)[:100]}", "")

        # ===== Phase 5: Form tests =====
        print("\n[Phase 5] 表单提交测试...")

        # Try POST to forms without CSRF token (via direct fetch)
        form_tests = [
            ("/material/add", "POST"),
            ("/supplier/add", "POST"),
            ("/unit/add", "POST"),
            ("/category/add", "POST"),
            ("/customer/add", "POST"),
            ("/warehouse/add", "POST"),
            ("/department/add", "POST"),
            ("/employee/add", "POST"),
            ("/in_order/add", "POST"),
            ("/out_order/add", "POST"),
        ]
        # Use the page's cookies
        cookies = ctx.cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

        import requests as req
        s = req.Session()
        for c in cookies:
            s.cookies.set(c['name'], c['value'])

        for url_path, method in form_tests:
            try:
                r = s.post(f"{BASE}{url_path}", data={}, timeout=10, allow_redirects=False)
                if r.status_code not in (200, 302, 400, 403, 422):
                    add_finding("表单 POST 异常", "P2", url_path, f"POST 返回 {r.status_code}",
                                r.text[:200])
            except Exception as e:
                add_finding("表单 POST 异常", "P2", url_path, f"POST 异常: {str(e)[:100]}", "")

        # ===== Phase 6: Fuzz tests on key list pages =====
        print("\n[Phase 6] 列表页参数模糊测试...")

        list_pages = ["/material", "/supplier", "/customer", "/warehouse",
                      "/unit", "/category", "/employee", "/department",
                      "/in_order", "/out_order", "/purchase_request",
                      "/purchase_order", "/sales_order", "/report",
                      "/stock_query", "/user", "/system_settings",
                      "/operation_audit", "/backup"]

        fuzz_payloads = [
            ("page=-1", "page=0", "page=999999", "page=abc"),
            ("q=' OR '1'='1", "q=<script>alert(1)</script>", "q=../../etc/passwd"),
            ("id=1 OR 1=1", "id=-1", "id=0", "id=999999999"),
        ]

        for lp in list_pages:
            for fz in [p for grp in fuzz_payloads for p in grp]:
                try:
                    r = s.get(f"{BASE}{lp}?{fz}", timeout=8, allow_redirects=False)
                    if r.status_code >= 500:
                        add_finding("参数模糊 5xx", "P1", f"{lp}?{fz}", f"GET 返回 {r.status_code}",
                                    r.text[:200])
                except Exception:
                    pass

        # ===== Phase 7: XSS check =====
        print("\n[Phase 7] XSS 反射检测...")
        xss_payload = "<script>alert('XSS_TEST_2026')</script>"
        xss_pages = ["/material", "/supplier", "/customer", "/warehouse",
                     "/in_order", "/out_order", "/report", "/stock_query", "/user"]
        for xp in xss_pages:
            try:
                r = s.get(f"{BASE}{xp}?q={xss_payload}", timeout=8)
                if xss_payload in r.text and 'XSS_TEST_2026' in r.text and '<script>alert' in r.text:
                    # Check if it's actually executing (not escaped)
                    if r.text.count(xss_payload) > 0 and not ('&lt;script&gt;' in r.text or '&amp;lt;' in r.text):
                        add_finding("XSS 反射", "P1", f"{xp}?q=", "XSS payload 未转义", r.text[:300])
            except Exception:
                pass

        # ===== Phase 8: Auth/permission =====
        print("\n[Phase 8] 权限/未登录访问检测...")
        sensitive = ["/admin_console", "/user", "/system_settings", "/backup",
                     "/operation_audit", "/change_password", "/ai/ops_dashboard",
                     "/in_order/add", "/out_order/add", "/material/add"]
        s_anon = req.Session()
        for sp in sensitive:
            try:
                r = s_anon.get(f"{BASE}{sp}", timeout=8, allow_redirects=False)
                if r.status_code == 200 and ('登录' not in r.text[:500] and 'login' not in r.text[:500].lower()):
                    add_finding("未授权访问", "P0", sp, f"未登录可访问 200", r.text[:200])
                elif r.status_code not in (302, 200, 401, 403):
                    add_finding("未授权访问异常", "P2", sp, f"未登录返回 {r.status_code}", "")
            except Exception:
                pass

        # ===== Phase 9: Header security check =====
        print("\n[Phase 9] 安全头检查...")
        r = s.get(f"{BASE}/", timeout=8)
        for header in ['X-Content-Type-Options', 'X-Frame-Options', 'X-XSS-Protection',
                       'Strict-Transport-Security', 'Content-Security-Policy']:
            if header not in r.headers:
                add_finding("安全头缺失", "P3", "/", f"缺少 {header} 响应头", "")

        # Check CORS
        if 'Access-Control-Allow-Origin' in r.headers:
            if r.headers['Access-Control-Allow-Origin'] == '*':
                add_finding("CORS 过宽", "P3", "/", "Access-Control-Allow-Origin: *", "")

        # ===== Phase 10: Static asset / error pages =====
        print("\n[Phase 10] 错误页/静态资源...")
        for path in ["/nonexistent_page_12345", "/../etc/passwd",
                     "/static/nonexistent.css", "/.git/HEAD",
                     "/admin", "/wp-admin", "/phpmyadmin", "/.env"]:
            try:
                r = s.get(f"{BASE}{path}", timeout=5, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("错误页 5xx", "P2", path, f"GET 返回 {r.status_code}", "")
            except Exception:
                pass

        # ===== Phase 11: Page content analysis for common issues =====
        print("\n[Phase 11] 页面内容/资源分析...")
        # Visit home, check for console errors
        page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=10000)
        save_screenshot(page, "11_home_final")
        # Check responsive
        for w in [375, 414, 768, 1920]:
            page.set_viewport_size({"width": w, "height": 800})
            try:
                page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=10000)
                save_screenshot(page, f"11_home_w{w}")
                # Check horizontal scroll
                has_hscroll = page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
                if has_hscroll and w < 768:
                    add_finding("移动端横向滚动", "P3", "/", f"viewport={w} 出现横向滚动条", "")
            except Exception:
                pass

        # ===== Phase 12: Login security tests =====
        print("\n[Phase 12] 登录安全测试...")
        for bad_pwd in ['admin', '123456', 'password', 'root', '']:
            try:
                r = req.post(f"{BASE}/login", data={'username': 'admin', 'password': bad_pwd},
                             timeout=5, allow_redirects=False)
                # Should fail (not redirect to home)
                if r.status_code == 302 and 'login' not in r.headers.get('Location', '').lower():
                    add_finding("弱密码", "P1", "/login",
                                f"弱密码 {bad_pwd!r} 登录成功", "")
            except Exception:
                pass

        # Check login rate limit (5 quick fails)
        fail_count = 0
        for i in range(5):
            try:
                r = req.post(f"{BASE}/login", data={'username': 'admin', 'password': f'wrong_pwd_{i}'},
                             timeout=5, allow_redirects=False)
                if r.status_code == 200 and '密码' in r.text or '失败' in r.text:
                    fail_count += 1
            except Exception:
                pass
        if fail_count == 5:
            add_finding("登录无锁定", "P2", "/login", "5 次错误密码未触发账户锁定", "")

        browser.close()

    # ===== Save findings =====
    print("\n" + "=" * 60)
    print(f"[*] 共发现 {len(findings)} 个问题")
    sev_count = {}
    for f in findings:
        sev_count[f['severity']] = sev_count.get(f['severity'], 0) + 1
    for k, v in sorted(sev_count.items()):
        print(f"  {k}: {v}")

    # Save JSON
    with open(OUT_DIR / "findings.json", "w", encoding="utf-8") as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)

    # Save console errors
    with open(OUT_DIR / "console_errors.json", "w", encoding="utf-8") as f:
        json.dump(console_errors, f, ensure_ascii=False, indent=2)
    print(f"  控制台错误: {len(console_errors)}")

    # Save network errors
    with open(OUT_DIR / "network_errors.json", "w", encoding="utf-8") as f:
        json.dump(network_errors, f, ensure_ascii=False, indent=2)
    print(f"  网络错误: {len(network_errors)}")

    print(f"\n结果目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
