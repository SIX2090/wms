"""
WMS 浏览器+接口深度 BUG 扫描器 v2 - 增强版
目标：登录 WMS，遍历所有页面，识别尽可能多的 BUG。
新增：详情页/打印页/导出/搜索/分页/批量操作/会话/CSRF/上传等更多测试。
"""
import json
import os
import re
import sys
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://127.0.0.1:8080"
OUT_DIR = Path("/workspace/audit_screenshots/bughunt_20260729")
OUT_DIR.mkdir(parents=True, exist_ok=True)

findings = []
console_errors = []
network_errors = []
page_results = []


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


def get_routes():
    sys.path.insert(0, '/workspace/app')
    sys.path.insert(0, '/workspace')
    os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
    from app import app as flask_app
    routes = []
    for rule in flask_app.url_map.iter_rules():
        if 'GET' in rule.methods and not rule.rule.startswith('/static'):
            routes.append(rule.rule)
    return sorted(set(routes))


def main():
    print("[*] WMS 浏览器+接口深度 BUG 扫描 v2 启动")
    print("=" * 60)

    # ===== Phase 1: Get all routes =====
    print("\n[Phase 1] 提取 Flask 路由...")
    routes = get_routes()
    print(f"  发现 {len(routes)} 个 GET 路由")
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

        # Login
        login_ok = False
        for pwd in ['admin', 'NewAdm!n2026']:
            try:
                page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=15000)
                page.fill('input[name="username"]', 'admin')
                page.fill('input[name="password"]', pwd)
                page.click('button[type="submit"]', timeout=5000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                if '/login' not in page.url:
                    login_ok = True
                    print(f"  [+] 登录成功 (pwd={pwd}), URL={page.url}")
                    break
            except Exception as e:
                print(f"  [!] {pwd}: {e}")

        if not login_ok:
            print("  [!] 登录失败")
            browser.close()
            return

        save_screenshot(page, "00_after_login")
        save_screenshot(page, "01_home")

        # Get cookies for HTTP requests
        import requests as req
        s = req.Session()
        for c in ctx.cookies():
            s.cookies.set(c['name'], c['value'])

        # ===== Phase 3: Crawl all routes (HTTP status + body error check) =====
        print("\n[Phase 3] 爬取所有路由...")
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
                body_text = page.evaluate("() => document.body && document.body.innerText.slice(0, 2000) || ''") or ""

                has_error = False
                if status >= 500:
                    page_500s.append((route, status, final_url))
                    has_error = True
                if status == 404:
                    page_404s.append((route, status, final_url))
                if ('Traceback' in body_text) or ('UndefinedError' in body_text) or body_text.strip() == 'Error':
                    has_error = True
                    if status not in (500,):
                        page_500s.append((route, status, final_url + ' (UndefError in body)'))
                if elapsed > 3.0:
                    slow_pages.append((route, round(elapsed, 2)))
                page_results.append({
                    'route': route, 'status': status, 'title': title[:80],
                    'elapsed': round(elapsed, 2), 'has_error': has_error,
                })
            except PWTimeout:
                page_results.append({'route': route, 'status': -1, 'title': 'TIMEOUT', 'has_error': True})
                page_500s.append((route, -1, url + ' (TIMEOUT)'))
            except Exception as e:
                page_results.append({'route': route, 'status': -2, 'title': 'EXC', 'has_error': True, 'exc': str(e)[:100]})
            if (i + 1) % 50 == 0:
                print(f"  进度 {i+1}/{len(routes)}")

        print(f"  完成 {len(page_results)} 个路由")
        print(f"  5xx/TB 错误: {len(page_500s)}")
        print(f"  404: {len(page_404s)}")
        print(f"  慢加载 (>3s): {len(slow_pages)}")

        for r, st, url in page_500s:
            add_finding("HTTP 5xx/渲染", "P1", r, f"页面异常 status={st}", f"final={url}")
        for r, st, url in page_404s:
            add_finding("HTTP 404", "P2", r, "页面返回 404", f"final={url}")
        for r, t in slow_pages:
            add_finding("性能", "P3", r, f"加载耗时 {t}s", "")

        # ===== Phase 4: Detail pages with various IDs =====
        print("\n[Phase 4] 详情页/打印页 ID 边界测试...")
        detail_patterns = [
            ("/material/{id}", "物料"),
            ("/material/{id}/edit", "物料编辑"),
            ("/supplier/{id}", "供应商详情"),
            ("/supplier/{id}/edit", "供应商编辑"),
            ("/customer/{id}", "客户详情"),
            ("/customer/{id}/edit", "客户编辑"),
            ("/warehouse/{id}", "仓库详情"),
            ("/warehouse/{id}/edit", "仓库编辑"),
            ("/unit/{id}", "单位详情"),
            ("/category/{id}", "分类详情"),
            ("/employee/{id}", "员工详情"),
            ("/department/{id}", "部门详情"),
            ("/in_order/{id}", "入库单详情"),
            ("/in_order/{id}/edit", "入库单编辑"),
            ("/in_order/{id}/print", "入库单打印"),
            ("/out_order/{id}", "出库单详情"),
            ("/out_order/{id}/edit", "出库单编辑"),
            ("/out_order/{id}/print", "出库单打印"),
            ("/purchase_request/{id}", "采购申请详情"),
            ("/purchase_request/{id}/edit", "采购申请编辑"),
            ("/purchase_order/{id}", "采购订单详情"),
            ("/purchase_order/{id}/edit", "采购订单编辑"),
            ("/sales_order/{id}", "销售订单详情"),
            ("/sales_order/{id}/edit", "销售订单编辑"),
            ("/transfer/{id}", "调拨单详情"),
            ("/transfer/{id}/edit", "调拨单编辑"),
            ("/check/{id}", "盘点单详情"),
            ("/adjustment/{id}", "调整单详情"),
            ("/user/{id}", "用户详情"),
            ("/user/{id}/edit", "用户编辑"),
            ("/label_template/{id}", "标签模板详情"),
            ("/bom/{id}", "BOM详情"),
            ("/bom/{id}/edit", "BOM编辑"),
            ("/subcontract/{id}", "委外单详情"),
            ("/subcontract/{id}/edit", "委外单编辑"),
            ("/after_sale_out/{id}", "售后出库详情"),
            ("/after_sale_out/{id}/edit", "售后出库编辑"),
        ]
        id_tests = [1, 0, -1, 999999, 'abc', '1 OR 1=1', "''", '0/0', 1.5]
        for pattern, label in detail_patterns:
            for test_id in id_tests:
                url = f"{BASE}{pattern.replace('{id}', str(test_id))}"
                try:
                    r = s.get(url, timeout=8, allow_redirects=False)
                    if r.status_code >= 500:
                        add_finding("详情页 5xx", "P1", f"{pattern.format(id=test_id)}",
                                    f"{label} ID={test_id!r} 返回 500", r.text[:200])
                    elif r.status_code == 200 and ('Traceback' in r.text or 'UndefinedError' in r.text):
                        add_finding("详情页渲染", "P1", pattern.format(id=test_id),
                                    f"{label} ID={test_id!r} 渲染异常", r.text[:200])
                except Exception:
                    pass

        # ===== Phase 5: Form submission tests =====
        print("\n[Phase 5] 表单提交测试...")
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
            ("/purchase_request/add", "POST"),
            ("/purchase_order/add", "POST"),
            ("/sales_order/add", "POST"),
            ("/transfer/add", "POST"),
            ("/check/add", "POST"),
            ("/adjustment/add", "POST"),
            ("/user/add", "POST"),
            ("/subcontract/add", "POST"),
            ("/after_sale_out/add", "POST"),
            ("/bom/add", "POST"),
            ("/label_template/add", "POST"),
            ("/opening_stock/add", "POST"),
        ]
        for url_path, method in form_tests:
            # Test 1: Empty form
            try:
                r = s.post(f"{BASE}{url_path}", data={}, timeout=10, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("表单 5xx", "P1", url_path, f"空表单 POST 返回 {r.status_code}",
                                r.text[:200])
            except Exception as e:
                add_finding("表单异常", "P2", url_path, f"空 POST 异常: {str(e)[:100]}", "")

            # Test 2: XSS in form data
            try:
                r = s.post(f"{BASE}{url_path}", data={'name': "<script>alert('xss')</script>"},
                           timeout=10)
                if r.status_code == 200 and "<script>alert('xss')</script>" in r.text:
                    add_finding("表单 XSS", "P1", url_path, "XSS 在 name 字段未转义", r.text[:300])
            except Exception:
                pass

            # Test 3: SQL injection
            try:
                r = s.post(f"{BASE}{url_path}", data={"name": "' OR '1'='1"},
                           timeout=10)
                if r.status_code >= 500:
                    add_finding("SQL 注入 5xx", "P1", url_path, f"SQL 注入返回 {r.status_code}",
                                r.text[:200])
            except Exception:
                pass

            # Test 4: Very long input
            try:
                r = s.post(f"{BASE}{url_path}", data={"name": "A" * 10000},
                           timeout=10)
                if r.status_code >= 500:
                    add_finding("超长输入 5xx", "P2", url_path, f"10000 字符输入返回 {r.status_code}",
                                r.text[:200])
            except Exception:
                pass

        # ===== Phase 6: List page fuzzing (expanded) =====
        print("\n[Phase 6] 列表页参数模糊测试 (扩展)...")
        list_pages = ["/material", "/supplier", "/customer", "/warehouse",
                      "/unit", "/category", "/employee", "/department",
                      "/in_order", "/out_order", "/purchase_request",
                      "/purchase_order", "/sales_order", "/report",
                      "/stock_query", "/user", "/system_settings",
                      "/operation_audit", "/backup", "/alert",
                      "/label_template", "/bom", "/opening_stock",
                      "/after_sale_out", "/subcontract", "/transfer",
                      "/check", "/adjustment", "/ai/agent_tasks",
                      "/ai/document_jobs", "/ai/business_quality",
                      "/ai/data_retention", "/ai/acceptance",
                      "/ai/sales_workbench", "/ai/purchase_workbench",
                      "/ai/warehouse_workbench", "/ai/ops_dashboard"]
        fuzz_payloads = [
            "page=-1", "page=0", "page=999999", "page=abc",
            "q=' OR '1'='1", "q=<script>alert(1)</script>", "q=../../etc/passwd",
            "id=1 OR 1=1", "id=-1", "id=0", "id=999999999",
            "page_size=999999", "page_size=-1", "page_size=0",
            "sort=id; DROP TABLE users--", "sort=id&order=ASC;DELETE",
            "start_date=invalid", "start_date=9999-99-99", "end_date=-1",
            "per_page=999999", "limit=999999", "offset=-1",
            "format=json", "format=xml", "format=csv",
        ]
        for lp in list_pages:
            for fz in fuzz_payloads:
                try:
                    r = s.get(f"{BASE}{lp}?{fz}", timeout=8, allow_redirects=False)
                    if r.status_code >= 500:
                        add_finding("参数模糊 5xx", "P1", f"{lp}?{fz}",
                                    f"GET 返回 {r.status_code}", r.text[:200])
                except Exception:
                    pass

        # ===== Phase 7: XSS check (more pages) =====
        print("\n[Phase 7] XSS 反射检测 (扩展)...")
        xss_pages = ["/material", "/supplier", "/customer", "/warehouse",
                     "/in_order", "/out_order", "/report", "/stock_query", "/user",
                     "/category", "/unit", "/employee", "/department",
                     "/purchase_request", "/purchase_order", "/sales_order",
                     "/label_template", "/bom", "/operation_audit",
                     "/alert", "/system_settings"]
        xss_payloads = [
            "<script>alert('XSS_TEST_2026')</script>",
            "'><script>alert(1)</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "\"><svg onload=alert(1)>",
        ]
        for xp in xss_pages:
            for payload in xss_payloads:
                try:
                    r = s.get(f"{BASE}{xp}?q={quote(payload)}", timeout=8)
                    if payload in r.text and not ('&lt;script&gt;' in r.text or '&amp;lt;' in r.text):
                        # Check if the literal payload is reflected (not escaped)
                        if r.text.count(payload) > 0:
                            add_finding("XSS 反射", "P1", f"{xp}?q=",
                                        f"XSS payload 反射", payload[:80])
                            break  # one finding per page is enough
                except Exception:
                    pass

        # ===== Phase 8: Auth/permission tests =====
        print("\n[Phase 8] 权限/未登录访问检测 (扩展)...")
        s_anon = req.Session()
        sensitive = ["/admin_console", "/user", "/system_settings", "/backup",
                     "/operation_audit", "/change_password", "/ai/ops_dashboard",
                     "/in_order/add", "/out_order/add", "/material/add",
                     "/supplier/add", "/customer/add", "/warehouse/add",
                     "/department/add", "/employee/add", "/unit/add",
                     "/category/add", "/user/add", "/bom/add",
                     "/label_template/add", "/opening_stock/add",
                     "/after_sale_out/add", "/subcontract/add",
                     "/transfer/add", "/check/add", "/adjustment/add",
                     "/purchase_request/add", "/purchase_order/add",
                     "/sales_order/add", "/ai/business_quality",
                     "/ai/data_retention", "/ai/acceptance",
                     "/ai/sales_workbench", "/ai/purchase_workbench",
                     "/ai/warehouse_workbench", "/ai/agent_tasks",
                     "/ai/document_jobs", "/ai/prelaunch",
                     "/admin_mobile_tokens"]
        for sp in sensitive:
            try:
                r = s_anon.get(f"{BASE}{sp}", timeout=8, allow_redirects=False)
                if r.status_code == 200 and ('登录' not in r.text[:500] and 'login' not in r.text[:500].lower()):
                    add_finding("未授权访问", "P0", sp, "未登录可访问 200", r.text[:200])
                elif r.status_code not in (302, 200, 401, 403):
                    add_finding("未授权异常", "P2", sp, f"未登录返回 {r.status_code}", "")
            except Exception:
                pass

        # ===== Phase 9: Security headers =====
        print("\n[Phase 9] 安全头检查...")
        r = s.get(f"{BASE}/", timeout=8)
        for header in ['X-Content-Type-Options', 'X-Frame-Options', 'X-XSS-Protection',
                       'Strict-Transport-Security', 'Content-Security-Policy',
                       'Referrer-Policy']:
            if header not in r.headers:
                add_finding("安全头缺失", "P3", "/", f"缺少 {header} 响应头", "")

        # ===== Phase 10: Error pages / static assets =====
        print("\n[Phase 10] 错误页/静态资源...")
        for path in ["/nonexistent_page_12345", "/../etc/passwd",
                     "/static/nonexistent.css", "/.git/HEAD",
                     "/admin", "/wp-admin", "/phpmyadmin", "/.env",
                     "/api/users", "/api/v1", "/api/admin",
                     "/debug", "/config", "/settings",
                     "/login/admin", "/admin/login", "/user/admin",
                     "/logout", "/logout?force=1",
                     "/api/ai/v2/conversations",
                     "/api/ai/v2/tools/inventory/health",
                     "/api/ai/v2/tools/inventory/low-stock",
                     "/api/ai/v2/tools/inventory/value",
                     "/api/ai/v2/tools/navigation/skills"]:
            try:
                r = s.get(f"{BASE}{path}", timeout=5, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("错误页 5xx", "P2", path, f"GET 返回 {r.status_code}",
                                r.text[:200])
            except Exception:
                pass

        # ===== Phase 11: Pagination tests =====
        print("\n[Phase 11] 分页测试...")
        for lp in ["/material", "/supplier", "/customer", "/in_order", "/out_order",
                   "/purchase_request", "/purchase_order", "/sales_order",
                   "/operation_audit", "/user"]:
            for p_param in ["page=1", "page=2", "page=999", "page=0", "page=-1",
                            "per_page=10", "per_page=100", "per_page=999999",
                            "page_size=200", "limit=500"]:
                try:
                    r = s.get(f"{BASE}{lp}?{p_param}", timeout=8)
                    if r.status_code >= 500:
                        add_finding("分页 5xx", "P1", f"{lp}?{p_param}",
                                    f"分页返回 {r.status_code}", r.text[:200])
                except Exception:
                    pass

        # ===== Phase 12: Search/filter edge cases =====
        print("\n[Phase 12] 搜索/筛选边界...")
        search_payloads = [
            ("q=", "空搜索"),
            ("q=   ", "纯空格"),
            ("q=" + quote("%" * 100), "100 个 %"),
            ("q=" + quote("_" * 100), "100 个 _"),
            ("q=" + quote("中文" * 100), "100 个中文"),
            ("q=*" * 5, "通配符"),
        ]
        for lp in ["/material", "/supplier", "/in_order", "/out_order"]:
            for q, desc in search_payloads:
                try:
                    r = s.get(f"{BASE}{lp}?{q}", timeout=8)
                    if r.status_code >= 500:
                        add_finding("搜索 5xx", "P1", f"{lp}?{q}",
                                    f"{desc} 返回 {r.status_code}", r.text[:200])
                except Exception:
                    pass

        # ===== Phase 13: Session/CSRF tests =====
        print("\n[Phase 13] 会话/CSRF 测试...")
        # CSRF: POST without token
        for url_path, _ in form_tests[:5]:
            try:
                r = s.post(f"{BASE}{url_path}", data={'name': 'test'}, timeout=8)
                # Should be 400 or 403 (CSRF rejection)
                if r.status_code == 200:
                    add_finding("CSRF 缺失", "P1", url_path, "POST 无 CSRF 仍 200", r.text[:200])
            except Exception:
                pass

        # ===== Phase 14: Mobile responsive check =====
        print("\n[Phase 14] 移动端响应式...")
        for w in [375, 414, 768, 1366, 1920]:
            page.set_viewport_size({"width": w, "height": 800})
            for path in ["/", "/material", "/in_order", "/out_order", "/report",
                         "/stock_query", "/user", "/system_settings"]:
                try:
                    page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=10000)
                    has_hscroll = page.evaluate(
                        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 5"
                    )
                    if has_hscroll:
                        add_finding("横向滚动", "P3", f"{path}@w{w}",
                                    f"viewport={w} 出现横向滚动", "")
                except Exception:
                    pass
        # Reset viewport
        page.set_viewport_size({"width": 1366, "height": 800})

        # ===== Phase 15: Page content checks =====
        print("\n[Phase 15] 页面内容/可访问性...")
        for path in ["/", "/material", "/in_order", "/out_order", "/report",
                     "/user", "/system_settings", "/admin_console"]:
            try:
                page.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=10000)
                # Check for missing alt attributes
                missing_alt = page.evaluate("""() => {
                    const imgs = Array.from(document.querySelectorAll('img'));
                    return imgs.filter(i => !i.alt && !i.getAttribute('aria-label')).length;
                }""")
                if missing_alt and missing_alt > 3:
                    add_finding("可访问性", "P3", path,
                                f"{missing_alt} 张图片缺少 alt 属性", "")
                # Check for buttons without labels
                unlabeled = page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    return btns.filter(b => !b.textContent.trim() && !b.getAttribute('aria-label')).length;
                }""")
                if unlabeled and unlabeled > 3:
                    add_finding("可访问性", "P3", path,
                                f"{unlabeled} 个按钮缺少 label", "")
            except Exception:
                pass

        # ===== Phase 16: API endpoints =====
        print("\n[Phase 16] API 端点测试...")
        api_paths = [
            "/api/materials", "/api/suppliers", "/api/customers",
            "/api/warehouses", "/api/units", "/api/categories",
            "/api/in_orders", "/api/out_orders",
            "/api/ai/v2/conversations", "/api/ai/v2/tools/inventory/health",
            "/api/ai/v2/tools/inventory/low-stock",
            "/api/ai/v2/tools/inventory/material",
            "/api/ai/v2/tools/inventory/transactions",
            "/api/ai/v2/tools/inventory/value",
            "/api/ai/v2/tools/navigation/help",
            "/api/ai/v2/tools/navigation/skills",
            "/api/ai/tools",
            "/api/ai/knowledge_search",
            "/api/ai/chat",
            "/api/ai/draft_check",
            "/api/ai/warehouse_assistant",
            "/api/ai/history",
            "/api/ai/audit",
            "/api/health", "/api/version", "/api/status",
        ]
        for ap in api_paths:
            try:
                r = s.get(f"{BASE}{ap}", timeout=8, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("API 5xx", "P1", ap, f"GET 返回 {r.status_code}", r.text[:200])
                elif r.status_code == 401 or r.status_code == 403:
                    add_finding("API 未授权", "P2", ap, f"GET 返回 {r.status_code} (需要鉴权)", "")
            except Exception:
                pass

        # ===== Phase 17: Detail with real IDs from DB =====
        print("\n[Phase 17] 真实 ID 测试...")
        try:
            import sqlite3
            conn = sqlite3.connect('/workspace/app/instance/inventory.db')
            cur = conn.cursor()
            # Get some real IDs
            for table, url_pattern in [
                ('material', '/material/{id}'),
                ('material', '/material/{id}/edit'),
                ('supplier', '/supplier/{id}'),
                ('customer', '/customer/{id}'),
                ('warehouse', '/warehouse/{id}'),
                ('in_order', '/in_order/{id}'),
                ('in_order', '/in_order/{id}/print'),
                ('out_order', '/out_order/{id}'),
                ('out_order', '/out_order/{id}/print'),
                ('user', '/user/{id}'),
                ('user', '/user/{id}/edit'),
            ]:
                try:
                    cur.execute(f"SELECT id FROM {table} LIMIT 1")
                    row = cur.fetchone()
                    if row:
                        rid = row[0]
                        url = f"{BASE}{url_pattern.replace('{id}', str(rid))}"
                        r = s.get(url, timeout=8)
                        if r.status_code >= 500:
                            add_finding("真实 ID 5xx", "P1", url,
                                        f"{table}.id={rid} 返回 500", r.text[:200])
                        if 'Traceback' in r.text or 'UndefinedError' in r.text:
                            add_finding("真实 ID 渲染", "P1", url,
                                        f"{table}.id={rid} 渲染异常", r.text[:200])
                except Exception:
                    pass
            conn.close()
        except Exception as e:
            print(f"  DB 错误: {e}")

        # ===== Phase 18: Data integrity check =====
        print("\n[Phase 18] 数据完整性/业务规则...")
        try:
            import sqlite3
            conn = sqlite3.connect('/workspace/app/instance/inventory.db')
            cur = conn.cursor()
            # Check for negative stock
            cur.execute("SELECT COUNT(*) FROM material WHERE stock < 0")
            neg_stock = cur.fetchone()[0]
            if neg_stock > 0:
                add_finding("数据完整性", "P1", "/stock_query",
                            f"物料表存在 {neg_stock} 条负库存记录", "")

            # Check for material without category
            cur.execute("SELECT COUNT(*) FROM material WHERE category_id IS NULL")
            no_cat = cur.fetchone()[0]
            if no_cat > 0:
                add_finding("数据完整性", "P2", "/material",
                            f"{no_cat} 个物料缺少分类", "")

            # Check for material without unit
            cur.execute("SELECT COUNT(*) FROM material WHERE unit_id IS NULL")
            no_unit = cur.fetchone()[0]
            if no_unit > 0:
                add_finding("数据完整性", "P2", "/material",
                            f"{no_unit} 个物料缺少单位", "")

            # Check duplicate codes
            cur.execute("SELECT code, COUNT(*) FROM material GROUP BY code HAVING COUNT(*) > 1")
            dups = cur.fetchall()
            if dups:
                add_finding("数据完整性", "P1", "/material",
                            f"{len(dups)} 个重复的物料编码", str(dups[:5]))

            # Check empty required fields
            cur.execute("SELECT COUNT(*) FROM material WHERE name = '' OR name IS NULL")
            no_name = cur.fetchone()[0]
            if no_name > 0:
                add_finding("数据完整性", "P1", "/material",
                            f"{no_name} 个物料名称为空", "")

            conn.close()
        except Exception as e:
            print(f"  DB check error: {e}")

        # ===== Phase 19: File upload tests =====
        print("\n[Phase 19] 文件上传测试...")
        # Test image upload
        for upload_url in ["/upload", "/api/upload", "/material/import", "/supplier/import",
                          "/in_order/import", "/out_order/import", "/user/import",
                          "/batch_import", "/label_template/import",
                          "/customer/import", "/warehouse/import",
                          "/unit/import", "/category/import",
                          "/department/import", "/employee/import",
                          "/bom/import", "/opening_stock/import"]:
            try:
                # Send an empty file
                r = s.post(f"{BASE}{upload_url}", files={'file': ('test.txt', b'hello')}, timeout=8)
                if r.status_code >= 500:
                    add_finding("上传 5xx", "P1", upload_url,
                                f"上传返回 {r.status_code}", r.text[:200])
            except Exception:
                pass

        # ===== Phase 20: Method tests (wrong HTTP method) =====
        print("\n[Phase 20: HTTP 方法测试]")
        for url_path in ["/login", "/logout", "/", "/material/add", "/in_order/add"]:
            for method in ["PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
                try:
                    r = s.request(method, f"{BASE}{url_path}", timeout=5, allow_redirects=False)
                    if r.status_code >= 500:
                        add_finding("方法 5xx", "P2", f"{method} {url_path}",
                                    f"{method} 返回 {r.status_code}", r.text[:200])
                except Exception:
                    pass

        # ===== Phase 21: Export/Download tests =====
        print("\n[Phase 21: 导出/下载测试]")
        for path in ["/material/export", "/supplier/export", "/customer/export",
                     "/in_order/export", "/out_order/export", "/stock_query/export",
                     "/report/export", "/report.pdf", "/material/export.xlsx",
                     "/in_order/export.xlsx", "/out_order/export.xlsx",
                     "/material/print", "/supplier/print", "/customer/print",
                     "/material/template", "/supplier/template", "/in_order/template"]:
            try:
                r = s.get(f"{BASE}{path}", timeout=10, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("导出 5xx", "P1", path, f"GET 返回 {r.status_code}", r.text[:200])
            except Exception:
                pass

        # ===== Phase 22: Mobile QR/Scan tests =====
        print("\n[Phase 22: 移动扫码/H5 测试]")
        for path in ["/mobile", "/mobile/scan", "/mobile/connect",
                     "/h5", "/m", "/wechat", "/api/wechat",
                     "/mobile/in_order", "/mobile/out_order", "/mobile/stock_query",
                     "/api/mobile/login", "/api/mobile/sync"]:
            try:
                r = s.get(f"{BASE}{path}", timeout=8, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("移动端 5xx", "P1", path, f"GET 返回 {r.status_code}", r.text[:200])
            except Exception:
                pass

        # ===== Phase 23: Deep links and redirects =====
        print("\n[Phase 23: 重定向/锚点测试]")
        for path in ["/", "/material#add", "/in_order#new", "/report#dashboard",
                     "/?lang=en", "/?theme=dark", "/?_=1"]:
            try:
                r = s.get(f"{BASE}{path}", timeout=8, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("链接 5xx", "P2", path, f"GET 返回 {r.status_code}", r.text[:200])
            except Exception:
                pass

        # ===== Phase 24: Concurrent session =====
        print("\n[Phase 24: 多会话测试]")
        # Open a second session in another context
        ctx2 = browser.new_context(
            viewport={'width': 1366, 'height': 800},
            locale='zh-CN',
        )
        page2 = ctx2.new_page()
        try:
            page2.goto(f"{BASE}/login")
            page2.fill('input[name="username"]', 'admin')
            page2.fill('input[name="password"]', 'admin')
            page2.click('button[type="submit"]', timeout=5000)
            page2.wait_for_load_state("domcontentloaded", timeout=10000)
            if '/login' in page2.url:
                add_finding("多会话登录", "P2", "/login", "第二会话登录失败", "")
        except Exception as e:
            add_finding("多会话异常", "P3", "/login", f"第二会话异常: {str(e)[:100]}", "")
        finally:
            ctx2.close()

        # ===== Phase 25: Cookie security =====
        print("\n[Phase 25: Cookie 安全]")
        for c in ctx.cookies():
            if c.get('httpOnly') is False:
                add_finding("Cookie 安全", "P2", "/login", f"Cookie {c['name']} 非 HttpOnly", "")
            if c.get('secure') is False and c['name'] in ('session', 'remember_token'):
                add_finding("Cookie 安全", "P3", "/login", f"Cookie {c['name']} 非 Secure", "")
            if c.get('sameSite') is None:
                add_finding("Cookie 安全", "P3", "/login", f"Cookie {c['name']} 无 SameSite", "")

        # ===== Phase 26: Login security =====
        print("\n[Phase 26: 登录安全]")
        for bad_pwd in ['admin', '123456', 'password', 'root', '']:
            try:
                r = req.post(f"{BASE}/login", data={'username': 'admin', 'password': bad_pwd},
                             timeout=5, allow_redirects=False)
                if r.status_code == 302 and 'login' not in r.headers.get('Location', '').lower():
                    add_finding("弱密码", "P1", "/login", f"弱密码 {bad_pwd!r} 登录成功", "")
            except Exception:
                pass

        # Check if user enumeration possible
        for user in ['admin', 'root', 'test', 'nonexistent', 'user']:
            try:
                r = req.post(f"{BASE}/login", data={'username': user, 'password': 'wrong_password_xyz'},
                             timeout=5)
                if '用户不存在' in r.text or 'user not found' in r.text.lower():
                    add_finding("用户枚举", "P2", "/login", f"用户 {user} 存在性可探测", "")
            except Exception:
                pass

        # ===== Phase 27: AI endpoints comprehensive =====
        print("\n[Phase 27: AI 端点深度测试]")
        ai_endpoints = [
            ("/ai/chat", "POST", {"message": "test", "user_id": "admin"}),
            ("/ai/chat/stream", "POST", {"message": "test", "user_id": "admin"}),
            ("/api/ai/chat", "POST", {"message": "test"}),
            ("/api/ai/chat/stream", "POST", {"message": "test"}),
            ("/ai/tools", "GET", None),
            ("/api/ai/tools", "GET", None),
            ("/ai/history", "GET", None),
            ("/api/ai/history", "GET", None),
            ("/ai/audit", "GET", None),
            ("/ai/draft_check", "POST", {"text": "test"}),
            ("/ai/extract", "POST", {}),
            ("/ai/document_extract", "POST", {}),
            ("/ai/delivery_match", "POST", {}),
            ("/ai/inventory_health", "GET", None),
            ("/ai/replenishment", "GET", None),
            ("/ai/sales_followup", "GET", None),
            ("/ai/purchase_followup", "GET", None),
            ("/ai/warehouse_patrol", "GET", None),
        ]
        for ep, method, data in ai_endpoints:
            try:
                if method == "GET":
                    r = s.get(f"{BASE}{ep}", timeout=8)
                else:
                    r = s.post(f"{BASE}{ep}", data=data or {}, timeout=8)
                if r.status_code >= 500:
                    add_finding("AI 5xx", "P1", f"{method} {ep}",
                                f"返回 {r.status_code}", r.text[:200])
            except Exception:
                pass

        # ===== Phase 28: Print templates =====
        print("\n[Phase 28: 打印模板/Excel 模板]")
        for path in ["/in_order/print_template", "/out_order/print_template",
                     "/print/in_order", "/print/out_order",
                     "/excel/in_order", "/excel/out_order",
                     "/static/templates/入库单打印模板示例.xlsx",
                     "/static/templates/出库单打印模板示例.xlsx",
                     "/static/templates/领料单打印模板示例.xlsx"]:
            try:
                r = s.get(f"{BASE}{path}", timeout=8, allow_redirects=False)
                if r.status_code >= 500:
                    add_finding("打印 5xx", "P1", path, f"GET 返回 {r.status_code}", r.text[:200])
            except Exception:
                pass

        browser.close()

    # ===== Save findings =====
    print("\n" + "=" * 60)
    print(f"[*] 共发现 {len(findings)} 个问题")
    sev_count = {}
    cat_count = {}
    for f in findings:
        sev_count[f['severity']] = sev_count.get(f['severity'], 0) + 1
        cat_count[f['category']] = cat_count.get(f['category'], 0) + 1
    for k, v in sorted(sev_count.items()):
        print(f"  {k}: {v}")
    print(f"\n  按类别:")
    for k, v in sorted(cat_count.items(), key=lambda x: -x[1])[:15]:
        print(f"    {k}: {v}")

    with open(OUT_DIR / "findings.json", "w", encoding="utf-8") as f:
        json.dump(findings, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "console_errors.json", "w", encoding="utf-8") as f:
        json.dump(console_errors, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "network_errors.json", "w", encoding="utf-8") as f:
        json.dump(network_errors, f, ensure_ascii=False, indent=2)
    with open(OUT_DIR / "page_results.json", "w", encoding="utf-8") as f:
        json.dump(page_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
