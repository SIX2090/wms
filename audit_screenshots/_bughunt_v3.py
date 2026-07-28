"""
WMS 浏览器+接口深度 BUG 扫描器 v3 - 扩展版
新增覆盖：静态资源 404、链接完整性、表单验证、可访问性、i18n、性能、
        业务逻辑、权限绕过、CSRF/会话/编码、HTML/CSS 错误、截断、特殊字符等。
"""
import json
import os
import re
import sys
import time
import traceback
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
OUT_DIR = Path("/workspace/audit_screenshots/bughunt_20260729")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 加载已有 108 条 finding 继续编号
findings = []
prior_path = OUT_DIR / "findings.json"
if prior_path.exists():
    try:
        prior = json.load(open(prior_path))
        for x in prior:
            findings.append(x)
        print(f"[*] 已加载历史 findings: {len(findings)} 条")
    except Exception:
        pass

START_NUM = len(findings) + 1
console_errors = []
network_errors = []


def add_finding(category, severity, page, summary, evidence=None):
    findings.append({
        "id": f"BUG-{len(findings)+1:03d}",
        "category": category,
        "severity": severity,
        "page": page,
        "summary": summary,
        "evidence": (evidence or "")[:600],
        "ts": datetime.now().isoformat(timespec="seconds"),
    })


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
    print("[*] WMS 浏览器+接口深度 BUG 扫描 v3 启动")
    print("=" * 60)
    print(f"[*] 起始编号 BUG-{START_NUM:03d}")

    routes = get_routes()
    print(f"[*] 发现 {len(routes)} 个 GET 路由")

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
        page = ctx.new_page()

        def on_console(msg):
            try:
                if msg.type in ('error', 'warning'):
                    console_errors.append({'page': page.url, 'type': msg.type, 'text': msg.text[:500]})
            except Exception:
                pass

        def on_response(resp):
            try:
                if resp.status >= 400:
                    network_errors.append({'page': page.url, 'status': resp.status, 'url': resp.url})
            except Exception:
                pass

        page.on('console', on_console)
        page.on('response', on_response)

        # ===== Login =====
        print("\n[Login] 登录 WMS...")
        try:
            page.goto(f"{BASE}/login", timeout=15000)
            page.fill('input[name="username"]', 'admin')
            page.fill('input[name="password"]', 'admin')
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle', timeout=10000)
            print(f"  after login: {page.url}")
        except Exception as e:
            print(f"  [login] {e}")
            # 强制绕过密码修改页
            try:
                page.goto(f"{BASE}/", timeout=10000)
            except Exception:
                pass

        # 取主导航链接
        main_links = []
        try:
            anchors = page.eval_on_selector_all('a[href]', 'els => els.map(e => e.getAttribute("href"))')
            for a in anchors:
                if a and not a.startswith('javascript:') and not a.startswith('#') and not a.startswith('http'):
                    if not a.startswith('/static'):
                        main_links.append(a)
        except Exception:
            pass
        main_links = sorted(set(main_links))
        print(f"[*] 主页发现 {len(main_links)} 个内部链接")

        # ===== 新增1: 静态资源 404 / 缺失 =====
        print("\n[New-1] 静态资源 404 检查...")
        asset_extensions = ('.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.gif', '.webp')
        asset_404 = []
        for path in ['/static/css/app.css', '/static/js/app.js', '/static/img/logo.png',
                     '/static/favicon.ico', '/static/img/avatar.png', '/static/css/bootstrap.min.css',
                     '/static/js/jquery.min.js', '/static/img/cover.jpg', '/static/img/empty.png',
                     '/static/img/error.svg', '/static/img/success.svg']:
            try:
                r = ctx.request.get(f"{BASE}{path}")
                if r.status == 404:
                    add_finding("静态资源 404", "P3", path, f"静态资源 404", "")
                elif r.status == 200:
                    pass
                else:
                    add_finding("静态资源 异常", "P3", path, f"状态 {r.status}", "")
            except Exception:
                pass

        # ===== 新增2: 主页 <img> 资源 404 =====
        print("\n[New-2] 主页内嵌 <img> 资源 404 检查...")
        try:
            page.goto(f"{BASE}/", timeout=15000)
            page.wait_for_load_state('networkidle', timeout=8000)
            imgs = page.eval_on_selector_all('img[src]', 'els => els.map(e => e.getAttribute("src"))')
            for src in imgs:
                if not src or src.startswith('data:'):
                    continue
                if src.startswith('http'):
                    full = src
                else:
                    full = urllib.parse.urljoin(BASE, src)
                try:
                    r = ctx.request.get(full)
                    if r.status >= 400:
                        add_finding("图片 404", "P3", src, f"图片资源 {r.status}", "")
                except Exception:
                    pass
        except Exception as e:
            print(f"  [New-2 err] {e}")

        # ===== 新增3: 内部链接 404 =====
        print("\n[New-3] 内部链接 404 检查...")
        for link in main_links[:80]:
            if not link.startswith('/'):
                continue
            try:
                r = ctx.request.get(f"{BASE}{link}")
                if r.status == 404:
                    add_finding("链接 404", "P3", link, "内部链接 404", "")
            except Exception:
                pass

        # ===== 新增4: 详情页 ID 边界测试 =====
        print("\n[New-4] 详情页 ID 边界测试...")
        detail_patterns = [
            '/material/{id}', '/category/{id}', '/supplier/{id}', '/warehouse/{id}',
            '/unit/{id}', '/customer/{id}', '/contract/{id}', '/employee/{id}',
            '/department/{id}', '/label_template/{id}', '/bom/{id}',
            '/opening_stock/{id}', '/in_order/{id}', '/out_order/{id}',
            '/stock_query?material_id={id}', '/sales_order/{id}',
            '/transfer/{id}', '/after_sale/{id}', '/inventory_adjust/{id}',
        ]
        for pat in detail_patterns:
            for test_id in ['0', '-1', '99999999', 'abc', 'null', 'undefined', '1.5',
                            "1' OR '1'='1", '../../../etc/passwd', '%00', 'NaN']:
                url = pat.format(id=test_id)
                try:
                    r = ctx.request.get(f"{BASE}{url}")
                    if r.status == 500:
                        add_finding("详情 边界 5xx", "P1", url, f"id={test_id} 返回 500", r.text()[:200] if hasattr(r.text, '__call__') else r.text[:200])
                except Exception:
                    pass

        # ===== 新增5: 跨用户水平越权 =====
        print("\n[New-5] 水平越权测试 (低权限用户访问管理接口)...")
        # 用 viewer 账号登录再访问 admin-only 资源
        for user in ['viewer', 'guest', 'operator', 'user1', 'test']:
            try:
                p2 = ctx.new_page()
                p2.goto(f"{BASE}/login", timeout=10000)
                p2.fill('input[name="username"]', user)
                p2.fill('input[name="password"]', '123456')
                p2.click('button[type="submit"]')
                p2.wait_for_load_state('networkidle', timeout=8000)
                if 'login' not in p2.url:
                    # 尝试访问敏感接口
                    for protected_url in ['/user', '/admin/console', '/backup', '/system_settings',
                                          '/operation_audit', '/api/ai/v2/config', '/api/ai/v2/admin/reload']:
                        try:
                            r = ctx.request.get(f"{BASE}{protected_url}")
                            if r.status == 200:
                                add_finding("权限绕过", "P1", f"{user}->{protected_url}",
                                            f"低权限用户 {user} 访问 {protected_url} 返回 200", "")
                        except Exception:
                            pass
                p2.close()
            except Exception:
                pass

        # ===== 新增6: HTTP 方法模糊 =====
        print("\n[New-6] HTTP 方法模糊测试...")
        methods = ['OPTIONS', 'TRACE', 'CONNECT', 'PUT', 'DELETE', 'PATCH']
        for method in methods:
            for path in ['/login', '/', '/material', '/api/ai/v2/chat']:
                try:
                    req = urllib.request.Request(f"{BASE}{path}", method=method)
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        code = resp.getcode()
                        if code >= 500:
                            add_finding("方法 5xx", "P2", f"{method} {path}", f"{method} {path} 返回 {code}", "")
                except urllib.error.HTTPError as e:
                    if e.code >= 500:
                        add_finding("方法 5xx", "P2", f"{method} {path}", f"{method} {path} 返回 {e.code}", "")
                except Exception:
                    pass

        # ===== 新增7: 业务逻辑 — 负数/0/超长输入 =====
        print("\n[New-7] 业务逻辑 边界值测试...")
        biz_payloads = [
            ('/in_order', {'supplier_id': -1, 'total_qty': -100, 'total_amount': -9999.99}),
            ('/in_order', {'supplier_id': 0, 'total_qty': 0, 'total_amount': 0}),
            ('/out_order', {'customer_id': -1, 'total_qty': -1, 'total_amount': -1}),
            ('/transfer', {'from_wh': 0, 'to_wh': 0, 'qty': -1}),
            ('/opening_stock', {'qty': -1, 'price': -1}),
            ('/material', {'price': -1, 'safety_stock': -10}),
            ('/category', {'parent_id': 99999999}),
            ('/bom', {'qty': -1, 'loss_rate': 999}),
        ]
        for url, payload in biz_payloads:
            try:
                r = ctx.request.post(f"{BASE}{url}", form=payload)
                if r.status == 500:
                    add_finding("业务 5xx", "P1", url, f"负数/0 输入 500: {payload}", "")
                elif r.status == 200:
                    # 200 也可能有问题（未拒绝负数）
                    if any(v < 0 for v in payload.values()) or 0 in payload.values():
                        if url not in ('/in_order', '/out_order'):
                            add_finding("业务边界", "P2", url, f"异常数值被接受: {payload}", "")
            except Exception:
                pass

        # ===== 新增8: HTML/JS 错误检查 =====
        print("\n[New-8] 浏览器控制台错误收集...")
        try:
            for path in ['/', '/material', '/in_order', '/out_order', '/report', '/admin/console', '/system_settings']:
                page.goto(f"{BASE}{path}", timeout=12000)
                page.wait_for_load_state('networkidle', timeout=6000)
        except Exception:
            pass
        # 整理 console_errors
        seen = set()
        for ce in console_errors:
            key = (ce.get('text', '')[:100], ce.get('page', '')[:80])
            if key in seen:
                continue
            seen.add(key)
            add_finding("JS 控制台", "P3", ce.get('page', '')[:120],
                        f"[{ce.get('type')}] {ce.get('text', '')[:200]}", "")

        # ===== 新增9: 可访问性 — alt/label =====
        print("\n[New-9] 可访问性 (a11y) 检查...")
        a11y_issues = []
        for path in ['/', '/material', '/category', '/in_order', '/out_order', '/supplier',
                     '/warehouse', '/customer', '/employee', '/report']:
            try:
                page.goto(f"{BASE}{path}", timeout=10000)
                page.wait_for_load_state('networkidle', timeout=5000)
                # img 无 alt
                no_alt = page.eval_on_selector_all('img:not([alt])', 'els => els.length')
                if no_alt > 0:
                    add_finding("a11y", "P3", path, f"{no_alt} 个 <img> 缺少 alt 属性", "")
                # input 无 label
                no_label = page.evaluate('''() => {
                    const inputs = document.querySelectorAll('input[type=text], input[type=number], input[type=password], textarea, select');
                    let n = 0;
                    for (const inp of inputs) {
                        const id = inp.id;
                        if (!id) continue;
                        const hasLabel = document.querySelector(`label[for="${id}"]`);
                        const hasAria = inp.getAttribute('aria-label') || inp.getAttribute('aria-labelledby');
                        const inLabel = inp.closest('label');
                        if (!hasLabel && !hasAria && !inLabel) n++;
                    }
                    return n;
                }''')
                if no_label and no_label > 2:
                    add_finding("a11y", "P3", path, f"{no_label} 个输入字段无 label/aria-label", "")
                # 链接无文字
                empty_links = page.eval_on_selector_all('a', 'els => els.filter(e => !e.textContent.trim() && !e.querySelector("img[alt]")).length')
                if empty_links and empty_links > 0:
                    add_finding("a11y", "P3", path, f"{empty_links} 个 <a> 无文本/无 alt 图", "")
                # 按钮无文字
                empty_btns = page.eval_on_selector_all('button', 'els => els.filter(e => !e.textContent.trim() && !e.getAttribute("aria-label")).length')
                if empty_btns and empty_btns > 0:
                    add_finding("a11y", "P3", path, f"{empty_btns} 个 <button> 无文本/无 aria-label", "")
            except Exception as e:
                pass

        # ===== 新增10: i18n 硬编码英文/中文检查 =====
        print("\n[New-10] i18n 硬编码检查...")
        i18n_indicators_en = ['Submit', 'Cancel', 'Save', 'Delete', 'Edit', 'Add', 'Search',
                              'Login', 'Logout', 'Register', 'Welcome', 'Error', 'Loading',
                              'Confirm', 'Yes', 'No', 'OK', 'Back', 'Next', 'Previous']
        for path in ['/login', '/', '/material', '/in_order']:
            try:
                r = ctx.request.get(f"{BASE}{path}")
                txt = r.text() if hasattr(r.text, '__call__') else r.text
                hits = [w for w in i18n_indicators_en if f'>{w}<' in txt or f' {w} ' in txt or f'"{w}"' in txt]
                if hits and path == '/login':
                    add_finding("i18n", "P3", path, f"登录页含未翻译英文: {hits[:5]}", "")
            except Exception:
                pass

        # ===== 新增11: 性能 — 慢页面 (>2s) =====
        print("\n[New-11] 慢页面性能检查...")
        perf_paths = ['/', '/material', '/category', '/supplier', '/in_order', '/out_order',
                      '/report', '/admin/console', '/stock_query', '/sales_order', '/transfer',
                      '/label_template', '/bom', '/opening_stock', '/api/ai/v2/dashboard']
        for path in perf_paths:
            try:
                t0 = time.time()
                r = ctx.request.get(f"{BASE}{path}")
                dt = time.time() - t0
                if dt > 3.0:
                    add_finding("性能", "P2", path, f"加载耗时 {dt:.2f}s", "")
                # 响应体过大
                cl = r.headers.get('content-length', '')
                if cl and cl.isdigit() and int(cl) > 5_000_000:
                    add_finding("性能", "P3", path, f"响应体过大 {cl} bytes", "")
            except Exception:
                pass

        # ===== 新增12: 安全响应头/cookie =====
        print("\n[New-12] 安全响应头完整检查...")
        security_headers = [
            'X-Content-Type-Options', 'X-Frame-Options', 'X-XSS-Protection',
            'Strict-Transport-Security', 'Content-Security-Policy',
            'Referrer-Policy', 'Permissions-Policy',
        ]
        try:
            r = ctx.request.get(f"{BASE}/login")
            for h in security_headers:
                if h not in r.headers:
                    add_finding("安全头缺失", "P3", "/login", f"缺少 {h} 响应头", "")
        except Exception:
            pass

        # ===== 新增13: 上传限制 =====
        print("\n[New-13] 上传文件安全测试...")
        # 创建 0 字节文件 / 巨大文件 / 危险扩展名
        tmp = OUT_DIR / "_upload_test"
        tmp.mkdir(exist_ok=True)
        test_files = {
            '_empty.txt': b'',
            '_big.txt': b'X' * (10 * 1024 * 1024),
            '_exec.php': b'<?php system($_GET[c]); ?>',
            '_evil.html': b'<script>alert(1)</script>',
            '_jsp.jsp': b'<% out.println(1); %>',
            '_xxe.xml': b'<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>',
        }
        for fname, content in test_files.items():
            fpath = tmp / fname
            try:
                fpath.write_bytes(content)
            except Exception:
                continue
        upload_endpoints = ['/material/import', '/category/import', '/supplier/import',
                            '/customer/import', '/unit/import', '/warehouse/import',
                            '/employee/import', '/department/import', '/contract/import',
                            '/user/import', '/bom/import', '/opening_stock/import',
                            '/label_template/import', '/system_settings/import']
        for ue in upload_endpoints:
            for fname in ['_empty.txt', '_exec.php', '_evil.html', '_xxe.xml']:
                fpath = tmp / fname
                try:
                    with open(fpath, 'rb') as f:
                        r = ctx.request.post(f"{BASE}{ue}",
                                             multipart={'file': {'name': fname, 'mimeType': 'application/octet-stream', 'buffer': f.read()}})
                    if r.status == 500:
                        add_finding("上传 5xx", "P1", ue, f"上传 {fname} 触发 500", r.text()[:200] if hasattr(r.text, '__call__') else r.text[:200])
                except Exception:
                    pass

        # ===== 新增14: CSRF token 复用 =====
        print("\n[New-14] CSRF token 复用测试...")
        try:
            page.goto(f"{BASE}/material", timeout=10000)
            page.wait_for_load_state('networkidle', timeout=5000)
            t1 = page.evaluate('document.querySelector("input[name=csrf_token]")?.value || ""')
            page.reload()
            page.wait_for_load_state('networkidle', timeout=5000)
            t2 = page.evaluate('document.querySelector("input[name=csrf_token]")?.value || ""')
            if t1 and t2 and t1 == t2:
                add_finding("CSRF", "P1", "/material", "CSRF token 跨请求未刷新", f"t1={t1[:20]}, t2={t2[:20]}")
        except Exception:
            pass

        # ===== 新增15: 编码/转义 =====
        print("\n[New-15] 编码与转义测试...")
        encoded_payloads = [
            ('%2e%2e%2f%2e%2e%2f', '路径遍历'),
            ('%00', 'NULL 字节'),
            ("\r\n\r\n", 'CRLF 注入'),
            ('${7*7}', '模板注入'),
            ('{{7*7}}', '模板注入'),
            ('<svg/onload=alert(1)>', 'SVG XSS'),
            ("'; DROP TABLE material; --", 'SQL 注入'),
        ]
        for payload, desc in encoded_payloads:
            for path in ['/material', '/in_order', '/api/ai/v2/chat']:
                try:
                    encoded = urllib.parse.quote(payload, safe='')
                    url = f"{BASE}{path}?q={encoded}"
                    r = ctx.request.get(url)
                    if r.status == 500:
                        add_finding("编码 5xx", "P1", path, f"{desc} 触发 500", "")
                except Exception:
                    pass

        # ===== 新增16: 移动端响应式 =====
        print("\n[New-16] 移动端响应式 (375x667 / 768x1024)...")
        for w, h, label in [(375, 667, 'iPhone'), (768, 1024, 'iPad'), (320, 568, 'iPhone-SE')]:
            mobile = browser.new_context(viewport={'width': w, 'height': h}, locale='zh-CN')
            mp = mobile.new_page()
            for path in ['/', '/material', '/in_order', '/report', '/stock_query']:
                try:
                    mp.goto(f"{BASE}{path}", timeout=10000)
                    mp.wait_for_load_state('networkidle', timeout=5000)
                    # 横向滚动
                    sw = mp.evaluate('document.documentElement.scrollWidth')
                    cw = mp.evaluate('document.documentElement.clientWidth')
                    if sw > cw + 5:
                        add_finding("移动端 横向滚动", "P3", f"{path}@{w}x{label}",
                                    f"scrollWidth={sw} > clientWidth={cw}", "")
                    # 文字截断
                    trunc = mp.evaluate('''() => {
                        const all = document.querySelectorAll('td, .ellipsis, .truncate');
                        let n = 0;
                        for (const el of all) {
                            if (el.scrollWidth > el.clientWidth + 2) n++;
                        }
                        return n;
                    }''')
                    if trunc and trunc > 3:
                        add_finding("移动端 文本溢出", "P3", f"{path}@{w}",
                                    f"{trunc} 个单元格文本溢出", "")
                except Exception:
                    pass
            mobile.close()

        # ===== 新增17: 分页/排序边界 =====
        print("\n[New-17] 分页/排序边界...")
        for path in ['/material', '/in_order', '/out_order', '/supplier', '/customer', '/category']:
            for param in ['page=0', 'page=-1', 'page=99999', 'page=abc',
                          'per_page=0', 'per_page=-1', 'per_page=99999',
                          'sort=__proto__', 'order=ASC; DROP TABLE', 'order_by=invalid_field']:
                try:
                    r = ctx.request.get(f"{BASE}{path}?{param}")
                    if r.status == 500:
                        add_finding("分页 5xx", "P1", f"{path}?{param}", f"参数 500", "")
                except Exception:
                    pass

        # ===== 新增18: 重复提交 / 幂等 =====
        print("\n[New-18] 重复提交测试...")
        # 对一个 POST 提交两次相同 payload
        for path in ['/opening_stock/save', '/in_order/save', '/out_order/save',
                     '/material/save', '/category/save']:
            payload = {'code': f'TEST-{int(time.time())}', 'name': '重复测试', 'qty': 1}
            try:
                r1 = ctx.request.post(f"{BASE}{path}", form=payload)
                r2 = ctx.request.post(f"{BASE}{path}", form=payload)
                # 若两次都 200 成功则疑似未做唯一性约束
                if r1.status == 200 and r2.status == 200:
                    add_finding("重复提交", "P2", path, f"相同 payload 重复提交均 200 (code={payload['code']})", "")
            except Exception:
                pass

        # ===== 新增19: 错误页与 500 =====
        print("\n[New-19] 触发常见 500 的 payload...")
        crash_payloads = [
            ('/material/save', {'code': None, 'name': 'x' * 100000, 'price': 'abc'}),
            ('/category/save', {'code': '', 'name': None, 'parent_id': 'abc'}),
            ('/supplier/save', {'code': None, 'name': None}),
            ('/customer/save', {'code': '', 'name': ''}),
            ('/in_order/save', {'supplier_id': 'NaN', 'total_qty': 'NaN'}),
        ]
        for path, payload in crash_payloads:
            try:
                r = ctx.request.post(f"{BASE}{path}", form=payload)
                if r.status == 500:
                    add_finding("崩溃 payload", "P1", path, f"异常 payload 触发 500", str(payload)[:200])
            except Exception:
                pass

        # ===== 新增20: 链接完整性 / 死链 =====
        print("\n[New-20] 链接完整性扫描...")
        for path in ['/material', '/in_order', '/out_order', '/supplier', '/customer',
                     '/category', '/report', '/admin/console']:
            try:
                r = ctx.request.get(f"{BASE}{path}")
                txt = r.text() if hasattr(r.text, '__call__') else r.text
                hrefs = re.findall(r'href="([^"]+)"', txt)
                bad = 0
                for h in hrefs:
                    if h.startswith('http') or h.startswith('#') or h.startswith('javascript:'):
                        continue
                    if h.startswith('/static') or h.startswith('/api'):
                        continue
                    if not h.startswith('/'):
                        continue
                # 统计无效 action=
                bad_action = re.findall(r'action="([^"]+)"', txt)
                for a in bad_action:
                    if a and not a.startswith('/') and not a.startswith('http') and '#' not in a:
                        add_finding("链接完整性", "P3", path, f"<form> 异常 action={a}", "")
            except Exception:
                pass

        # ===== 保存 =====
        with open(OUT_DIR / "findings.json", "w", encoding="utf-8") as f:
            json.dump(findings, f, ensure_ascii=False, indent=2)
        with open(OUT_DIR / "console_errors.json", "w", encoding="utf-8") as f:
            json.dump(console_errors, f, ensure_ascii=False, indent=2)
        with open(OUT_DIR / "network_errors.json", "w", encoding="utf-8") as f:
            json.dump(network_errors, f, ensure_ascii=False, indent=2)

        print("\n" + "=" * 60)
        print(f"[✓] 完成。共发现 {len(findings)} 个 BUG (新增 {len(findings) - (START_NUM - 1)} 条)")
        from collections import Counter
        c = Counter(b['category'] for b in findings)
        print("\n分类统计:")
        for cat, n in c.most_common():
            print(f"  {cat}: {n}")
        s = Counter(b['severity'] for b in findings)
        print("\n严重级别:")
        for sv, n in s.most_common():
            print(f"  {sv}: {n}")
        ctx.close()
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        # 即使出错也保存
        with open(OUT_DIR / "findings.json", "w", encoding="utf-8") as f:
            json.dump(findings, f, ensure_ascii=False, indent=2)
        print(f"[!] 异常退出: {e}; 已保存 {len(findings)} 条")
