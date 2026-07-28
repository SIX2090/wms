# -*- coding: utf-8 -*-
"""超额出库后续: 完成超额出库单应被库存校验拦截; 然后清理."""
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

def get(url):
    try:
        r = op.open(BASE + url, timeout=15); return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

def cur_stock():
    st, b = get("/api/material/all")
    for m in json.loads(b).get("data", []):
        if m.get("code") == "QAMAT01": return m.get("stock")
    return None

# 找到超额出库单 id
st, b = get("/out_order")
ids = re.findall(r"/out_order/(\d+)", b)
print("out_order ids:", ids[:3])
oid = ids[0] if ids else None
print("创建超额单后库存(应仍为10):", cur_stock())
if oid:
    st, b = get(f"/out_order/{oid}")
    draft = "草稿" in b
    print(f"出库单 {oid} 状态含草稿: {draft}")
    st, r = post_json(f"/out_order/{oid}/complete", {})
    blocked = st >= 400 or "库存不足" in r or "error" in r
    print(f"[{'PASS' if blocked else 'BUG!'}] 完成超额出库单: HTTP {st} {r[:150]}")
    print("完成尝试后库存:", cur_stock())
    # 清理: 若已完成需反提交, 再删
    if not blocked and st == 200:
        post_json(f"/out_order/{oid}/revert", {})
    st, r = post_json(f"/out_order/{oid}/delete", {})
    print(f"清理删除出库单: HTTP {st} {r[:100]}")
