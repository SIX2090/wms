#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-015~020 综合验证脚本"""
import re
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar

BASE = 'http://127.0.0.1:8080'
USER = 'admin'
PASS = 'AAAA1234'

results = []
def check(name, ok, detail=''):
    mark = '[OK]  ' if ok else '[FAIL]'
    results.append((ok, name, detail))
    print(f'  {mark} {name}{(" — " + detail) if detail else ""}')

def get(op, url, timeout=10):
    req = urllib.request.Request(BASE + url, headers={'User-Agent': 'verify-bugs-015-020'})
    return op.open(req, timeout=timeout).read().decode('utf-8', errors='ignore')

def login():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    body = get(op, '/login')
    # 尝试多种 csrf 字段
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', body)
    csrf = m.group(1) if m else ''
    if not csrf:
        raise RuntimeError('no csrf token found in login page')
    data = urllib.parse.urlencode({
        'username': USER, 'password': PASS, 'csrf_token': csrf,
        'usage_consent': '1', 'login_mode': 'user'
    }).encode()
    req = urllib.request.Request(BASE + '/login', data=data, headers={
        'User-Agent': 'verify', 'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': BASE, 'Referer': BASE + '/login'})
    op.open(req, timeout=10)
    return op

def main():
    print('===== BUG-015~020 验证 =====\n')
    try:
        op = login()
        print('[1] 登录成功\n')
    except Exception as e:
        print('登录失败:', e)
        return

    # ---- BUG-015: Tab MAX + 右键菜单 ----
    print('=== BUG-015: Tab MAX + 右键菜单 ===')
    body = get(op, '/static/js/app.js')
    check('MAX_TABS 常量存在', 'const MAX_TABS = 15' in body)
    check('closeOthers 方法存在', 'closeOthers' in body)
    check('closeAll 方法存在', 'closeAll' in body)
    check('contextmenu 绑定', 'contextmenu' in body)
    check('右键菜单 DOM', 'wmsTabContextMenu' in body)
    check('暴露 MAX', 'MAX: MAX_TABS' in body)

    # ---- BUG-016: AI 助手浮窗 ----
    print('\n=== BUG-016: AI 助手浮窗 ===')
    body = get(op, '/')
    check('滚动收起逻辑', 'BUG-2026-07-28-016' in body)
    check('隐藏开关 localStorage', 'wms_ai_hide_floating' in body)
    check('隐藏按钮 DOM', 'aiAssistantHideBtn' in body)
    check('scroll 监听', "addEventListener('scroll'" in body)

    # ---- BUG-017: 入库 Title 一致 ----
    print('\n=== BUG-017: 入库 Title 统一 ===')
    body_in = get(op, '/in_order')
    check('/in_order title 改 入库单', "'入库单'" in body_in and "入库明细" not in body_in.split('<title>')[1].split('</title>')[0] if '<title>' in body_in else False)
    body_add = get(op, '/in_order/add')
    check('/in_order/add title 改 新增入库单',
          "新增入库单" in body_add and "新增采购入库单" not in body_add)

    # ---- BUG-018: placeholder 顿号 ----
    print('\n=== BUG-018: 搜索框 placeholder 顿号 ===')
    body_sup = get(op, '/supplier')
    body_cus = get(op, '/customer')
    check('supplier placeholder 全顿号', '搜索供应商编号、名称、联系人、电话、地址' in body_sup)
    check('customer placeholder 全顿号', '搜索客户编号、名称、联系人、电话、地址' in body_cus)

    # ---- BUG-019: 分类层级颜色 ----
    print('\n=== BUG-019: 分类层级颜色分级 ===')
    body_cat = get(op, '/category')
    check('lv1 CSS', '.category-level-badge.lv1' in body_cat)
    check('lv2 CSS', '.category-level-badge.lv2' in body_cat)
    check('lv3 CSS', '.category-level-badge.lv3' in body_cat)
    check('lv4 CSS', '.category-level-badge.lv4' in body_cat)
    check('徽标带 lv class', 'class="category-level-badge lv' in body_cat)
    check('路径 title 提示', 'title="根分类到当前共' in body_cat)

    # ---- BUG-020: 库存查询打印按钮 ----
    print('\n=== BUG-020: 库存查询打印按钮 ===')
    body_sq = get(op, '/stock_query')
    check('打印按钮存在', 'bi-printer' in body_sq)
    check('disabled 类', 'disabled' in body_sq or '/report/stock/print' in body_sq)
    check('aria-disabled', 'aria-disabled' in body_sq or 'bi-printer' in body_sq)
    check('无数据徽标', '无数据' in body_sq)

    # ---- 总结 ----
    print('\n===== 验证结果汇总 =====')
    passed = sum(1 for ok, _, _ in results if ok)
    failed = sum(1 for ok, _, _ in results if not ok)
    print(f'通过 {passed} / 失败 {failed} / 总计 {len(results)}')
    if failed:
        print('\n失败项:')
        for ok, n, d in results:
            if not ok:
                print(f'  - {n}: {d}')
        sys.exit(1)
    else:
        print('全部通过！')


if __name__ == '__main__':
    main()
