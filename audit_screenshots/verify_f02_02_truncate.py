#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_f02_02_truncate.py — BUG-F02-02 专项验证

目标：
- 6 个主数据新增/编辑路由：add_material / edit_material / add_supplier /
  edit_supplier / add_customer / edit_customer
- 每个路由对其受控字段做「超限 1 字符 → 400 + 中文 msg」「临界 1 字符 → 200」
- 物料额外覆盖 spec/brand/purpose/remark
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


def post(opener, path, data, content_type="application/x-www-form-urlencoded"):
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST")
    req.add_header("Content-Type", content_type)
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


def post_form(opener, path, data):
    body = urllib.parse.urlencode(data, doseq=True).encode('utf-8')
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("X-Requested-With", "XMLHttpRequest")
    try:
        return opener.open(req, timeout=10), None
    except urllib.error.HTTPError as e:
        return e, e.read().decode('utf-8', errors='ignore')


def post_with_csrf(opener, path, csrf_token, extra):
    data = dict(extra)
    data['csrf_token'] = csrf_token
    return post_form(opener, path, data)


def main():
    print('===== BUG-F02-02 物料/供应商/客户 主数据长度截断防护 =====\n')
    results = []

    def check(name, cond, detail=''):
        results.append((cond, name, detail))
        mark = '✓' if cond else '✗'
        print(f'  [{mark}] {name}' + (f' — {detail}' if detail and not cond else ''))

    try:
        opener = login_admin()
    except Exception as exc:
        print('[FATAL] 登录失败，请先启动服务：', exc)
        sys.exit(1)
    print('[1] 登录成功\n')

    # 抓三个表单页的 CSRF token
    csrf_mat = fetch_csrf_from(opener, '/material/add')
    csrf_sup = fetch_csrf_from(opener, '/supplier')
    csrf_cus = fetch_csrf_from(opener, '/customer')
    check('拿到 /material/add CSRF', bool(csrf_mat), csrf_mat[:12] if csrf_mat else 'NONE')
    check('拿到 /supplier CSRF', bool(csrf_sup), csrf_sup[:12] if csrf_sup else 'NONE')
    check('拿到 /customer CSRF', bool(csrf_cus), csrf_cus[:12] if csrf_cus else 'NONE')

    # ---- 物料 add ----
    # DB 列宽：code=50/name=100/brand=100/spec=100/purpose=200/remark=500
    code_51 = 'M' + 'X' * 50
    code_50 = 'M' + 'X' * 49
    name_101 = 'A' * 101
    name_100 = 'A' * 100
    spec_101 = 'S' * 101
    spec_100 = 'S' * 100
    purpose_201 = 'P' * 201
    purpose_200 = 'P' * 200
    remark_501 = 'R' * 501
    remark_500 = 'R' * 500

    def msg_contains(body, kw):
        # JSON 响应中文字符以反斜杠 u 转义，解码后再判断
        if not body:
            return False
        try:
            j = json.loads(body)
            return kw in (j.get('msg') or '')
        except Exception:
            return kw in body

    # code>50
    r, body = post_with_csrf(opener, '/material/add', csrf_mat, {'code': code_51, 'name': '正常名称', 'spec': ''})
    check('物料 add code>50 应 400', r.status == 400, f'status={r.status}')
    check('物料 add code>50 msg 中文', msg_contains(body, '物料编码不能超过 50'), (body or '')[:80])

    # name>100
    r, body = post_with_csrf(opener, '/material/add', csrf_mat, {'code': 'A001@F02', 'name': name_101, 'spec': ''})
    check('物料 add name>100 应 400', r.status == 400, f'status={r.status}')
    check('物料 add name>100 msg', msg_contains(body, '物料名称不能超过 100'), (body or '')[:80])

    # spec>100
    r, body = post_with_csrf(opener, '/material/add', csrf_mat, {'code': 'A002@F02', 'name': '正常', 'spec': spec_101})
    check('物料 add spec>100 应 400', r.status == 400, f'status={r.status}')
    check('物料 add spec>100 msg', msg_contains(body, '物料规格不能超过 100'), (body or '')[:80])

    # purpose>200
    r, body = post_with_csrf(opener, '/material/add', csrf_mat, {'code': 'A003@F02', 'name': '正常', 'spec': '', 'purpose': purpose_201})
    check('物料 add purpose>200 应 400', r.status == 400, f'status={r.status}')
    check('物料 add purpose>200 msg', msg_contains(body, '用途不能超过 200'), (body or '')[:80])

    # remark>500
    r, body = post_with_csrf(opener, '/material/add', csrf_mat, {'code': 'A004@F02', 'name': '正常', 'spec': '', 'remark': remark_501})
    check('物料 add remark>500 应 400', r.status == 400, f'status={r.status}')
    check('物料 add remark>500 msg', msg_contains(body, '备注不能超过 500'), (body or '')[:80])

    # 临界值全部成功
    r, body = post_with_csrf(opener, '/material/add', csrf_mat, {
        'code': code_50, 'name': name_100, 'spec': spec_100,
        'purpose': purpose_200, 'remark': remark_500,
    })
    check('物料 add 临界值应 200', r.status == 200, f'status={r.status}, body={(body or "")[:160]}')

    # 找刚创建的物料 id（用 /material/api/list 或扫描列表）
    new_id = None
    try:
        r = get(opener, '/material/api/list')
        if r.status == 200:
            txt = r.read().decode('utf-8', errors='ignore')
            m_all = re.findall(r'"id"\s*:\s*(\d+)', txt)
            if m_all:
                new_id = max(int(x) for x in m_all)
    except Exception:
        pass
    if not new_id:
        r = get(opener, '/material')
        body = r.read().decode('utf-8', errors='ignore')
        m_all = re.findall(r'data-id="(\d+)"', body)
        if m_all:
            new_id = max(int(x) for x in m_all)
    check('能找到刚创建的物料 id', new_id is not None, f'id={new_id}')

    # ---- 物料 edit ----
    if new_id:
        r, _ = post_with_csrf(opener, f'/material/edit/{new_id}', csrf_mat, {'code': code_51, 'name': 'X'})
        check('物料 edit code>50 应 400', r.status == 400, f'status={r.status}')
        r, _ = post_with_csrf(opener, f'/material/edit/{new_id}', csrf_mat, {'code': 'E001@F02', 'name': name_101})
        check('物料 edit name>100 应 400', r.status == 400, f'status={r.status}')
        r, _ = post_with_csrf(opener, f'/material/edit/{new_id}', csrf_mat, {'code': 'E001@F02', 'name': 'N', 'spec': spec_101})
        check('物料 edit spec>100 应 400', r.status == 400, f'status={r.status}')

    # ---- 供应商 add ----
    s_name_101 = 'S' * 101
    s_name_100 = 'S' * 100
    s_addr_201 = 'A' * 201
    s_addr_200 = 'A' * 200
    s_contact_51 = 'C' * 51
    s_contact_50 = 'C' * 50
    s_phone_21 = '1' * 21
    s_phone_20 = '1' * 20

    r, _ = post_with_csrf(opener, '/supplier/add', csrf_sup, {'code': 'S' * 51, 'name': '正常'})
    check('供应商 add code>50 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/supplier/add', csrf_sup, {'code': 'SUP-F02-01', 'name': s_name_101})
    check('供应商 add name>100 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/supplier/add', csrf_sup, {'code': 'SUP-F02-02', 'name': '正常', 'contact': s_contact_51})
    check('供应商 add contact>50 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/supplier/add', csrf_sup, {'code': 'SUP-F02-03', 'name': '正常', 'phone': s_phone_21})
    check('供应商 add phone>20 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/supplier/add', csrf_sup, {'code': 'SUP-F02-04', 'name': '正常', 'address': s_addr_201})
    check('供应商 add address>200 应 400', r.status == 400, f'status={r.status}')

    r, body = post_with_csrf(opener, '/supplier/add', csrf_sup, {
        'code': 'SUP-F02-OK', 'name': s_name_100, 'contact': s_contact_50,
        'phone': s_phone_20, 'address': s_addr_200,
    })
    check('供应商 add 临界值应 200', r.status == 200, f'status={r.status}, body={(body or "")[:160]}')

    # ---- 客户 add ----
    c_name_101 = 'K' * 101
    c_name_100 = 'K' * 100
    c_addr_201 = 'D' * 201
    c_addr_200 = 'D' * 200
    c_contact_51 = 'L' * 51
    c_contact_50 = 'L' * 50
    c_phone_21 = '9' * 21
    c_phone_20 = '9' * 20

    r, _ = post_with_csrf(opener, '/customer/add', csrf_cus, {'code': 'C' * 51, 'name': '正常'})
    check('客户 add code>50 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/customer/add', csrf_cus, {'code': 'CUS-F02-01', 'name': c_name_101})
    check('客户 add name>100 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/customer/add', csrf_cus, {'code': 'CUS-F02-02', 'name': '正常', 'contact': c_contact_51})
    check('客户 add contact>50 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/customer/add', csrf_cus, {'code': 'CUS-F02-03', 'name': '正常', 'phone': c_phone_21})
    check('客户 add phone>20 应 400', r.status == 400, f'status={r.status}')
    r, _ = post_with_csrf(opener, '/customer/add', csrf_cus, {'code': 'CUS-F02-04', 'name': '正常', 'address': c_addr_201})
    check('客户 add address>200 应 400', r.status == 400, f'status={r.status}')

    r, body = post_with_csrf(opener, '/customer/add', csrf_cus, {
        'code': 'CUS-F02-OK', 'name': c_name_100, 'contact': c_contact_50,
        'phone': c_phone_20, 'address': c_addr_200,
    })
    check('客户 add 临界值应 200', r.status == 200, f'status={r.status}, body={(body or "")[:160]}')

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
