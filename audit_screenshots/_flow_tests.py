# -*- coding: utf-8 -*-
"""Logout flow + empty-form POST validation tests."""
import re, sys, urllib.request, urllib.parse, http.cookiejar, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
BASE = "http://127.0.0.1:8080"

def new_session():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    b = op.open(BASE + "/login").read().decode("utf-8", "ignore")
    csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
    op.open(BASE + "/login", data=urllib.parse.urlencode(
        {"username": "admin", "password": "AAAA1234", "usage_consent": "1",
         "login_mode": "admin", "csrf_token": csrf}).encode())
    return op

def fetch(op, url, data=None):
    try:
        r = op.open(url, data=data, timeout=15)
        return r.status, r.geturl(), r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, url, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return -1, url, str(e)

# 1. 登出流程
op = new_session()
st, url, b = fetch(op, BASE + "/logout")
st2, _, b2 = fetch(op, BASE + "/material")
kicked = "登录" in b2 and ("密码" in b2 or "username" in b2)
print(f"[LOGOUT] logout->{st}, 登出后访问/material: {'已踢回登录页 OK' if kicked else 'FAIL 仍可访问'}")

# 2. 空表单 POST（列表页取 csrf，POST-only 端点）
op = new_session()
for listp, addp in [("/unit", "/unit/add"), ("/category", "/category/add"), ("/warehouse", "/warehouse/add")]:
    st, _, form = fetch(op, BASE + listp)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', form)
    if not m:
        print(f"[EMPTY-FORM] {listp} 无 csrf_token，跳过")
        continue
    csrf = m.group(1)
    st, url, b = fetch(op, BASE + addp, data=urllib.parse.urlencode({"csrf_token": csrf}).encode())
    if st >= 500:
        print(f"[EMPTY-FORM] {addp} POST空表单 -> HTTP {st} BUG!")
    else:
        has_err = ("必填" in b or "不能" in b or "error" in b.lower() or "alert-danger" in b or "请" in b)
        print(f"[EMPTY-FORM] {addp} POST空表单 -> {st} {'有校验提示 OK' if has_err else 'PENDING 需人工确认是否被创建'}")

# 3. 特殊字符输入（单位名称 XSS）
st, _, form = fetch(op, BASE + "/unit")
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', form).group(1)
xss_name = "<script>alert('xss_test')</script>"
st, url, b = fetch(op, BASE + "/unit/add", data=urllib.parse.urlencode({"csrf_token": csrf, "name": xss_name}).encode())
created = (st == 200 and ("成功" in b or "添加成功" in b)) or st in (301, 302)
print(f"[XSS-INPUT] /unit/add 特殊字符名称 -> {st} {'疑似已创建(需验证输出转义)' if created else '被拒绝/校验拦截'}")
st, _, lb = fetch(op, BASE + "/unit")
if xss_name in lb:
    print("[XSS-INPUT] BUG: /unit 列表未转义反射脚本标签 (存储型XSS)")
elif "&lt;script&gt;" in lb:
    print("[XSS-INPUT] OK: 列表已转义")
else:
    print("[XSS-INPUT] 单位未创建或名称未显示，需人工核对")
