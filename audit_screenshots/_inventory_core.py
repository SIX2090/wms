# -*- coding: utf-8 -*-
"""库存核心规则全链路验证（创建→完成→库存→删除规则→超额出库→反提交→清理）"""
import re, sys, json, urllib.request, urllib.parse, http.cookiejar, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + "/login").read().decode("utf-8", "ignore")
CSRF = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
op.open(BASE + "/login", data=urllib.parse.urlencode(
    {"username": "admin", "password": "AAAA1234", "usage_consent": "1",
     "login_mode": "admin", "csrf_token": CSRF}).encode())
# 登录后 session 轮换，需重新取 CSRF token
b = op.open(BASE + "/material").read().decode("utf-8", "ignore")
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b)
if m:
    CSRF = m.group(1)
    print("CSRF token refreshed")

def post_form(url, data):
    data = dict(data); data["csrf_token"] = CSRF
    try:
        r = op.open(BASE + url, data=urllib.parse.urlencode(data).encode(), timeout=15)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

def post_json(url, obj):
    req = urllib.request.Request(BASE + url, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json", "X-CSRFToken": CSRF})
    try:
        r = op.open(req, timeout=15)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

def get(url):
    try:
        r = op.open(BASE + url, timeout=15)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

def stock_of(code):
    st, b = get(f"/api/material/search?keyword={code}")
    try:
        d = json.loads(b)
        items = d if isinstance(d, list) else d.get("data", [])
        for m in items:
            if m.get("code") == code:
                return m.get("stock")
    except Exception:
        pass
    st, b = get(f"/stock_query?keyword={code}")
    m = re.search(re.escape(code) + r".{0,800}?([\d.]+)\s*</td>", b, re.S)
    return None

results = []
def log(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'BUG '}] {name} {detail}")

# 0. 准备基础数据
st, r = post_form("/unit/add", {"code": "QAU01", "name": "QA测试个"})
unit_ok = "success" in r or "已存在" in r
st, r = post_form("/supplier/add", {"code": "QASUP01", "name": "QA测试供应商"})
sup_ok = "success" in r or "已存在" in r
st, b = get("/api/suppliers")
sup_id = None
try:
    for s in json.loads(b):
        if s.get("code") == "QASUP01": sup_id = s.get("id")
except Exception: pass
st, b = get("/api/units")
unit_id = None
try:
    for u in json.loads(b):
        if u.get("code") == "QAU01": unit_id = u.get("id")
except Exception: pass
st, r = post_form("/material/add", {"code": "QAMAT01", "name": "QA测试物料", "spec": "T1",
                                    "unit_id": unit_id or "", "supplier_id": sup_id or "",
                                    "stock": "0", "price": "1"})
mat_ok = "success" in r or "已存在" in r
print(f"准备数据: unit={unit_ok}(id={unit_id}) supplier={sup_ok}(id={sup_id}) material={mat_ok}")

# 1. 手工新增入库单（不关联采购订单）
st, r = post_json("/in_order/add", {
    "order_no": "", "supplier_id": sup_id, "date": "2026-07-28",
    "business_type": "采购入库", "purpose": "采购到货入库", "warehouse": "材料仓",
    "items": [{"code": "QAMAT01", "quantity": 10, "price": 1}]})
try:
    rid = json.loads(r).get("id") or json.loads(r).get("order_id")
except Exception:
    rid = None
if not rid:
    st, b = get("/in_order")
    m = re.findall(r"/in_order/(\d+)", b)
    rid = m[0] if m else None
log("手工新增入库单(不关联订单)", rid is not None and st in (200, 201), f"id={rid} resp={r[:120]}")

if rid:
    # 2. 完成入库
    st, r = post_json(f"/in_order/{rid}/complete", {})
    log("完成入库单", "success" in r or st == 200, f"HTTP {st} {r[:100]}")
    # 3. 库存校验
    st, b = get("/api/material/all")
    stock = None
    try:
        for m in json.loads(b).get("data", []):
            if m.get("code") == "QAMAT01": stock = m.get("stock")
    except Exception: pass
    log("完成后库存=10", stock in (10, 10.0, "10", "10.0"), f"实际stock={stock}")

    # 4. 已完成单详情页删除入口
    st, b = get(f"/in_order/{rid}")
    completed = "已完成" in b or "已审核" in b
    has_del_btn = bool(re.search(r"delete[^\"']*\(\s*\)|删除", b)) and "反提交" not in b.split("删除")[0][-50:]
    del_btn = "删除" in b
    log("已完成单状态确认", completed, "")
    log("已完成单详情页无直接删除入口", not del_btn or "反提交" in b,
        f"页面含'删除'={del_btn}, 含'反提交'={'反提交' in b}")

    # 5. 直接删除已完成单 → 必须拒绝
    st, r = post_json(f"/in_order/{rid}/delete", {})
    rejected = st in (400, 403, 405) or "反提交" in r or "不能" in r or "不允许" in r or "error" in r
    st2, b2 = get(f"/in_order/{rid}")
    still_there = st2 == 200
    log("直接删除已完成单被拒绝", rejected and still_there, f"HTTP {st} resp={r[:120]} 单据仍在={still_there}")

    # 6. 超额出库拦截
    st, r = post_json("/out_order/add", {
        "order_no": "", "date": "2026-07-28", "business_type": "其他出库",
        "customer": "QA测试", "warehouse": "材料仓",
        "items": [{"code": "QAMAT01", "quantity": 999999, "price": 1}]})
    blocked = "error" in r or st >= 400 or "库存不足" in r
    log("超额出库被拦截", blocked, f"HTTP {st} {r[:120]}")

    # 7. 反提交 → 库存回退
    st, r = post_json(f"/in_order/{rid}/revert", {})
    st2, b = get("/api/material/all")
    stock2 = None
    try:
        for m in json.loads(b).get("data", []):
            if m.get("code") == "QAMAT01": stock2 = m.get("stock")
    except Exception: pass
    log("反提交成功且库存回退为0", ("success" in r or st == 200) and stock2 in (0, 0.0, "0", "0.0"),
        f"HTTP {st} resp={r[:80]} 回退后stock={stock2}")

    # 8. 清理：删除草稿
    st, r = post_json(f"/in_order/{rid}/delete", {})
    log("清理: 草稿删除成功", "success" in r or st in (200, 302), f"HTTP {st} {r[:80]}")

print("\n===== 库存核心规则汇总 =====")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'BUG '} {n} {d}")
