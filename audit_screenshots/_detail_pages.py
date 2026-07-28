# -*- coding: utf-8 -*-
"""Detail/print pages: probe param routes with real ids from list pages + invalid ids."""
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

ERR = ["Traceback", "Internal Server Error", "jinja2.exceptions", "sqlalchemy.exc", "UndefinedError", "AttributeError", "KeyError"]

def get(url):
    try:
        r = opener.open(url, timeout=15)
        return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return -1, str(e)

# 参数路由（GET，detail/print 类，排除 delete/cancel/confirm 等写操作）
src = open(r"c:\Users\Administrator\Desktop\wms\app\app.py", encoding="utf-8").read()
route_defs = re.findall(r"""@app\.route\(\s*['"]([^'"]+)['"]\s*(?:,\s*methods=\[([^\]]+)\])?""", src)
WRITE_HINTS = ("delete", "cancel", "confirm", "void", "complete", "submit", "audit",
               "approve", "reject", "edit", "copy", "revoke", "push", "create", "unsubmit")
param_gets = []
for url, methods in route_defs:
    ms = methods or "GET"
    if "GET" not in ms or "<" not in url:
        continue
    tail = url.rsplit("/", 1)[-1]
    if any(h in tail for h in WRITE_HINTS):
        continue
    param_gets.append(url)

bugs, tested = [], 0
BIG = "99999999"
for pat in sorted(set(param_gets)):
    sample = re.sub(r"<int:\w+>", "1", pat)
    sample = re.sub(r"<(?:string:)?\w+>", "test", sample)
    for label, u in (("id=1", sample), (f"id={BIG}", sample.replace("1", BIG, 1) if "1" in sample else None)):
        if not u:
            continue
        st, b = get(BASE + u)
        tested += 1
        if st >= 500 or st == -1:
            bugs.append((u, st, "HTTP " + str(st)))
        elif st == 200:
            for m in ERR:
                if m in b:
                    bugs.append((u, st, "marker " + m)); break
print(f"param GET tested: {tested}, issues: {len(bugs)}")
for u, st, msg in bugs:
    print(f"  [{st}] {u} :: {msg}")
