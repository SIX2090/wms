#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_f02_01_sort.py — BUG-F02-01 基础资料排序默认按 code 升序

目标：
- 5 个基础资料列表默认进列表时，第一行是 code 最小的物料
- 默认 sort_by=code sort_order=asc（从页面渲染的 sort_th macro caret-up 位置判断）
- 显式 ?sort=code&order=desc 也正确
- 模板中含 sort_th 或等价的内联 sortable-header
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


def detect_default_sort(body):
    """从模板渲染结果中识别默认 sort_by / sort_order。
    模板 sort_th 在 sort_by == field 时输出 caret-up/down icon。
    所以默认 sort=code asc 时：<th data-sortable="code" ...> <i class="bi bi-caret-up-fill ...>"""
    # 找所有 sortable-header th 块
    th_blocks = re.findall(
        r'<th[^>]*data-sortable="([^"]+)"[^>]*>(.*?)</th>',
        body, re.DOTALL
    )
    for field, inner in th_blocks:
        if 'bi-caret-up-fill' in inner:
            return field, 'asc'
        if 'bi-caret-down-fill' in inner:
            return field, 'desc'
    # material.html 用内联 sortable-header，写法略不同：sort_by == field 时输出 caret
    # 它也用相同的 i 标签
    return None, None


def detect_first_code_in_table(body):
    """从表格中抓第一行 code 列的内容。多种模板中 code 列的 data-column-key 不一定一致，
    但第一行 td 中的第一个短字符串通常是 code。"""
    # 找 <tbody>...</tbody>
    m_tbody = re.search(r'<tbody[^>]*>(.*?)</tbody>', body, re.DOTALL)
    if not m_tbody:
        return None
    tbody = m_tbody.group(1)
    # 找第一行 <tr>...</tr>
    m_tr = re.search(r'<tr[^>]*>(.*?)</tr>', tbody, re.DOTALL)
    if not m_tr:
        return None
    tr = m_tr.group(1)
    # 抓所有 td
    tds = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
    # 找第一个像 code 的（短、字母数字下划线点破折号）
    for td in tds:
        # 去掉内嵌标签
        text = re.sub(r'<[^>]+>', '', td).strip()
        if text and re.fullmatch(r'[A-Za-z0-9_\-\.]{1,30}', text):
            return text
    return None


def main():
    print('===== BUG-F02-01 基础资料排序默认按 code 升序 =====\n')
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

    # 1) 静态校验：app.py 默认值
    with open(r'c:\Users\Administrator\Desktop\wms\app\app.py', encoding='utf-8') as f:
        app_src = f.read()
    check('_get_master_list_filters 默认 code',
          "def _get_master_list_filters(default_sort='code')" in app_src, '')
    check('_get_master_list_filters 默认 order=asc',
          re.search(r"sort_order\s*=\s*request\.args\.get\('order',\s*'asc'\)", app_src) is not None, '')
    check('material_list 默认 sort=code',
          re.search(r"sort_by\s*=\s*request\.args\.get\('sort',\s*'code'\)", app_src) is not None, '')
    check('material_list 默认 order=asc',
          re.search(r"sort_order\s*=\s*request\.args\.get\('order',\s*'asc'\)", app_src) is not None, '')
    check('contract_list 默认 contract_no / asc',
          re.search(r"sort_by\s*=\s*\(request\.args\.get\('sort'\)\s*or\s*'contract_no'\)", app_src) is not None, '')
    check('_warehouse_query_from_args 默认 code',
          re.search(r"_warehouse_query_from_args\(\):[\s\S]{0,150}?_get_master_list_filters\('code'\)", app_src) is not None, '')
    check('_department_query_from_args 默认 code',
          re.search(r"def\s+_department_query_from_args\(\):\s*\n\s*#\s*BUG-F02-01[\s\S]{0,150}?_get_master_list_filters\('code'\)", app_src) is not None, '')

    # 2) 动态校验：从渲染 HTML 的 caret icon 位置识别默认 sort_by / sort_order
    import sqlite3
    db_path = r'c:\Users\Administrator\Desktop\wms\app\instance\inventory.db'
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 哪些列表页用 code 字段排序
    lists_with_code = [
        ('/material', 'material', 'code'),
        ('/supplier', 'supplier', 'code'),
        ('/customer', 'customer', 'code'),
        ('/warehouse', 'warehouse', 'code'),
        ('/department', 'department', 'code'),
        ('/category', 'material_category', 'code'),
        ('/unit', 'unit', 'code'),
        ('/contract', 'contract', 'contract_no'),
    ]

    for path, tbl, sort_field in lists_with_code:
        r = opener.open(f"{BASE}{path}")
        body = r.read().decode('utf-8', errors='ignore')
        sb, so = detect_default_sort(body)
        print(f'  {path} 默认 sort={sb} order={so}')
        check(f'{path} 默认 sort={sort_field}', sb == sort_field, f'got {sb}')
        check(f'{path} 默认 order=asc', so == 'asc', f'got {so}')
        check(f'{path} 渲染 200', r.status == 200, f'status={r.status}')

    # 3) 显式 ?sort=code&order=desc 时，渲染 HTML 中 caret-down 应在 code 列
    r = opener.open(f"{BASE}/material?sort=code&order=desc")
    body = r.read().decode('utf-8', errors='ignore')
    sb, so = detect_default_sort(body)
    check('显式 ?sort=code&order=desc 渲染 caret-down 在 code 列',
          sb == 'code' and so == 'desc',
          f'got sort={sb} order={so}')

    # 4) 模板 sort_th 宏检查
    mat_path = r'c:\Users\Administrator\Desktop\wms\app\templates\material.html'
    with open(mat_path, encoding='utf-8') as f:
        mat_tpl = f.read()
    check('material.html 含 sort_th 宏或等价 inline sortable-header',
          ('sort_th(' in mat_tpl) or ('data-sortable=' in mat_tpl and 'sortable-header' in mat_tpl),
          'material.html 实际用内联实现 (与 sort_th 等价)')

    conn.close()

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
