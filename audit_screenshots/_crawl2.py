# -*- coding: utf-8 -*-
"""Full GET-route crawl based on real route table extracted from app.py."""
import re, sys, urllib.request, urllib.parse, http.cookiejar, json, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"
src = open(r"c:\Users\Administrator\Desktop\wms\app\app.py", encoding="utf-8").read()
route_defs = re.findall(r"""@app\.route\(\s*['"]([^'"]+)['"]\s*(?:,\s*methods=\[([^\]]+)\])?""", src)

static, param_routes = [], []
for url, methods in route_defs:
    ms = methods or "GET"
    if "GET" not in ms:
        continue
    if "<" in url:
        param_routes.append(url)
    else:
        static.append(url)
static = sorted(set(static))
print(f"static GET routes: {len(static)}, param routes: {len(param_routes)}")

ERROR_MARKERS = ["Traceback (most recent call last)", "jinja2.exceptions", "Internal Server Error",
                 "sqlalchemy.exc", "UndefinedError", "TemplateNotFound", "BuildError", "werkzeug.exceptions"]

def make_opener(follow=True):
    if follow:
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl): return None
    return urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

def fetch(opener, url, data=None):
    try:
        r = opener.open(url, data=data, timeout=15)
        return r.status, r.geturl(), r.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, url, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return -1, url, str(e)

# login
opener = make_opener()
st, _, body = fetch(opener, BASE + "/login")
csrf = (re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body) or [None, ""])[1]
data = urllib.parse.urlencode({"username": "admin", "password": "AAAA1234", "usage_consent": "1",
                               "login_mode": "admin", "csrf_token": csrf}).encode()
st, url, body = fetch(opener, BASE + "/login", data=data)
assert st == 200 and ("退出" in body or "工作台" in body or "欢迎" in body), "login failed"
print("login OK")

results = []
for p in static:
    st, url, body = fetch(opener, BASE + p)
    issues = []
    if st == -1:
        issues.append("请求异常: " + body[:150])
    elif st in (404, 405):
        issues.append(f"HTTP {st}")
    elif st >= 500:
        issues.append(f"HTTP {st} 服务器错误")
    elif st == 200:
        for mk in ERROR_MARKERS:
            if mk in body:
                issues.append("错误标记: " + mk)
        if "<form" in body and "csrf_token" not in body:
            issues.append("表单缺CSRF")
        if len(body) < 400:
            issues.append(f"内容过短({len(body)}B)")
    if issues:
        results.append((p, st, "; ".join(dict.fromkeys(issues))))
        print(f"[{st}] {p} :: {'; '.join(dict.fromkeys(issues))}")

# 匿名访问抽查
anon = make_opener(follow=False)
anon_fails = []
for p in ["/material", "/sales", "/stock_query", "/admin/console", "/user", "/system_settings", "/backup"]:
    st, _, _ = fetch(anon, BASE + p)
    if st == 200:
        anon_fails.append(p)
        print(f"[ANON-FAIL] {p} 未登录返回200")
print(f"\n===== 汇总: 异常 {len(results)} 项, 匿名可访问 {len(anon_fails)} 项 =====")
json.dump({"errors": [{"path": p, "http": s, "issue": i} for p, s, i in results],
           "anon_ok": anon_fails},
          open(r"c:\Users\Administrator\Desktop\wms\audit_screenshots\_crawl2_result.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
