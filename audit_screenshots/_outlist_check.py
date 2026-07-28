# -*- coding: utf-8 -*-
"""出库单列表不显示新建草稿排查."""
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

# 先造一张今天的出库草稿（数量1，库存0无所谓，草稿不校验）
b = op.open(BASE + "/material").read().decode("utf-8", "ignore")
m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b)
if m: CSRF = m.group(1)
req = urllib.request.Request(BASE + "/out_order/add",
    data=json.dumps({"order_no": "", "date": "2026-07-28", "business_type": "其他出库",
                     "customer": "QA列表可见性", "warehouse": "材料仓",
                     "items": [{"code": "QAMAT01", "quantity": 1, "price": 1}]}).encode(),
    headers={"Content-Type": "application/json", "X-CSRFToken": CSRF})
r = op.open(req); resp = json.loads(r.read().decode("utf-8", "ignore"))
new_no = resp.get("order_no"); new_id = resp.get("id")
print("新建出库草稿:", new_no, "id=", new_id)

def get(url):
    try:
        r = op.open(BASE + url, timeout=15); return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")

for q in ["", "?status=", "?status=all", "?per_page=100"]:
    st, b = get("/out_order" + q)
    print(f"/out_order{q} -> 含新单号: {new_no in b}")
# 看列表页总行数与筛选默认值
st, b = get("/out_order")
tb = re.findall(r"<tbody[^>]*>(.*?)</tbody>", b, re.S)
if tb:
    rows = re.findall(r"<tr", tb[0])
    print("tbody 行数:", len(rows))
    print("tbody 前300字符:", re.sub(r"\s+", " ", tb[0])[:300])
sel = re.findall(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', b, re.S)
for name, body_ in sel:
    opts = re.findall(r'<option[^>]*selected[^>]*>([^<]+)', body_)
    print(f"select {name} 默认选中: {opts}")
# 清理
req = urllib.request.Request(BASE + f"/out_order/{new_id}/delete", data=b"{}",
    headers={"Content-Type": "application/json", "X-CSRFToken": CSRF})
try:
    r = op.open(req); print("清理:", r.status)
except urllib.error.HTTPError as e:
    print("清理:", e.code)
