# -*- coding: utf-8 -*-
import re, sys, urllib.request, urllib.parse, http.cookiejar, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + "/login").read().decode("utf-8", "ignore")
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
op.open(BASE + "/login", data=urllib.parse.urlencode(
    {"username": "admin", "password": "AAAA1234", "usage_consent": "1",
     "login_mode": "admin", "csrf_token": csrf}).encode())
r = op.open(BASE + "/api/material/all", timeout=10)
print("material/all FULL:", r.read().decode("utf-8", "ignore")[:600])
for u in ["/api/suppliers", "/api/units", "/warehouse/api/list", "/api/categories"]:
    try:
        r = op.open(BASE + u, timeout=10)
        body = r.read().decode("utf-8", "ignore")
        print(f"{u} -> {r.status} {body[:200]}")
    except Exception as e:
        print(f"{u} -> ERR {e}")
# 物料列表页行数
h = op.open(BASE + "/material").read().decode("utf-8", "ignore")
rows = re.findall(r"<tr[^>]*>.*?</tr>", h, re.S)
print(f"/material rows: {len(rows)}")
codes = re.findall(r'/material/(\d+)', h)
print("material ids sample:", codes[:5])
