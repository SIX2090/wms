# -*- coding: utf-8 -*-
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

st, b = get("/out_order")
print("页面含 OU26070001:", "OU26070001" in b, "len:", len(b))
# 找单号附近链接
m = re.search(r"OU26070001.{0,400}", b, re.S)
if m: print("上下文:", re.sub(r"\s+", " ", m.group(0))[:350])
# 详情页直接试 id=1
st, b = get("/out_order/1")
print("/out_order/1 ->", st, "含OU26070001:", "OU26070001" in b, "含草稿:", "草稿" in b)
if "OU26070001" in b:
    st, r = post_json("/out_order/1/complete", {})
    blocked = st >= 400 or "库存不足" in r or "error" in r
    print(f"[{'PASS' if blocked else 'BUG! 超额出库竟能完成'}] complete: HTTP {st} {r[:200]}")
    st, b = get("/api/material/all")
    stock = None
    for mm in json.loads(b).get("data", []):
        if mm.get("code") == "QAMAT01": stock = mm.get("stock")
    print("完成后库存:", stock)
    # 清理
    if not blocked:
        post_json("/out_order/1/revert", {})
    st, r = post_json("/out_order/1/delete", {})
    print("清理:", st, r[:100])
