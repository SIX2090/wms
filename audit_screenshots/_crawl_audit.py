# -*- coding: utf-8 -*-
"""WMS HTTP crawl audit: login then visit all module pages, record status/errors/CSRF."""
import re, sys, urllib.request, urllib.parse, http.cookiejar, json, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"
USER, PWD = "admin", "AAAA1234"

PAGES = [
    "/", "/index", "/change_password",
    # 基础资料
    "/material", "/material/add", "/category", "/unit", "/warehouse",
    "/supplier", "/customer", "/department", "/employee",
    # 采购
    "/purchase_request", "/purchase_request/add", "/purchase_order", "/purchase_order/add",
    "/in_order", "/in_order/add", "/in_order/push",
    # 销售
    "/sales_order", "/sales_order/add", "/out_order", "/out_order/add",
    "/after_sale_out", "/after_sale_out/add", "/sales_outbound_list", "/sales_outbound_selection",
    # 库存
    "/stock_query", "/check", "/transfer", "/adjustment", "/adjustment/add", "/opening_stock",
    # 委外/BOM/领料/合同
    "/subcontract", "/subcontract_issue", "/subcontract_receive", "/subcontract_progress",
    "/bom", "/requisition", "/contract",
    # 报表
    "/report", "/report_dashboard", "/purchase_report", "/sales_dashboard", "/sales_report",
    "/sales_trend_report", "/sales_price_analysis", "/sales_reconciliation_report",
    "/sales_execution_report", "/sales_outflow_report", "/sales_exceptions",
    # AI
    "/ai/acceptance", "/ai/agent_tasks", "/ai/business_quality", "/ai/data_retention",
    "/ai/demand_forecast", "/ai/document_jobs", "/ai/inventory_health",
    "/ai/location_recommendation", "/ai/material_alias", "/ai/ops_dashboard",
    "/ai/prelaunch", "/ai/purchase_workbench", "/ai/replenishment", "/ai/replenishment_smart",
    "/ai/sales_workbench", "/ai/supplier_evaluation", "/ai/warehouse_workbench",
    "/document_ocr", "/pending_documents", "/approval", "/alert",
    # 系统
    "/user", "/system_settings", "/backup", "/operation_audit", "/admin_console",
    "/admin/mobile_tokens", "/batch_import", "/label_template", "/mobile_scan", "/mobile_connect",
]

ERROR_MARKERS = ["Traceback (most recent call last)", "jinja2.exceptions", "werkzeug.exceptions",
                 "Internal Server Error", "500 Internal", "sqlalchemy.exc", "UndefinedError",
                 "TemplateNotFound", "BuildError"]

def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get_csrf(body):
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    return m.group(1) if m else ""

def fetch(opener, url, data=None, method="GET"):
    try:
        r = opener.open(url, data=data, timeout=15)
        return r.status, r.geturl(), r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, url, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return -1, url, str(e)

def main():
    results = []
    # --- 1. 未登录访问内页是否重定向到登录 ---
    anon = make_opener()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None
    anon_nr = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    st, _, body = fetch(anon_nr, BASE + "/material")
    anon_ok = st in (302, 303) or (st == 200 and "登录" in body and "用户名" in body)
    results.append(("ANON-REDIRECT", "/material", st, "OK" if anon_ok else "FAIL: 未登录可直接访问"))

    # --- 2. 登录 ---
    opener = make_opener()
    st, _, body = fetch(opener, BASE + "/login")
    csrf = get_csrf(body)
    data = urllib.parse.urlencode({"username": USER, "password": PWD, "usage_consent": "1",
                                   "login_mode": "admin", "csrf_token": csrf}).encode()
    st, url, body = fetch(opener, BASE + "/login", data=data, method="POST")
    logged_in = ("欢迎" in body or "工作台" in body or "首页" in body or "退出" in body) and st == 200
    results.append(("LOGIN", "/login", st, "OK" if logged_in else "FAIL: 登录失败 " + str(re.findall(r'class="alert[^"]*"[^>]*>([^<]+)<', body)[:3])))
    if not logged_in:
        report(results); return

    # --- 3. 遍历页面 ---
    for p in PAGES:
        st, url, body = fetch(opener, BASE + p)
        issues = []
        if st == -1:
            issues.append("请求异常: " + body[:200])
        elif st >= 500:
            issues.append(f"HTTP {st}")
        elif st == 404:
            issues.append("HTTP 404")
        elif st == 200:
            for mk in ERROR_MARKERS:
                if mk in body:
                    issues.append("页面含错误标记: " + mk)
            if "<form" in body and 'name="csrf_token"' not in body and "csrf_token" not in body:
                issues.append("表单缺少 CSRF token")
            if len(body) < 500:
                issues.append(f"页面内容过短({len(body)}B) 可能渲染异常")
        status = "; ".join(issues) if issues else "OK"
        results.append(("PAGE", p, st, status))
        if issues:
            print(f"[BUG?] {p} -> {st} {status}")

    report(results)

def report(results):
    print("\n===== 爬取审计汇总 =====")
    bad = [r for r in results if r[3] != "OK"]
    print(f"总检查项: {len(results)}, 异常: {len(bad)}")
    for kind, path, st, status in bad:
        print(f"  [{kind}] {path} HTTP={st} :: {status}")
    with open(r"c:\Users\Administrator\Desktop\wms\audit_screenshots\_crawl_result.json", "w", encoding="utf-8") as f:
        json.dump([{"type": k, "path": p, "http": s, "result": v} for k, p, s, v in results], f, ensure_ascii=False, indent=1)
    print("结果已写入 _crawl_result.json")

if __name__ == "__main__":
    main()
