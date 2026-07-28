# -*- coding: utf-8 -*-
import re, sys, urllib.request, urllib.parse, http.cookiejar, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
body = opener.open(BASE + "/login").read().decode("utf-8", "ignore")
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body).group(1)
opener.open(BASE + "/login", data=urllib.parse.urlencode(
    {"username": "admin", "password": "AAAA1234", "usage_consent": "1",
     "login_mode": "admin", "csrf_token": csrf}).encode())

for p in ["/ai/inventory_health_live", "/ai/replenishment_live", "/label/batch_print"]:
    try:
        r = opener.open(BASE + p, timeout=15)
        b = r.read().decode("utf-8", "ignore")
        print(f"--- {p} HTTP {r.status} len={len(b)}")
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "ignore")
        print(f"--- {p} HTTP {e.code} len={len(b)}")
        tb = re.findall(r'(?:Traceback|Error|Exception)[^<]{0,300}', b)
        for t in tb[:5]:
            print("   ", t.strip()[:250])
    if p == "/label/batch_print":
        forms = re.findall(r'<form[^>]*>', b)
        print("   forms:", forms[:5])
        print("   has csrf:", "csrf_token" in b)
