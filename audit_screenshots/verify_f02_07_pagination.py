#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_f02_07_pagination.py — BUG-F02-07 主数据分页 per_page 上限 + URL 记忆

目标：
- per_page 超过白名单 (10, 20, 50, 100, 200) 时被截断到 20
- warehouse/department/contract 列表含 .per-page-select 下拉
- 点页码时 URL 含 sort/order/per_page 参数（URL 记忆）
- base.html 含 per-page-select 自动绑定
"""
import os
import re
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

BASE = "http://127.0.0.1:8080"
USER = "admin"
PWD = "AAAA1234"


def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def get(opener, path):
    return opener.open(f"{BASE}{path}")


def post(opener, path, data):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    return opener.open(req)


def fetch_csrf_from(opener, url):
    r = opener.open(f"{BASE}{url}")
    body = r.read().decode("utf-8", errors="ignore")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    return m.group(1) if m else ""


def login_admin():
    opener = make_opener()
    csrf = fetch_csrf_from(opener, "/login")
    post(opener, "/login", {
        "username": USER, "password": PWD,
        "usage_consent": "1", "login_mode": "admin",
        "csrf_token": csrf,
    })
    return opener


def main():
    print('===== BUG-F02-07 主数据分页 per_page 上限 + URL 记忆 =====\n')
    results = []

    def check(name, cond, detail=''):
        results.append((cond, name, detail))
        mark = '✓' if cond else '✗'
        print(f'  [{mark}] {name}' + (f' — {detail}' if detail and not cond else ''))

    try:
        opener = login_admin()
    except Exception as exc:
        print('[FATAL] 登录失败：', exc)
        sys.exit(1)
    print('[1] admin 登录成功\n')

    # 1) 静态校验
    with open(r'c:\Users\Administrator\Desktop\wms\app\templates\_list_macros.html', encoding='utf-8') as f:
        macro_src = f.read()
    check('per_page_select macro 已定义',
          'macro per_page_select' in macro_src and '10' in macro_src and '200' in macro_src, '')

    with open(r'c:\Users\Administrator\Desktop\wms\app\templates\base.html', encoding='utf-8') as f:
        base_src = f.read()
    check('base.html 自动绑定 .per-page-select',
          "querySelectorAll('.per-page-select')" in base_src, '')

    for tpl in ('warehouse.html', 'department.html', 'contract.html'):
        path = rf'c:\Users\Administrator\Desktop\wms\app\templates\{tpl}'
        with open(path, encoding='utf-8') as f:
            tpl_src = f.read()
        check(f'{tpl} import per_page_select',
              'per_page_select' in tpl_src and "import sort_th, per_page_select" in tpl_src, '')
        check(f'{tpl} 渲染 per_page_select(per_page)',
              'per_page_select(per_page)' in tpl_src, '')

    with open(r'c:\Users\Administrator\Desktop\wms\app\app.py', encoding='utf-8') as f:
        app_src = f.read()
    # 至少 8 处 per_page 白名单
    n_whitelist = app_src.count('if per_page not in [10, 20, 50, 100, 200]:')
    check(f'per_page 白名单统一为 [10, 20, 50, 100, 200] (>=8 处)', n_whitelist >= 8, f'found {n_whitelist}')

    # 2) 动态校验：/material?per_page=999 应被截断
    # 通过页面渲染的 select 看 current per_page 是不是 20
    r = opener.open(f"{BASE}/material?per_page=999")
    body = r.read().decode('utf-8', errors='ignore')
    # 抓 <option value="X" selected>
    m = re.search(r'<option\s+value="(\d+)"[^>]*selected[^>]*>\1\s*条', body)
    if m:
        check('per_page=999 被截断到 20', m.group(1) == '20', f'got {m.group(1)}')
    else:
        # 备选：select 单独渲染
        m2 = re.search(r'value="(\d+)"[^>]*selected', body)
        check('per_page=999 被截断到 20', m2 and m2.group(1) == '20', f'got {m2.group(1) if m2 else "?"}')

    # 3) /material?per_page=50 应保持 50
    r = opener.open(f"{BASE}/material?per_page=50")
    body = r.read().decode('utf-8', errors='ignore')
    m = re.search(r'value="(\d+)"[^>]*selected', body)
    check('per_page=50 保持 50', m and m.group(1) == '50', f'got {m.group(1) if m else "?"}')

    # 4) URL 记忆：?sort=code&order=asc&per_page=50&search=foo 时页码链接应保留这些参数
    r = opener.open(f"{BASE}/material?sort=code&order=desc&per_page=50&search=QAMAT01")
    body = r.read().decode('utf-8', errors='ignore')
    # 找 page=2 的链接
    m_p2 = re.search(r'href="([^"]*page=2[^"]*)"', body)
    if m_p2:
        url = m_p2.group(1)
        check('页码链接含 sort=code', 'sort=code' in url, url[:200])
        check('页码链接含 order=desc', 'order=desc' in url, url[:200])
        check('页码链接含 per_page=50', 'per_page=50' in url, url[:200])
        check('页码链接含 search=QAMAT01', 'search=QAMAT01' in url, url[:200])
    else:
        # 数据太少没翻页，跳过
        print('  (无 page=2 链接，数据量太少，跳过 URL 记忆检查)')

    # 5) warehouse/department/contract 列表渲染 per_page_select
    for path in ('/warehouse', '/department', '/contract'):
        r = opener.open(f"{BASE}{path}")
        body = r.read().decode('utf-8', errors='ignore')
        check(f'{path} 含 .per-page-select',
              'per-page-select' in body, '')
        check(f'{path} 含 5 个分页选项',
              body.count('option value="') >= 5, f'found {body.count("option value=")}')

    # 总结
    passed = sum(1 for ok,_,_ in results if ok)
    print(f'\n通过 {passed} / 总计 {len(results)}')
    if passed != len(results):
        for ok, n, d in results:
            if not ok:
                print(f'  - {n}: {d}')
        sys.exit(1)
    print('全部通过！')


if __name__ == '__main__':
    main()
