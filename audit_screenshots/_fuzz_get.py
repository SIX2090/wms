# -*- coding: utf-8 -*-
"""Read-only GET parameter fuzz on list pages: pagination, search, special chars."""
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

CASES = []
lists = ["/material", "/category", "/unit", "/warehouse", "/supplier", "/customer",
         "/department", "/employee", "/purchase_request", "/purchase_order", "/in_order",
         "/sales", "/out_order", "/after_sale_out", "/stock_query", "/check", "/transfer",
         "/adjustment", "/subcontract", "/bom", "/requisition", "/contract",
         "/user", "/operation_audit"]
params = [
    ("page", "99999"), ("page", "-1"), ("page", "abc"),
    ("keyword", "<script>alert(1)</script>"), ("keyword", "' OR '1'='1"),
    ("keyword", "%"), ("keyword", "A" * 500), ("search", "<img src=x onerror=alert(1)>"),
]
for lp in lists:
    for k, v in params:
        CASES.append((lp, k, v))

ERR = ["Traceback", "Internal Server Error", "jinja2.exceptions", "sqlalchemy.exc", "UndefinedError"]
bugs = []
for lp, k, v in CASES:
    url = f"{BASE}{lp}?{k}={urllib.parse.quote(v)}"
    try:
        r = opener.open(url, timeout=15)
        b = r.read().decode("utf-8", "ignore")
        code = r.status
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", "ignore"); code = e.code
    except Exception as e:
        bugs.append((lp, k, v[:20], f"EXC {e}")); continue
    if code >= 500:
        bugs.append((lp, k, v[:20], f"HTTP {code}"))
    else:
        for m in ERR:
            if m in b:
                bugs.append((lp, k, v[:20], f"err-marker {m}")); break
        # XSS reflection check: unescaped script tag reflected
        if v.startswith("<script>") and v in b:
            bugs.append((lp, k, "xss", "未转义反射 <script>"))
        if v.startswith("<img") and v in b:
            bugs.append((lp, k, "xss", "未转义反射 <img onerror>"))

print(f"total cases: {len(CASES)}, issues: {len(bugs)}")
seen = set()
for lp, k, v, msg in bugs:
    key = (lp, msg)
    if key in seen: continue
    seen.add(key)
    print(f"  [{msg}] {lp} ?{k}={v}")
