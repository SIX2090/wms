#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_f02_09_10_frontend.py — BUG-F02-09 / BUG-F02-10 基础资料前端修复验证

BUG-F02-09: material.html 标签模板设计器 16 处调用未定义的 saveTemplateToStorage()
  - 函数已定义且仅定义一次
  - 16 处调用点保留
  - 无已保存模板时自动恢复 localStorage 草稿（restoreTemplateDraft 挂载到空模板分支）
  - 保存到服务器成功后清除草稿
  - 浏览器实测：打开设计器执行 insertRow 不再抛 ReferenceError，草稿写入 localStorage

BUG-F02-10: warehouse/department/employee 的 GET 筛选表单泄露 csrf_token 到 URL
  - GET 筛选表单块内不再含 csrf_token 隐藏域（静态 + 线上 HTTP 双重验证）
  - 三个页面的 POST 模态框表单仍保留 csrf_token（每页 3 处）
"""
import os
import re
import sys
import urllib.request
import urllib.parse
import http.cookiejar

BASE = "http://127.0.0.1:8080"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "app", "templates")

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS" if ok else "FAIL"), "-", name, ("| " + detail if detail else ""))


def read(name):
    with open(os.path.join(TPL, name), encoding="utf-8") as f:
        return f.read()


# ---------- Part A: 静态检查 BUG-F02-09 ----------
src = read("material.html")
check("F02-09 saveTemplateToStorage 已定义且仅一次",
      len(re.findall(r"function\s+saveTemplateToStorage\s*\(", src)) == 1)
check("F02-09 16 处调用点保留",
      len(re.findall(r"saveTemplateToStorage\(\);", src)) == 16,
      "实际 %d 处" % len(re.findall(r"saveTemplateToStorage\(\);", src)))
check("F02-09 restoreTemplateDraft 已定义",
      len(re.findall(r"function\s+restoreTemplateDraft\s*\(", src)) == 1)
check("F02-09 空模板分支挂载草稿恢复",
      re.search(r'-- 无模板 --.{0,200}?restoreTemplateDraft\(\);', src, re.S) is not None)
check("F02-09 保存成功后清除草稿",
      "localStorage.removeItem('labelTemplateDraft')" in src)
check("F02-09 草稿键名一致",
      src.count("labelTemplateDraft") >= 3)
# 括号配平粗检（新增函数段）
seg = src[src.index("function saveTemplateToStorage"):src.index("function openLabelTemplate")]
check("F02-09 新增代码段花括号配平", seg.count("{") == seg.count("}"),
      "{=%d }=%d" % (seg.count("{"), seg.count("}")))

# ---------- Part A2: 静态检查 BUG-F02-10 ----------
for fname in ("warehouse.html", "department.html", "employee.html"):
    body = read(fname)
    m = re.search(r'<form method="get".*?</form>', body, re.S)
    check("F02-10 %s GET 筛选表单无 csrf_token" % fname,
          m is not None and "csrf_token" not in m.group(0))
    check("F02-10 %s POST 模态框保留 csrf_token(3 处)" % fname,
          body.count('name="csrf_token"') == 3,
          "实际 %d 处" % body.count('name="csrf_token"'))

# ---------- Part B: 线上 HTTP 检查 ----------
def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def login(opener, username, password):
    body = opener.open(BASE + "/login").read().decode("utf-8", "ignore")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    csrf = m.group(1) if m else ""
    data = urllib.parse.urlencode({
        "csrf_token": csrf, "username": username, "password": password,
        "usage_consent": "1", "login_mode": "user",
    }).encode("utf-8")
    req = urllib.request.Request(BASE + "/login", data=data, method="POST")
    return opener.open(req)


opener = make_opener()
logged_in = False
for pwd in ("AAAA1234", "admin"):
    try:
        r = login(opener, "admin", pwd)
        if "login" not in r.geturl():
            logged_in = True
            break
    except Exception:
        continue

if logged_in:
    try:
        html = opener.open(BASE + "/warehouse?status=active&search=test").read().decode("utf-8", "ignore")
        m = re.search(r'<form method="get".*?</form>', html, re.S)
        check("F02-10 线上 /warehouse GET 表单无 csrf_token",
              m is not None and "csrf_token" not in m.group(0))
    except Exception as e:
        check("F02-10 线上 /warehouse GET 表单无 csrf_token", False, str(e))
else:
    check("F02-10 线上 /warehouse GET 表单无 csrf_token", False, "登录失败，跳过线上检查")

# ---------- Part C: 浏览器实测 BUG-F02-09 ----------
def browser_test():
    from playwright.sync_api import sync_playwright
    errors = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/login")
        page.fill('input[name="username"]', "admin")
        page.fill('input[name="password"]', "AAAA1234")
        page.check('input[name="usage_consent"]')
        page.click('button[type="submit"]')
        page.wait_for_url(lambda u: "login" not in u, timeout=8000)
        page.goto(BASE + "/material")
        page.wait_for_load_state("networkidle")
        check("F02-09 浏览器 typeof saveTemplateToStorage == function",
              page.evaluate("typeof saveTemplateToStorage") == "function")
        page.click('button:has-text("标签模板")')
        page.wait_for_selector("#labelTemplateModal.show", timeout=5000)
        before = len(errors)
        page.click('#labelTemplateModal button[onclick="insertRow()"]')
        page.wait_for_timeout(300)
        check("F02-09 插入行不再抛 ReferenceError",
              not any("saveTemplateToStorage" in e for e in errors[before:]),
              "; ".join(errors[before:])[:120])
        draft = page.evaluate("localStorage.getItem('labelTemplateDraft')")
        ok_draft = False
        if draft:
            import json
            try:
                d = json.loads(draft)
                ok_draft = isinstance(d.get("cells"), list) and d.get("rows", 0) >= 1
            except Exception:
                ok_draft = False
        check("F02-09 草稿已写入 localStorage 且结构正确", ok_draft)
        browser.close()
    return errors


if logged_in:
    try:
        browser_test()
    except Exception as e:
        check("F02-09 浏览器实测", False, repr(e)[:200])
else:
    check("F02-09 浏览器实测", False, "登录失败，跳过浏览器检查")

# ---------- 汇总 ----------
failed = [r for r in results if not r[1]]
print("\n==== 汇总: %d/%d PASS ====" % (len(results) - len(failed), len(results)))
sys.exit(1 if failed else 0)
