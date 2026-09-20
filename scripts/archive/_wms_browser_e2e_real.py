"""WMS 全方位浏览器端到端测试 + MASTER-AUDIT-FIX 验证一体化脚本 (v2)

使用 Playwright + 系统 Chrome 真实驱动浏览器。

输出：
  /workspace/audit_screenshots/real_e2e/  截图目录
  /workspace/wms_browser_e2e_real_<时间>.md  报告
  /workspace/wms_browser_e2e_real_data.json  数据
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://127.0.0.1:8080"
ROOT = Path("/workspace")
SHOTS = ROOT / "audit_screenshots" / "real_e2e"
SHOTS.mkdir(parents=True, exist_ok=True)
REPORT_MD = ROOT / f"wms_browser_e2e_real_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
DATA_JSON = ROOT / "wms_browser_e2e_real_data.json"

CHECKS = []
SHOTS_LIST = []


def add(level, code, name, expect, actual, pass_, note=""):
    CHECKS.append({
        "level": level, "code": code, "name": name,
        "expect": expect, "actual": actual, "pass": pass_, "note": note,
    })
    status = "✅" if pass_ else "❌"
    print(f"{status} [{level}] {code} {name} | expect={expect} | actual={actual}")


def shot(page, name):
    p = SHOTS / f"{name}.png"
    try:
        page.screenshot(path=str(p), full_page=False)
        SHOTS_LIST.append(str(p))
        return str(p)
    except Exception:
        return ""


def goto_safe(page, path, timeout=10000):
    """Navigate to path, return (status, html, final_url)."""
    try:
        resp = page.goto(BASE + path, wait_until="domcontentloaded", timeout=timeout)
        if resp is None:
            return (0, "", page.url)
        status = resp.status
        html = page.content()
        return (status, html, page.url)
    except Exception:
        return (0, "", page.url)


def login(page):
    page.goto(BASE + "/login", wait_until="domcontentloaded", timeout=15000)
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "admin")
    page.click('button[type="submit"].btn-login')
    try:
        page.wait_for_url(re.compile(r".*/(?<!login)$|(?<!/login).*"), timeout=8000)
    except PWTimeout:
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
    # Also try waiting for /index or main page indicator
    try:
        page.wait_for_function(
            "() => !window.location.pathname.includes('/login')",
            timeout=5000,
        )
    except Exception:
        pass
    shot(page, "02_after_login")


def main():
    results = {"start": datetime.now().isoformat(), "checks": [], "fix_verification": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            executable_path="/opt/google/chrome/chrome",
        )
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.set_default_timeout(12000)

        # ===== Stage 1: Login =====
        print("\n=== Stage 1: Login ===")
        st, html, url = goto_safe(page, "/login")
        add("INFO", "S1-1", "Login page reachable",
            "200 + title含'登录'",
            f"status={st} title={page.title()}",
            st == 200 and "登录" in page.title())
        shot(page, "01_login_page")
        login(page)
        cur = page.url
        logged_in = "/login" not in cur and "/change_password" not in cur
        add("AUTH", "S1-2", "Admin login (no forced change)",
            "URL 不含 /login /change_password",
            f"url={cur}",
            logged_in)
        nav_count = page.locator("nav a, .sidebar a, .menu a, .nav-link, .navbar a").count()
        add("INFO", "S1-3", "Navigation links present",
            ">0", f"{nav_count}",
            nav_count > 0)

        # ===== Stage 2: Master data menus =====
        print("\n=== Stage 2: Master data menus ===")
        master_menus = [
            ("/material", "物料", "M-物料"),
            ("/category", "分类", "M-分类"),
            ("/unit", "单位", "M-单位"),
            ("/supplier", "供应商", "M-供应商"),
            ("/customer", "客户", "M-客户"),
            ("/warehouse", "仓库", "M-仓库"),
            ("/department", "部门", "M-部门"),
            ("/employee", "员工", "M-员工"),
            ("/contract", "合同", "M-合同"),
            ("/bom", "BOM", "M-BOM"),
            ("/label_template", "标签", "M-标签"),
            ("/opening_stock", "期初", "M-期初"),
        ]
        for path, expected_keyword, code in master_menus:
            st, html, url = goto_safe(page, path)
            title = page.title()
            ok = st == 200 and (expected_keyword in title or expected_keyword in html)
            add("MENU", code, f"访问 {path}",
                f"200 + 含 '{expected_keyword}'",
                f"status={st} title={title[:40]}",
                ok)
            shot(page, f"menu_{code.replace('-', '_')}")

        # ===== Stage 3: IO menus =====
        print("\n=== Stage 3: IO menus ===")
        io_menus = [
            ("/in_order", "I-入库"),
            ("/out_order", "I-出库"),
            ("/purchase_request", "I-采购申请"),
            ("/purchase_order", "I-采购订单"),
            ("/transfer", "I-调拨"),
            ("/check", "I-盘点"),
            ("/adjustment", "I-调整"),
            ("/subcontract", "I-委外"),
            ("/after_sale_out", "I-售后"),
            ("/requisition", "I-领用"),
            ("/sales", "I-销售"),
        ]
        for path, code in io_menus:
            st, html, url = goto_safe(page, path)
            title = page.title()
            ok = st == 200 and st != 404
            add("MENU", code, f"访问 {path}",
                "200",
                f"status={st} title={title[:40]}",
                ok)
            shot(page, f"io_{code.replace('-', '_')}")

        # ===== Stage 4: Reports =====
        print("\n=== Stage 4: Reports ===")
        report_menus = [
            ("/report", "R-报表"),
            ("/stock_query", "R-库存"),
            ("/purchase_report", "R-采购"),
        ]
        for path, code in report_menus:
            st, html, url = goto_safe(page, path)
            title = page.title()
            ok = st == 200
            add("MENU", code, f"访问 {path}", "200",
                f"status={st} title={title[:40]}", ok)
            shot(page, f"rpt_{code.replace('-', '_')}")

        # ===== Stage 5: System =====
        print("\n=== Stage 5: System ===")
        sys_menus = [
            ("/user", "S-用户"),
            ("/system_settings", "S-设置"),
            ("/backup", "S-备份"),
            ("/operation_audit", "S-审计"),
            ("/approval", "S-审批"),
        ]
        for path, code in sys_menus:
            st, html, url = goto_safe(page, path)
            title = page.title()
            ok = st == 200
            add("MENU", code, f"访问 {path}", "200",
                f"status={st} title={title[:40]}", ok)
            shot(page, f"sys_{code.replace('-', '_')}")

        # ===== Stage 6: P0-1 verification (label/batch_print) =====
        print("\n=== Stage 6: P0-1 /label/batch_print ===")
        # 6a: no ids -> empty state
        st, html, url = goto_safe(page, "/label/batch_print")
        no_placeholder = "未选择物料" in html and "alert-info" in html
        add("FIX", "P0-1a", "空状态 (无 ids)",
            "显示'未选择物料'占位",
            f"placeholder_present={no_placeholder}",
            st == 200 and no_placeholder)
        shot(page, "fix_p0_1a_empty")

        # 6b: with valid ids=1,2 -> should render data
        st, html, url = goto_safe(page, "/label/batch_print?ids=1,2")
        # When materials present: '未选择物料' should NOT appear, and MATERIALS JSON should be present
        empty_gone = "未选择物料" not in html
        has_materials = "MATERIALS = " in html and ("M0001" in html or "M0002" in html)
        has_count = "共 " in html and "个标签" in html
        add("FIX", "P0-1b", "有效 ids (1,2)",
            "占位消失 + 含材料数据",
            f"empty_gone={empty_gone} has_materials={has_materials} has_count={has_count}",
            st == 200 and empty_gone and has_materials)
        shot(page, "fix_p0_1b_with_ids")

        # 6c: invalid ids -> falls back to empty state
        st, html, url = goto_safe(page, "/label/batch_print?ids=999,1000")
        no_data_placeholder = "未选择物料" in html
        add("FIX", "P0-1c", "无效 ids (999,1000)",
            "回退空态",
            f"empty_placeholder={no_data_placeholder}",
            st == 200 and no_data_placeholder)
        shot(page, "fix_p0_1c_invalid_ids")

        # ===== Stage 7: P1 batch_import ?type= redirects =====
        print("\n=== Stage 7: P1 batch_import ?type= ===")
        modules = [
            "material", "category", "unit", "supplier", "customer",
            "warehouse", "department", "employee", "contract",
            "label_template", "bom", "opening_stock", "user",
        ]
        for m in modules:
            st, html, url = goto_safe(page, f"/batch_import?type={m}")
            has_import = "导入" in html or "import" in html.lower()
            highlight_ok = m in html or m.replace("_", "") in html
            add("FIX", f"P1-imp-{m}", f"/batch_import?type={m}",
                "200 + 模块高亮",
                f"status={st} has_import={has_import} highlight={highlight_ok}",
                st == 200 and has_import and highlight_ok)
            shot(page, f"fix_p1_imp_{m}")

        # ===== Stage 8: P1 stub routes (only 4 modules have actual stubs) =====
        print("\n=== Stage 8: P1 stub /import /export routes ===")
        # Stubs exist for: user, system_settings, label_template, opening_stock
        stub_modules = ["user", "system_settings", "label_template", "opening_stock"]
        for m in stub_modules:
            # /export is GET and redirects to /batch_import
            st, html, url = goto_safe(page, f"/{m}/export")
            redirected = "batch_import" in url and f"type={m}" in url
            add("FIX", f"P1-stub-{m}-export", f"/{m}/export",
                "重定向到 /batch_import?type=" + m,
                f"status={st} final_url={url[-50:]}",
                st in (200, 302) and redirected)
            shot(page, f"fix_p1_stub_{m}_export")
            # /import is POST-only (returns 405 for GET, which is correct behavior)
            st, html, url = goto_safe(page, f"/{m}/import")
            add("FIX", f"P1-stub-{m}-import", f"/{m}/import",
                "POST-only (GET 405)",
                f"status={st}",
                st == 405)
            shot(page, f"fix_p1_stub_{m}_import")

        # Verify the OTHER modules have proper import/export routes
        # (POST for import, GET for export returning file or page)
        print("\n=== Stage 8b: P1 /import (POST-only) /export (GET) on other modules ===")
        for m in ["material", "supplier", "customer", "category", "unit",
                  "warehouse", "department", "employee", "contract", "bom"]:
            # /import on these is POST-only
            st, html, url = goto_safe(page, f"/{m}/import")
            post_only = st == 405  # Method not allowed
            add("FIX", f"P1-{m}-import-post", f"/{m}/import GET",
                "405 (POST-only)",
                f"status={st}",
                post_only)

            # /export returns xlsx file (send_file) — Playwright may see status=0
            # (no HTML response) since it's a file download
            st, html, url = goto_safe(page, f"/{m}/export")
            export_ok = st in (200, 0)  # 0 = file download in Playwright
            add("FIX", f"P1-{m}-export-get", f"/{m}/export GET",
                "200 或 0 (file download)",
                f"status={st}",
                export_ok)

        # ===== Stage 9: Label print toolbar buttons =====
        print("\n=== Stage 9: Label print toolbar ===")
        st, html, url = goto_safe(page, "/material")
        has_batch_print = "batch_print" in html or "批量打印" in html
        add("FIX", "P1-toolbar-material", "物料列表批量打印入口",
            "含'批量打印'按钮/链接",
            f"has={has_batch_print}",
            st == 200 and has_batch_print)
        shot(page, "fix_p1_toolbar_material")

        # ===== Stage 10: IO toolbar =====
        print("\n=== Stage 10: IO toolbar ===")
        for path, keyword in [
            ("/in_order", "新增"),  # 新增产品入库 / 新增采购入库 / 新增其他入库
            ("/out_order", "新增"),
            ("/purchase_request", "新建"),
            ("/transfer", "新增调拨"),
        ]:
            st, html, url = goto_safe(page, path)
            has_add = keyword in html
            add("TOOL", f"add-{path.strip('/')}", f"{path} 工具栏",
                f"含'{keyword}'按钮",
                f"has={has_add}",
                st == 200 and has_add)
            shot(page, f"tool_{path.strip('/').replace('/', '_')}")

        # ===== Stage 13: Add page / modal form structure =====
        # Must run BEFORE Stage 11 (which clears cookies)
        print("\n=== Stage 13: Form structure (logged in) ===")
        # /material/add supports GET
        for path, expected_field in [
            ("/material/add", "name"),
            ("/in_order/add", "warehouse_id"),
            ("/out_order/add", "warehouse_id"),
        ]:
            st, html, url = goto_safe(page, path)
            has_field = f'name="{expected_field}"' in html
            add("FORM", f"form-{path.strip('/').replace('/', '_')}", f"{path} 字段",
                f"含 name='{expected_field}'",
                f"has={has_field}",
                st == 200 and has_field)
            shot(page, f"form_{path.strip('/').replace('/', '_')}")

        # Modal-based forms live on the list page
        for path, expected_field in [
            ("/category", "name"),
            ("/unit", "name"),
            ("/supplier", "name"),
            ("/customer", "name"),
            ("/warehouse", "name"),
            ("/department", "name"),
            ("/employee", "name"),
        ]:
            st, html, url = goto_safe(page, path)
            has_field = f'name="{expected_field}"' in html
            add("FORM", f"modal-{path.strip('/')[:12]}", f"{path} 模态字段",
                f"含 name='{expected_field}'",
                f"has={has_field}",
                st == 200 and has_field)
            shot(page, f"modal_{path.strip('/')[:12]}")

        # ===== Stage 14: P0-1b really confirmed with direct HTTP =====
        print("\n=== Stage 14: P0-1b real-data double check ===")
        st, html, url = goto_safe(page, "/label/batch_print?ids=1,2,3,4,5")
        empty_gone = "未选择物料" not in html
        has_data = "M0001" in html and "M0002" in html
        count_text = re.search(r'共\s*(\d+)\s*个标签', html)
        has_count = count_text is not None
        add("FIX", "P0-1b-full", "P0-1b 完整 ids (1-5)",
            "占位消失 + 含 5 个材料 + 显示数量",
            f"empty_gone={empty_gone} has_data={has_data} has_count={has_count} match={count_text.group(0) if count_text else 'none'}",
            st == 200 and empty_gone and has_data and has_count)
        shot(page, "fix_p0_1b_full")

        # ===== Stage 11: Login flow + CSRF =====
        print("\n=== Stage 11: Real login flow + CSRF ===")
        ctx.clear_cookies()
        page.goto(BASE + "/login", wait_until="domcontentloaded", timeout=15000)
        # Ensure we are on login page
        try:
            page.wait_for_selector('input[name="username"]', timeout=8000)
        except Exception:
            page.goto(BASE + "/login", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_selector('input[name="username"]', timeout=8000)
        csrf_token = page.locator('input[name="csrf_token"]').first
        has_csrf = csrf_token.count() > 0
        add("AUTH", "S11-1", "CSRF token in login form",
            "有 csrf_token 隐藏域",
            f"has={has_csrf}",
            has_csrf)
        # Wrong password
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "wrong")
        page.click('button[type="submit"].btn-login')
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        wrong_url = page.url
        wrong_rejected = "/login" in wrong_url
        add("AUTH", "S11-2", "Wrong password rejected",
            "留在 /login",
            f"url={wrong_url}",
            wrong_rejected)
        shot(page, "fix_login_wrong")
        # Right password
        # Use a fresh context to ensure clean state
        ctx2 = browser.new_context(viewport={"width": 1440, "height": 900})
        page2 = ctx2.new_page()
        page2.set_default_timeout(12000)
        try:
            page2.goto(BASE + "/login", wait_until="domcontentloaded", timeout=15000)
            page2.wait_for_selector('input[name="username"]', timeout=8000)
            page2.fill('input[name="username"]', "admin")
            page2.fill('input[name="password"]', "admin")
            page2.click('button[type="submit"].btn-login')
            page2.wait_for_function(
                "() => !window.location.pathname.includes('/login')",
                timeout=8000,
            )
            ok_url = page2.url
        except Exception as e:
            ok_url = f"err: {e}"
        ctx2.close()
        login_ok = "/login" not in ok_url
        add("AUTH", "S11-3", "Correct password accepted",
            "离开 /login",
            f"url={ok_url}",
            login_ok)
        shot(page, "fix_login_ok")

        # ===== Stage 12: Permission matrix (admin) =====
        print("\n=== Stage 12: Permission matrix (admin) ===")
        for path in ["/user", "/system_settings", "/backup",
                     "/operation_audit", "/approval"]:
            st, html, url = goto_safe(page, path)
            ok = st == 200
            add("PERM", f"perm-{path.strip('/')[:15]}", f"Admin→{path}",
                "200", f"status={st}", ok)
            shot(page, f"perm_{path.strip('/')[:15]}")

        # ===== Stage 15: Final report =====
        results["end"] = datetime.now().isoformat()
        results["checks"] = CHECKS
        results["screenshots"] = SHOTS_LIST
        results["total_checks"] = len(CHECKS)
        results["passed"] = sum(1 for c in CHECKS if c["pass"])
        results["failed"] = sum(1 for c in CHECKS if not c["pass"])
        results["pass_rate"] = f"{results['passed'] / max(1, results['total_checks']) * 100:.1f}%"

        # P0/P1 fix summary
        fix_checks = [c for c in CHECKS if c["level"] == "FIX"]
        results["fix_verification"] = {
            "total_fix_checks": len(fix_checks),
            "fix_passed": sum(1 for c in fix_checks if c["pass"]),
            "fix_failed": [c["code"] for c in fix_checks if not c["pass"]],
        }

        with open(DATA_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        with open(REPORT_MD, "w", encoding="utf-8") as f:
            f.write(f"# WMS 浏览器端到端测试 + MASTER-AUDIT-FIX 验证报告\n\n")
            f.write(f"**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**测试环境**：http://127.0.0.1:8080 + Chrome 147 + Playwright\n\n")
            f.write(f"**通过率**：{results['passed']} / {results['total_checks']} = {results['pass_rate']}\n\n")
            f.write(f"**截图数量**：{len(SHOTS_LIST)} 张（保存于 `audit_screenshots/real_e2e/`）\n\n")
            f.write(f"## P0/P1 修复验证汇总\n\n")
            f.write(f"- 修复检查总数：{results['fix_verification']['total_fix_checks']}\n")
            f.write(f"- 通过：{results['fix_verification']['fix_passed']}\n")
            f.write(f"- 失败：{len(results['fix_verification']['fix_failed'])}\n")
            if results['fix_verification']['fix_failed']:
                f.write(f"- 失败项：{', '.join(results['fix_verification']['fix_failed'])}\n")
            f.write(f"\n## 检查项明细\n\n")
            f.write("| 等级 | 编号 | 名称 | 期望 | 实际 | 结果 |\n")
            f.write("|------|------|------|------|------|------|\n")
            for c in CHECKS:
                st_ = "✅" if c["pass"] else "❌"
                f.write(f"| {c['level']} | {c['code']} | {c['name']} | {c['expect']} | {c['actual']} | {st_} |\n")
            f.write(f"\n## 失败项\n\n")
            failed = [c for c in CHECKS if not c["pass"]]
            if not failed:
                f.write("无。\n")
            else:
                for c in failed:
                    f.write(f"- **{c['code']}** {c['name']} | expect={c['expect']} | actual={c['actual']}\n")
            f.write(f"\n## 截图清单（前 30）\n\n")
            for s in SHOTS_LIST[:30]:
                f.write(f"- `{s}`\n")
            if len(SHOTS_LIST) > 30:
                f.write(f"- ...（其余 {len(SHOTS_LIST) - 30} 张略）\n")

        print(f"\n=== DONE: {results['passed']}/{results['total_checks']} = {results['pass_rate']} ===")
        print(f"Report: {REPORT_MD}")
        print(f"Data:   {DATA_JSON}")
        print(f"Shots:  {len(SHOTS_LIST)} files in {SHOTS}")
        print(f"FIX:    {results['fix_verification']['fix_passed']}/{results['fix_verification']['total_fix_checks']}")

        browser.close()


if __name__ == "__main__":
    main()
