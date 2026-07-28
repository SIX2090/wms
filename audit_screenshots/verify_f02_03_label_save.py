"""Verify BUG-F02-03: 标签模板保存布局路由 + JS 误报成功修复

症状：拖完字段点保存，alert「布局保存成功」，实际数据丢失
根因：app.py 无 /label_template/<id>/save_layout 路由
修复：app.py 新增 save_label_template_layout（@require_role admin/warehouse + layout 校验 + 审计）+
      label_template_detail.html saveLayout() 加 response.ok 校验 + disabled 防双击
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
    if isinstance(data, dict) and content_type == "application/json":
        body = json.dumps(data).encode("utf-8")
    else:
        body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST")
    req.add_header("Content-Type", content_type)
    return opener.open(req)


def fetch_csrf(opener, url):
    r = opener.open(f"{BASE}{url}")
    body = r.read().decode("utf-8", errors="ignore")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    if not m:
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', body)
    return m.group(1) if m else "", body


def login_admin():
    opener = make_opener()
    csrf, _ = fetch_csrf(opener, "/login")
    post(opener, "/login", {
        "username": USER, "password": PWD,
        "usage_consent": "1", "login_mode": "admin",
        "csrf_token": csrf,
    })
    return opener, csrf


def get_csrf(opener, url):
    """获取任意页面的 CSRF token（用于 JSON API 调用）"""
    r = opener.open(f"{BASE}{url}")
    body = r.read().decode("utf-8", errors="ignore")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    return m.group(1) if m else "", body


def post_json(opener, url, payload, csrf=None):
    """POST JSON body"""
    req = urllib.request.Request(
        f"{BASE}{url}",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    if csrf:
        req.add_header("X-CSRFToken", csrf)
    return opener.open(req)


def login_user(username, password):
    opener = make_opener()
    csrf, _ = fetch_csrf(opener, "/login")
    post(opener, "/login", {
        "username": username, "password": password,
        "usage_consent": "1", "login_mode": "user",
        "csrf_token": csrf,
    })
    return opener


def main():
    print('===== BUG-F02-03 验证 =====\n')
    results = []

    def check(name, cond, detail=''):
        results.append((cond, name, detail))
        mark = '✓' if cond else '✗'
        print(f'  [{mark}] {name}' + (f' — {detail}' if detail and not cond else ''))

    # 服务可达性
    try:
        opener, _ = login_admin()
    except Exception as exc:
        print('[FATAL] 登录失败，请先 py audit_screenshots/start_server.py 启动服务:', exc)
        sys.exit(1)
    print('[1] 登录成功\n')

    # 1) 找到第一个标签模板 id
    list_resp = get(opener, "/label_template")
    check('GET /label_template 200', list_resp.status == 200, str(list_resp.status))
    body = list_resp.read().decode("utf-8", errors="ignore")
    template_id = None
    m = re.search(r'href="/label_template/(\d+)"', body)
    if m:
        template_id = int(m.group(1))
    # 获取该页面的 CSRF token（用于后续 JSON API 调用）
    csrf_list = ""
    m_csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    if m_csrf:
        csrf_list = m_csrf.group(1)
    if not template_id:
        api = get(opener, "/label_template/api/list")
        if api.status == 200:
            j = json.loads(api.read().decode("utf-8", errors="ignore"))
            tlist = j.get("templates") or []
            if tlist:
                template_id = tlist[0]["id"]
    check('找到至少 1 个标签模板', template_id is not None, f'id={template_id}')
    check('获取到 list 页面 CSRF token', bool(csrf_list), csrf_list[:20] if csrf_list else 'NONE')

    if not template_id:
        print('\n无模板可测，跳过动态用例')
    else:
        # 2) 空 body 返回 400
        try:
            r0 = opener.open(urllib.request.Request(
                f"{BASE}/label_template/{template_id}/save_layout",
                data=b'', method="POST",
            ))
            code0 = r0.status
        except urllib.error.HTTPError as e:
            code0 = e.code
        check('空 body 返回 400', code0 == 400, f'got {code0}')

        # 3) 正常 layout 返回 200 + success
        good_layout = {
            "cols": 5, "rows": 6,
            "cells": [
                {"x": 0, "y": 0, "field": "material_code", "w": 2, "h": 1},
                {"x": 0, "y": 1, "field": "material_name", "w": 3, "h": 1},
                {"x": 0, "y": 2, "field": "barcode", "w": 5, "h": 2},
            ],
        }
        r1 = post_json(opener, f"/label_template/{template_id}/save_layout",
                       {"layout": good_layout}, csrf=csrf_list)
        r1_body = r1.read().decode("utf-8", errors="ignore")
        j1 = json.loads(r1_body)
        check('正常 layout 返回 200', r1.status == 200, str(r1.status))
        check('响应 status=success', j1.get("status") == "success", str(j1))
        check('响应 msg=布局已保存', '已保存' in j1.get('msg', ''))

        # 4) 二次进入详情页 layout 应回显（含 BUG-F02-03 标记或 material_code 字段）
        detail_resp = get(opener, f"/label_template/{template_id}")
        check('详情页 200', detail_resp.status == 200, str(detail_resp.status))
        detail_body = detail_resp.read().decode("utf-8", errors="ignore")
        check('详情页含新布局字段 material_code', 'material_code' in detail_body)
        check('详情页含 BUG-F02-03 修复标记', 'BUG-F02-03' in detail_body)
        check('saveLayout 含 response.ok 校验', 'response.ok' in detail_body)
        check('saveLayout 含 _savingLayout 守卫', '_savingLayout' in detail_body)
        check('saveLayout 含 spinner-border 反馈', 'spinner-border' in detail_body)

        # 5) 不合法类型（layout=字符串"abc"）应 400
        try:
            r2 = post_json(opener, f"/label_template/{template_id}/save_layout",
                           {"layout": "not-a-object"}, csrf=csrf_list)
            code2 = r2.status
        except urllib.error.HTTPError as e:
            code2 = e.code
        check('字符串 layout 返回 400', code2 == 400, f'got {code2}')

        # 6) 缺 layout 字段应 400
        try:
            r2b = post_json(opener, f"/label_template/{template_id}/save_layout",
                            {"foo": "bar"}, csrf=csrf_list)
            code2b = r2b.status
        except urllib.error.HTTPError as e:
            code2b = e.code
        check('缺 layout 字段返回 400', code2b == 400, f'got {code2b}')

        # 7) 不存在的 template_id 应 404
        try:
            r3 = post_json(opener, "/label_template/99999/save_layout",
                           {"layout": good_layout}, csrf=csrf_list)
            code3 = r3.status
        except urllib.error.HTTPError as e:
            code3 = e.code
        check('不存在 template_id 返回 404', code3 == 404, f'got {code3}')

    # 总结
    print('\n===== 验证结果汇总 =====')
    passed = sum(1 for ok,_,_ in results if ok)
    print(f'通过 {passed} / 总计 {len(results)}')
    if passed != len(results):
        for ok, n, d in results:
            if not ok:
                print(f'  - {n}: {d}')
        sys.exit(1)
    print('全部通过！')


if __name__ == '__main__':
    main()
