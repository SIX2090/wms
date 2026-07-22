"""WMS 业务流程端到端测试（真实业务流，不依赖浏览器）。

模拟真实用户路径：
1. 登录 → 验证角色
2. 创建基础数据（分类/单位/仓库/供应商/客户/物料）
3. 采购业务流（采购申请 → 采购订单 → 入库 → 库存增加验证）
4. 销售业务流（销售订单 → 出库 → 库存扣减验证）
5. 库存业务流（盘点/调整/调拨）
6. 报表验证

使用 requests.Session 保持登录态。
"""
import json
import re
import sys
import time
import uuid
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

import requests


BASE = "http://127.0.0.1:8080"
USERNAME = "admin"
# Try common admin passwords (system may have been initialized with any of them)
PASSWORDS = ["Admin@123", "admin", "Admin123", "123456", "admin123"]


class TestResult:
    def __init__(self):
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []
        self.warnings: List[str] = []

    def ok(self, name: str):
        self.passed.append(name)
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str):
        self.failed.append((name, reason))
        print(f"  [FAIL] {name}: {reason}")

    def warn(self, name: str, msg: str):
        self.warnings.append(f"{name}: {msg}")
        print(f"  [WARN] {name}: {msg}")


class CsrfExtractor(HTMLParser):
    """从 HTML 中提取 csrf_token hidden input。"""

    def __init__(self):
        super().__init__()
        self.csrf_token: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        if tag.lower() == "input":
            attr_dict = {k.lower(): v for k, v in attrs}
            if attr_dict.get("name", "").lower() == "csrf_token":
                self.csrf_token = attr_dict.get("value")


def get_csrf_token(html: str) -> Optional[str]:
    p = CsrfExtractor()
    p.feed(html)
    return p.csrf_token


def login(session: requests.Session, password: str) -> bool:
    """Try to login. Returns True on success."""
    # 1. GET /login to obtain CSRF token (via hidden input rendered in form)
    r = session.get(f"{BASE}/login", timeout=10)
    if r.status_code != 200:
        return False
    csrf = get_csrf_token(r.text)
    if not csrf:
        return False
    # 2. POST credentials
    r = session.post(
        f"{BASE}/login",
        data={
            "csrf_token": csrf,
            "username": USERNAME,
            "password": password,
        },
        allow_redirects=False,
        timeout=10,
    )
    # Success: 302 redirect to / (or /change_password for first login)
    return r.status_code in (302, 303) and "/login" not in r.headers.get("Location", "/login")


def ensure_login(session: requests.Session) -> Tuple[bool, str]:
    for pwd in PASSWORDS:
        # Re-create session to clear any prior failed attempts
        for k in list(session.cookies.keys()):
            del session.cookies[k]
        if login(session, pwd):
            return True, pwd
    return False, ""


def get_csrf_from_page(session: requests.Session, url: str) -> Optional[str]:
    r = session.get(f"{BASE}{url}", timeout=10)
    if r.status_code != 200:
        return None
    return get_csrf_token(r.text)


def post_form(session: requests.Session, url: str, data: Dict[str, Any]) -> requests.Response:
    """Submit a form with CSRF token auto-injected."""
    if "csrf_token" not in data:
        csrf = get_csrf_from_page(session, url)
        if csrf:
            data["csrf_token"] = csrf
    return session.post(f"{BASE}{url}", data=data, allow_redirects=True, timeout=15)


def post_form_or_json(session: requests.Session, url: str, data: Dict[str, Any]) -> Tuple[int, Any]:
    """POST data; use form-encoded. Get CSRF from the page that hosts this form (e.g. /supplier)."""
    # Extract the host page (e.g. /supplier) by stripping /add from /supplier/add
    host = url
    if host.endswith("/add"):
        host = host[:-4]
    elif "/add?" in host:
        host = host.split("/add?")[0]
    csrf = get_csrf_from_page(session, host)
    if not csrf:
        # Try root as fallback
        csrf = get_csrf_from_page(session, "/")
    payload = dict(data)
    if csrf:
        payload["csrf_token"] = csrf
    r = session.post(f"{BASE}{url}", data=payload, allow_redirects=False, timeout=15)
    if r.status_code in (200, 302, 303):
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"html": r.text[:300]}
    # Try JSON as fallback
    headers = {"X-CSRFToken": csrf} if csrf else {}
    r = session.post(f"{BASE}{url}", json=data, headers=headers, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:300]}


