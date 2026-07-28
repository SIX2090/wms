# -*- coding: utf-8 -*-
import re, sys, urllib.request, urllib.parse, http.cookiejar, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + "/login").read().decode("utf-8", "ignore")
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
op.open(BASE + "/login", data=urllib.parse.urlencode(
    {"username": "admin", "password": "AAAA1234", "usage_consent": "1",
     "login_mode": "admin", "csrf_token": csrf}).encode())
for p in ["/supplier", "/material", "/unit"]:
    h = op.open(BASE + p).read().decode("utf-8", "ignore")
    # 提取所有模态/表单中的字段名
    forms = re.findall(r'<form[^>]*action="([^"]*)"[^>]*>(.*?)</form>', h, re.S)
    print(f"=== {p}: {len(forms)} forms")
    for action, fbody in forms[:6]:
        fields = re.findall(r'name="([^"]+)"', fbody)
        print(f"  action={action} fields={fields}")
