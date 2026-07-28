# -*- coding: utf-8 -*-
"""CSRF: POST without token must be rejected (400/403), not processed."""
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

# 只挑选安全的 POST 端点（修改密码用错误数据，不会成功）
tests = [
    ("/user/change_password", {"old_password": "x", "new_password": "y", "confirm_password": "z"}),
]
for url, payload in tests:
    # 不带 csrf
    try:
        r = opener.open(BASE + url, data=urllib.parse.urlencode(payload).encode(), timeout=15)
        print(f"[NO-CSRF] {url} -> {r.status} (预期 400/403，若 200 则 CSRF 防护缺失)")
    except urllib.error.HTTPError as e:
        print(f"[NO-CSRF] {url} -> {e.code} ({'OK 已拦截' if e.code in (400, 403) else '其他'})")
