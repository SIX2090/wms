# -*- coding: utf-8 -*-
"""已完成入库单详情页删除按钮可见性确认（浏览器+截图），测完清理。"""
import re, sys, io, json, time, urllib.request, urllib.parse, http.cookiejar
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
SHOTS = r"c:\Users\Administrator\Desktop\wms\audit_screenshots"

# --- HTTP 造一张已完成入库单 ---
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + "/login").read().decode("utf-8", "ignore")
CSRF = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
op.open(BASE + "/login", data=urllib.parse.urlencode(
    {"username": "admin", "password": "AAAA1234", "usage_consent": "1",
     "login_mode": "admin", "csrf_token": CSRF}).encode())
b = op.open(BASE + "/material").read().decode("utf-8", "ignore")
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b)
if m: CSRF = m.group(1)

def post_json(url, obj):
    req = urllib.request.Request(BASE + url, data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json", "X-CSRFToken": CSRF})
    try:
        r = op.open(req, timeout=15); return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

# 确保基础数据存在（服务重启后可能丢失）
def post_form(url, data):
    data = dict(data); data["csrf_token"] = CSRF
    try:
        r = op.open(BASE + url, data=urllib.parse.urlencode(data).encode(), timeout=15)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

sup = json.loads(op.open(BASE + "/api/suppliers").read().decode())
sup_id = next((s["id"] for s in sup if s.get("code") == "QASUP01"), None)
if not sup_id:
    post_form("/supplier/add", {"code": "QASUP01", "name": "QA测试供应商"})
    sup = json.loads(op.open(BASE + "/api/suppliers").read().decode())
    sup_id = next((s["id"] for s in sup if s.get("code") == "QASUP01"), None)
units = json.loads(op.open(BASE + "/api/units").read().decode())
unit_id = next((u["id"] for u in units if u.get("code") == "QAU01"), None)
if not unit_id:
    post_form("/unit/add", {"code": "QAU01", "name": "QA测试个"})
    units = json.loads(op.open(BASE + "/api/units").read().decode())
    unit_id = next((u["id"] for u in units if u.get("code") == "QAU01"), None)
mats = json.loads(op.open(BASE + "/api/material/all").read().decode()).get("data", [])
if not any(m.get("code") == "QAMAT01" for m in mats):
    stx, rx = post_form("/material/add", {"code": "QAMAT01", "name": "QA测试物料", "spec": "T1",
                                          "unit_id": unit_id or "", "supplier_id": sup_id or "",
                                          "stock": "0", "price": "1"})
    print("重建物料:", rx[:100])
st, r = post_json("/in_order/add", {
    "order_no": "", "supplier_id": sup_id, "date": "2026-07-29",
    "business_type": "采购入库", "purpose": "采购到货入库", "warehouse": "材料仓",
    "items": [{"code": "QAMAT01", "quantity": 5, "price": 1}]})
oid = json.loads(r).get("id")
print("建单:", r[:100])
st, r = post_json(f"/in_order/{oid}/complete", {})
print("完成:", r[:100])

# --- 浏览器查看详情页 ---
with sync_playwright() as p:
    br = p.chromium.launch(headless=True,
        executable_path=r"C:\Users\Administrator\chrome-cft\chrome-win64\chrome.exe")
    ctx = br.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/login", wait_until="load")
    page.fill('input[name="username"]', "admin")
    page.fill('input[name="password"]', "AAAA1234")
    try: page.check('input[name="usage_consent"]')
    except Exception: pass
    page.click('button[type="submit"], .btn-primary')
    page.wait_for_load_state("load"); time.sleep(1)
    page.goto(f"{BASE}/in_order/{oid}", wait_until="load"); time.sleep(1)
    page.screenshot(path=SHOTS + r"\qa_19_in_order_completed_detail.png")
    # 可见按钮分析
    btns = page.eval_on_selector_all(
        "button, a.btn, input[type=submit]",
        "els => els.filter(e => e.offsetParent !== null).map(e => (e.innerText || e.value || '').trim()).filter(t => t)")
    print("已完成单详情页可见按钮:", btns)
    visible_del = [t for t in btns if "删除" in t]
    visible_unsubmit = [t for t in btns if "反提交" in t]
    print("含'删除'可见按钮:", visible_del)
    print("含'反提交'可见按钮:", visible_unsubmit)
    # 列表页行操作
    page.goto(f"{BASE}/in_order", wait_until="load"); time.sleep(1)
    page.screenshot(path=SHOTS + r"\qa_20_in_order_list_completed.png")
    row_btns = page.eval_on_selector_all(
        "table button, table a.btn",
        "els => els.filter(e => e.offsetParent !== null).map(e => (e.innerText || '').trim()).filter(t => t)")
    print("列表页行内可见按钮:", row_btns[:20])
    br.close()

# --- 清理: 反提交 + 删除 ---
st, r = post_json(f"/in_order/{oid}/revert", {})
print("反提交:", r[:80])
st, r = post_json(f"/in_order/{oid}/delete", {})
print("删除清理:", r[:80])
print("VERDICT:", "BUG-已完成单存在可见删除按钮" if visible_del else "OK-已完成单无可见删除按钮")
