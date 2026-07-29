#!/usr/bin/env python3
"""
其他入库单/其他出库单综合工具栏验证

覆盖：
  1. /other_in_order/add 渲染新工具栏（含 14 个按钮 + 5 个导航按钮）
  2. /other_out_order/add 渲染新工具栏（11 个按钮 + 5 个导航按钮）
  3. /in_order/add 不渲染新工具栏（保留原 page-header）
  4. /out_order/add 不渲染新工具栏（保留原 page-header）
  5. handleOtherOrderToolbar JS 函数存在
  6. CSS 类 .other-order-toolbar/.tool-btn 存在
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, 'app')
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

import app as app_module  # noqa: E402
from app import db  # noqa: E402

flask_app = app_module.app
results = []


def record(name, ok, detail=''):
    results.append((name, 'PASS' if ok else 'FAIL', detail))


def login_admin(client):
    with client.session_transaction() as s:
        s['_user_id'] = '1'
        s['_fresh'] = True


def expect_toolbar(body, url, present):
    has = 'other-order-toolbar' in body
    has_handler = 'handleOtherOrderToolbar' in body
    has_css = '.other-order-toolbar .tool-btn' in body
    if present:
        record(f'{url} 工具栏', has and has_handler and has_css,
               f'has={has} handler={has_handler} css={has_css}')
    else:
        record(f'{url} 不渲染工具栏', not has,
               f'has={has}（期望 False）')


def expect_buttons(body, expected, url):
    for action, expected_count in expected.items():
        # 匹配 data-action="..." 的按钮（含嵌套 <i> 标签）
        actual = body.count(f'data-action="{action}"')
        ok = actual == expected_count
        record(f'{url} "{action}" 按钮',
               ok,
               f'data-action 出现 {actual} 次（期望 {expected_count}）')


with flask_app.app_context():
    c = flask_app.test_client()
    login_admin(c)

    # 1. 其他入库
    rv = c.get('/other_in_order/add')
    assert rv.status_code == 200
    body = rv.data.decode('utf-8', errors='ignore')
    expect_toolbar(body, '/other_in_order/add', True)
    expect_buttons(body, {
        'new': 1, 'save': 1, 'save-and-complete': 1, 'delete': 1,
        'print': 1, 'import': 1, 'export': 1,
        'import-export-template': 1, 'smart-share': 1,
        'nav-first': 1, 'nav-prev': 1, 'nav-next': 1, 'nav-last': 1,
    }, '/other_in_order/add')
    # 不应再有旧按钮
    record('/other_in_order/add 无 "保存草稿"',
           '保存草稿' not in body,
           f'has="保存草稿"={"保存草稿" in body}')
    record('/other_in_order/add 无 "保存并新增"',
           '保存并新增' not in body,
           f'has="保存并新增"={"保存并新增" in body}')

    # 2. 其他出库
    rv = c.get('/other_out_order/add')
    assert rv.status_code == 200
    body2 = rv.data.decode('utf-8', errors='ignore')
    expect_toolbar(body2, '/other_out_order/add', True)
    expect_buttons(body2, {
        'new': 1, 'save': 1, 'save-and-new': 1, 'delete': 1,
        'print': 1, 'import': 1, 'export': 1,
        'import-export-template': 1, 'smart-share': 1,
        'nav-first': 1, 'nav-prev': 1, 'nav-next': 1, 'nav-last': 1,
    }, '/other_out_order/add')
    # 不应有 完成入库
    record('/other_out_order/add 无 "完成入库"',
           '完成入库' not in body2,
           f'has="完成入库"={"完成入库" in body2}')

    # 3. 普通入库不应有工具栏
    rv = c.get('/in_order/add')
    assert rv.status_code == 200
    body3 = rv.data.decode('utf-8', errors='ignore')
    expect_toolbar(body3, '/in_order/add', False)
    record('/in_order/add 保留 "保存草稿"',
           '保存草稿' in body3,
           f'has="保存草稿"={"保存草稿" in body3}')

    # 4. 普通出库不应有工具栏
    rv = c.get('/out_order/add')
    assert rv.status_code == 200
    body4 = rv.data.decode('utf-8', errors='ignore')
    expect_toolbar(body4, '/out_order/add', False)
    record('/out_order/add 保留 "保存并新增"',
           '保存并新增' in body4,
           f'has="保存并新增"={"保存并新增" in body4}')

# 输出报告
print()
print('=' * 80)
print(' 其他入库/出库单 综合工具栏验证')
print('=' * 80)
fail = 0
for name, status, detail in results:
    flag = '[OK]  ' if status == 'PASS' else '[FAIL]'
    print(f'  {flag} {name:48s} {detail}')
    if status != 'PASS':
        fail += 1
print('=' * 80)
print(f' 总计 {len(results)} 项，通过 {len(results) - fail}，失败 {fail}')
print('=' * 80)
sys.exit(0 if fail == 0 else 1)