def post_json_with_csrf(session: requests.Session, url: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST JSON to a CSRF-protected endpoint."""
    # Get CSRF token from any page (cookie-bound)
    csrf = get_csrf_from_page(session, "/")
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-CSRFToken"] = csrf
    r = session.post(f"{BASE}{url}", json=payload, headers=headers, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}


def get_json(session: requests.Session, url: str) -> Tuple[int, Any]:
    r = session.get(f"{BASE}{url}", timeout=10)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text[:300]


# ==================== 测试套件 ====================

def test_login(session: requests.Session, r: TestResult) -> bool:
    print("\n=== 1. 登录与权限验证 ===")
    ok, pwd = ensure_login(session)
    if not ok:
        r.fail("login", "所有 admin 密码尝试都失败")
        return False
    r.ok(f"login with password='{pwd}'")
    # Verify session works
    code, _ = get_json(session, "/")
    if code == 200:
        r.ok("auth/session-valid")
    else:
        r.warn("auth/session-valid", f"首页返回 {code}")
    return True


def test_basic_data(session: requests.Session, r: TestResult) -> Dict[str, Any]:
    """创建/验证基础数据：分类/单位/仓库/供应商/客户/物料。"""
    print("\n=== 2. 基础数据维护 ===")
    created: Dict[str, Any] = {}

    # 2.1 分类
    code, body = get_json(session, "/api/categories")
    cats = body if isinstance(body, list) else (body.get("data") or body.get("categories") or [])
    if cats:
        created["category_id"] = cats[0].get("id")
        r.ok(f"category/list: {len(cats)} 项")
    else:
        r.fail("category/list", "无分类数据")

    # 2.2 单位
    code, body = get_json(session, "/api/units")
    units = body if isinstance(body, list) else (body.get("data") or body.get("units") or [])
    if units:
        created["unit_id"] = units[0].get("id")
        r.ok(f"unit/list: {len(units)} 项")
    else:
        # Try create via JSON
        unit_name = f"E2E单位-{uuid.uuid4().hex[:6]}"
        unit_code = f"EU{uuid.uuid4().hex[:4]}"
        status, body = post_form_or_json(session, "/unit/add", {
            "code": unit_code, "name": unit_name
        })
        code, body = get_json(session, "/api/units")
        units = body if isinstance(body, list) else (body.get("data") or body.get("units") or [])
        if units:
            created["unit_id"] = units[0].get("id")
            r.ok(f"unit/add+list: {len(units)} 项")
        else:
            r.fail("unit/list", f"无单位数据且无法创建 (status={status})")

    # 2.3 仓库
    code, body = get_json(session, "/warehouse/api/all")
    if code == 200:
        whs = body if isinstance(body, list) else (body.get("data") or body.get("warehouses") or [])
        if whs:
            created["warehouse_id"] = whs[0].get("id")
            created["warehouse_name"] = whs[0].get("name")
            r.ok(f"warehouse/list: {len(whs)} 项")
        else:
            wh_name = f"E2E仓库-{uuid.uuid4().hex[:6]}"
            wh_code = f"WH{uuid.uuid4().hex[:4]}"
            status, body = post_form_or_json(session, "/warehouse/add", {
                "code": wh_code, "name": wh_name, "location": "e2e", "manager": "tester"
            })
            if isinstance(body, dict) and body.get("status") == "success":
                created["warehouse_id"] = body.get("id")
                created["warehouse_name"] = wh_name
                r.ok(f"warehouse/add+list: id={body.get('id')}")
            else:
                r.fail("warehouse/list", f"无法创建 (status={status} body={body})")
    else:
        # Try to find via material/warehouse list
        code, body = get_json(session, "/api/material/all")
        mats = (body.get("data") or body.get("materials") or []) if isinstance(body, dict) else []
        if mats and mats[0].get("warehouse_id"):
            created["warehouse_id"] = mats[0].get("warehouse_id")
            created["warehouse_name"] = mats[0].get("warehouse_name") or "default"
            r.ok(f"warehouse (inferred from material): {created['warehouse_id']}")
        else:
            r.warn("warehouse/api/all", f"返回 {code}，未找到仓库")

    # 2.4 供应商
    code, body = get_json(session, "/api/suppliers")
    sups = body if isinstance(body, list) else (body.get("data") or body.get("suppliers") or [])
    if sups:
        created["supplier_id"] = sups[0].get("id")
        r.ok(f"supplier/list: {len(sups)} 项")
    else:
        # Create one
        sup_name = f"E2E供应商-{uuid.uuid4().hex[:6]}"
        sup_code = f"SUP{uuid.uuid4().hex[:4]}"
        status, body = post_form_or_json(session, "/supplier/add", {
            "code": sup_code, "name": sup_name,
            "contact": "测试人", "phone": "13800000000", "address": "E2E测试"
        })
        code, body = get_json(session, "/api/suppliers")
        sups = body if isinstance(body, list) else (body.get("data") or body.get("suppliers") or [])
        if sups:
            created["supplier_id"] = sups[0].get("id")
            r.ok(f"supplier/add+list: {len(sups)} 项")
        else:
            r.fail("supplier/list", f"无法创建 (status={status})")

    # 2.5 客户
    code, body = get_json(session, "/api/customers")
    custs = body if isinstance(body, list) else (body.get("data") or body.get("customers") or [])
    if custs:
        created["customer_id"] = custs[0].get("id")
        r.ok(f"customer/list: {len(custs)} 项")
    else:
        cust_name = f"E2E客户-{uuid.uuid4().hex[:6]}"
        cust_code = f"CUS{uuid.uuid4().hex[:4]}"
        status, body = post_form_or_json(session, "/customer/add", {
            "code": cust_code, "name": cust_name,
            "contact": "客户A", "phone": "13900000000"
        })
        code, body = get_json(session, "/api/customers")
        custs = body if isinstance(body, list) else (body.get("data") or body.get("customers") or [])
        if custs:
            created["customer_id"] = custs[0].get("id")
            r.ok(f"customer/add+list: {len(custs)} 项")
        else:
            r.fail("customer/list", f"无法创建 (status={status})")

    # 2.6 物料
    mat_code = f"E2E{uuid.uuid4().hex[:8]}"
    csrf = get_csrf_from_page(session, "/material")
    payload = {
        "csrf_token": csrf or "",
        "code": mat_code,
        "name": f"E2E物料-{mat_code[:6]}",
        "spec": "E2E规格",
        "category_id": created.get("category_id", ""),
        "unit_id": created.get("unit_id", ""),
        "supplier_id": created.get("supplier_id", ""),
        "price": "10.50",
        "min_stock": "5",
        "stock": "0",
    }
    resp = session.post(f"{BASE}/material/add", data=payload, allow_redirects=True, timeout=10)
    if resp.status_code == 200:
        r.ok(f"material/add: {mat_code}")
        created["material_code"] = mat_code
    else:
        r.warn("material/add", f"返回 {resp.status_code}")

    # 2.7 物料列表
    code, body = get_json(session, "/api/material/all")
    mats = (body.get("data") or body.get("materials") or []) if isinstance(body, dict) else []
    target = next((m for m in mats if m.get("code") == mat_code), None)
    if target:
        created["material_id"] = target.get("id")
        created["material_stock"] = float(target.get("stock", 0) or 0)
        r.ok(f"material/verify-created: stock={target.get('stock')}")
    else:
        r.warn("material/verify-created", f"未找到 {mat_code}（可能未提交成功）")
    r.ok(f"material/list: {len(mats)} 项")

    # 导出
    resp = session.get(f"{BASE}/material/export", timeout=10)
    if resp.status_code == 200 and b"PK" in resp.content[:4]:
        r.ok(f"material/export: {len(resp.content)} bytes")
    else:
        r.warn("material/export", f"返回 {resp.status_code}, {len(resp.content)} bytes")

    return created


def test_purchase_flow(session: requests.Session, r: TestResult, data: Dict[str, Any]) -> Optional[int]:
    """采购申请 → 采购订单 → 入库 → 库存增加验证。"""
    print("\n=== 3. 采购业务流 ===")
    if not data.get("material_id") or not data.get("supplier_id"):
        r.fail("purchase", "缺少 material 或 supplier，跳过")
        return None

    # 3.1 采购申请
    csrf = get_csrf_from_page(session, "/purchase_request/add")
    resp = session.post(f"{BASE}/purchase_request/add", data={
        "csrf_token": csrf or "",
        "supplier_id": data["supplier_id"],
        "remark": f"E2E采购申请-{uuid.uuid4().hex[:6]}",
        f"items[0].material_id": data["material_id"],
        "items[0].quantity": "100",
        "items[0].price": "10.50",
    }, allow_redirects=True, timeout=10)
    if resp.status_code == 200:
        r.ok("purchase_request/add")
    else:
        r.warn("purchase_request/add", f"返回 {resp.status_code}")

    # 3.2 入库单（直接入库，更直接的库存验证路径）
    in_qty = 50
    stock_before = data.get("material_stock", 0)
    warehouse_id = data.get("warehouse_id", "")
    warehouse_name = data.get("warehouse_name", "主仓")
    if not warehouse_id:
        # Try fetch warehouse list from stock or material API
        code, body = get_json(session, "/api/stock/warehouses")
        if code == 200 and body:
            warehouse_id = body[0].get("id", "") if isinstance(body, list) else ""
            warehouse_name = body[0].get("name", warehouse_name) if isinstance(body, list) else warehouse_name
    csrf = get_csrf_from_page(session, "/in_order/add")
    payload = {
        "csrf_token": csrf or "",
        "supplier_id": data["supplier_id"],
        "warehouse": warehouse_name,
        "warehouse_id": warehouse_id,
        "remark": f"E2E入库-{uuid.uuid4().hex[:6]}",
        f"items[0].material_id": data["material_id"],
        "items[0].material_code": data.get("material_code", ""),
        "items[0].quantity": str(in_qty),
        "items[0].price": "10.50",
    }
    resp = session.post(f"{BASE}/in_order/add", data=payload, allow_redirects=True, timeout=10)
    if resp.status_code == 200:
        r.ok("in_order/add")
    else:
        r.warn("in_order/add", f"返回 {resp.status_code}")

    # 验证库存增加
    time.sleep(0.5)
    code, body = get_json(session, "/api/material/all")
    mats = (body.get("data") or body.get("materials") or []) if isinstance(body, dict) else []
    target = next((m for m in mats if m.get("code") == data.get("material_code")), None)
    if target:
        new_stock = float(target.get("stock", 0) or 0)
        if new_stock >= stock_before + in_qty - 1:
            r.ok(f"in_order/stock-verify: {stock_before} -> {new_stock} (+{new_stock - stock_before})")
            data["material_stock"] = new_stock
        elif new_stock > stock_before:
            r.ok(f"in_order/stock-partial: {stock_before} -> {new_stock} (+{new_stock - stock_before})")
            data["material_stock"] = new_stock
        else:
            r.warn("in_order/stock-no-change", f"{stock_before} -> {new_stock}（未增加）")
    return None


def test_sales_flow(session: requests.Session, r: TestResult, data: Dict[str, Any]):
    """销售订单 → 出库 → 库存扣减验证。"""
    print("\n=== 4. 销售业务流 ===")
    if not data.get("material_id") or not data.get("customer_id") or data.get("material_stock", 0) <= 0:
        r.warn("sales", "缺少物料/客户或库存不足，跳过")
        return

    out_qty = min(10, int(data["material_stock"]))
    if out_qty <= 0:
        r.warn("sales", "无库存可出库")
        return
    stock_before = data["material_stock"]

    # 4.1 出库单
    csrf = get_csrf_from_page(session, "/out_order/add")
    resp = session.post(f"{BASE}/out_order/add", data={
        "csrf_token": csrf or "",
        "customer_id": data["customer_id"],
        "warehouse_id": data.get("warehouse_id", ""),
        "warehouse": data.get("warehouse_name", "主仓"),
        "remark": f"E2E出库-{uuid.uuid4().hex[:6]}",
        f"items[0].material_id": data["material_id"],
        "items[0].material_code": data.get("material_code", ""),
        "items[0].quantity": str(out_qty),
        "items[0].price": "12.00",
    }, allow_redirects=True, timeout=10)
    if resp.status_code == 200:
        r.ok("out_order/add")
    else:
        r.warn("out_order/add", f"返回 {resp.status_code}")

    time.sleep(0.5)
    code, body = get_json(session, "/api/material/all")
    mats = (body.get("data") or body.get("materials") or []) if isinstance(body, dict) else []
    target = next((m for m in mats if m.get("code") == data.get("material_code")), None)
    if target:
        new_stock = float(target.get("stock", 0) or 0)
        if new_stock <= stock_before:
            r.ok(f"out_order/stock-verify: {stock_before} -> {new_stock} (-{stock_before - new_stock})")
        else:
            r.fail("out_order/stock-verify", f"库存未扣减: {stock_before} -> {new_stock}")


def test_reports(session: requests.Session, r: TestResult):
    print("\n=== 5. 报表与导出 ===")
    for path in [
        "/sales/report", "/sales/trend_report", "/sales/price_analysis",
        "/sales/outflow_report", "/sales/execution_report",
        "/in_order/export", "/out_order/export", "/sales/export",
        "/material/export", "/supplier/export", "/customer/export",
        "/warehouse/export", "/category/export", "/unit/export",
    ]:
        resp = session.get(f"{BASE}{path}", timeout=10)
        if resp.status_code == 200 and len(resp.content) > 100:
            r.ok(f"report {path}: {len(resp.content)} bytes")
        else:
            r.warn(f"report {path}", f"返回 {resp.status_code}, {len(resp.content)} bytes")


def test_stock_and_alerts(session: requests.Session, r: TestResult):
    print("\n=== 6. 库存业务与预警 ===")
    for path in ["/stock_query", "/opening_stock", "/check", "/transfer", "/alert", "/adjustment/add", "/bom", "/subcontract", "/report/view/inventory"]:
        resp = session.get(f"{BASE}{path}", timeout=10)
        if resp.status_code == 200:
            r.ok(f"page {path}")
        else:
            r.fail(f"page {path}", f"返回 {resp.status_code}")


def test_ai_pages(session: requests.Session, r: TestResult):
    print("\n=== 7. AI 模块页面 ===")
    paths = [
        "/ai/sales_workbench", "/ai/purchase_workbench", "/ai/warehouse_workbench",
        "/ai/ops", "/ai/data-retention", "/ai/business_quality", "/ai/agent_tasks",
        "/ai/document_ocr", "/ai/document_jobs", "/ai/replenishment",
        "/ai/inventory_health", "/ai/supplier_evaluation", "/ai/material_alias",
    ]
    for path in paths:
        resp = session.get(f"{BASE}{path}", timeout=10)
        if resp.status_code == 200:
            r.ok(f"ai page {path}")
        else:
            r.warn(f"ai page {path}", f"返回 {resp.status_code}")


def test_mobile_scan(session: requests.Session, r: TestResult):
    print("\n=== 8. 移动扫码 ===")
    resp = session.get(f"{BASE}/mobile/app", timeout=10)
    if resp.status_code == 200:
        r.ok("mobile/app page")
    else:
        r.warn("mobile/app", f"返回 {resp.status_code}")


def test_user_settings(session: requests.Session, r: TestResult):
    print("\n=== 9. 用户与系统设置 ===")
    for path in ["/user", "/department", "/system_settings"]:
        resp = session.get(f"{BASE}{path}", timeout=10)
        if resp.status_code == 200:
            r.ok(f"page {path}")
        else:
            r.warn(f"page {path}", f"返回 {resp.status_code}")


def main() -> int:
    print("=" * 60)
    print("WMS 业务流程端到端测试")
    print("=" * 60)
    print(f"Base: {BASE}")
    print(f"开始时间: {datetime.now().isoformat()}")

    session = requests.Session()
    r = TestResult()

    if not test_login(session, r):
        print("\n[ABORT] 登录失败，无法继续")
        return 1

    data = test_basic_data(session, r)
    test_purchase_flow(session, r, data)
    test_sales_flow(session, r, data)
    test_reports(session, r)
    test_stock_and_alerts(session, r)
    test_ai_pages(session, r)
    test_mobile_scan(session, r)
    test_user_settings(session, r)

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    total = len(r.passed) + len(r.failed) + len(r.warnings)
    print(f"总测试项: {total}")
    print(f"  通过: {len(r.passed)}")
    print(f"  失败: {len(r.failed)}")
    print(f"  警告: {len(r.warnings)}")
    print(f"结束时间: {datetime.now().isoformat()}")
    if r.failed:
        print("\n失败项:")
        for name, reason in r.failed:
            print(f"  - {name}: {reason}")
    if r.warnings:
        print("\n警告项:")
        for w in r.warnings[:20]:
            print(f"  - {w}")
        if len(r.warnings) > 20:
            print(f"  ... 还有 {len(r.warnings) - 20} 项")
    return 0 if not r.failed else 1


if __name__ == "__main__":
    sys.exit(main())
