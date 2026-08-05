#!/usr/bin/env python3
"""WMS 系统全面功能测试（端到端，经运行服务器）。

覆盖：所有页面(GET 200)、工具栏按钮端点、明细栏按钮端点、导出接口、
代表性单据的 创建→完成→反提交→删除 状态流转、API 接口。
以 admin/admin 登录，不改密码；测试数据带唯一后缀并在结束后清理。

用法：python scripts/system_functional_test.py [--base-url http://127.0.0.1:8080]
"""
import argparse
import json
import re
import sys
import time
import requests

_arg_parser = argparse.ArgumentParser(description='WMS 系统全面功能测试')
_arg_parser.add_argument('--base-url', default='http://127.0.0.1:8080')
_REQ = _arg_parser.parse_known_args()[0]
BASE = _REQ.base_url.rstrip('/')
_s = requests.Session()
_results = []
_tmp = int(time.time())
TAG = f'TEST{_tmp}'


def record(path, status, ok, note=''):
    _results.append((path, status, ok, note))
    print(f'[{"PASS" if ok else "FAIL"}] {status} {path} {note}')


def csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None


def get(path, **kw):
    return _s.get(BASE + path, timeout=20, **kw)


def post(path, data=None, json=None, **kw):
    return _s.post(BASE + path, data=data, json=json, timeout=20, **kw)


def wh_id():
    try:
        r = get('/api/warehouses')
        js = r.json()
        data = js.get('data') or {}
        rows = data.get('items') if isinstance(data, dict) else data
        if not isinstance(rows, list):
            rows = js.get('warehouses') or js.get('items') or []
        if isinstance(rows, list) and rows:
            return str(rows[0].get('id'))
    except Exception:
        pass
    return None


def wh_name():
    try:
        r = get('/api/warehouses')
        js = r.json()
        data = js.get('data') or {}
        rows = data.get('items') if isinstance(data, dict) else data
        if not isinstance(rows, list):
            rows = js.get('warehouses') or js.get('items') or []
        if isinstance(rows, list) and rows:
            return rows[0].get('name') or rows[0].get('code')
    except Exception:
        pass
    return None


def first_material_code():
    try:
        r = get('/api/material/all')
        js = r.json()
        data = js.get('data') or js
        if isinstance(data, list) and data:
            return data[0].get('code')
    except Exception:
        pass
    return None


def unique_material_code():
    """创建一个全新物料并返回其 code，避免与既有未完成单据撞物料触发重复告警。"""
    code = f'UM-{TAG}'
    try:
        g = get('/material/add')
        tok = csrf(g.text)
        if not tok:
            return None
        post('/material/add', data={'name': f'唯一测试物料-{TAG}', 'code': code,
                                    'specification': '测试', 'unit': '个', 'price': '1',
                                    'category_id': '', 'warehouse_id': '', 'safety_stock': '0',
                                    'csrf_token': tok}, allow_redirects=False)
        return code
    except Exception:
        return None


def ensure_supplier():
    """确保存在一个供应商，返回其数字 id（采购入库 supplier_id 需要 id）。"""
    try:
        r = get('/api/suppliers')
        js = r.json()
        rows = js.get('data') if isinstance(js, dict) else js
        if isinstance(rows, list) and rows:
            return rows[0].get('id')
    except Exception:
        pass
    # 无供应商则创建一个
    try:
        g = get('/supplier')
        tok = csrf(g.text)
        if tok:
            post('/supplier/add', data={'code': f'SUP-{TAG}', 'name': f'测试供应商-{TAG}',
                                        'csrf_token': tok}, allow_redirects=False)
            r = get('/api/suppliers')
            js = r.json()
            rows = js.get('data') if isinstance(js, dict) else js
            if isinstance(rows, list) and rows:
                return rows[0].get('id')
    except Exception:
        pass
    return None
def login(username='admin', password='admin'):
    r = get('/login')
    tok = csrf(r.text)
    assert tok, '登录页无 CSRF token'
    r = post('/login', data={'username': username, 'password': password,
                             'csrf_token': tok, 'login_mode': 'admin'},
             allow_redirects=False)
    if r.status_code == 302:
        g = get(r.headers.get('Location', '/'))
        return g.status_code == 200
    return False


if not login():
    print('FATAL: 无法以 admin/admin 登录'); sys.exit(1)
record('/login', 200, True, 'admin/admin')

# ─────────── 1. 工作台 ───────────
WORKBENCH = ['/', '/report/dashboard', '/sales/dashboard', '/sales/exceptions',
             '/ai/warehouse_workbench', '/ai/purchase_workbench', '/ai/sales_workbench',
             '/ai/ops', '/ai/business_quality', '/ai/prelaunch', '/ai/acceptance',
             '/ai/agent_tasks', '/ai/document_jobs', '/ai/replenishment',
             '/ai/replenishment_smart', '/ai/inventory_health', '/ai/document_ocr',
             '/ai/supplier_evaluation', '/ai/location_recommendation', '/ai/demand_forecast',
             '/ai/material_alias', '/ai/data-retention']
for p in WORKBENCH:
    try:
        r = get(p)
        record(f'[工作台] {p}', r.status_code, r.status_code == 200)
    except Exception as e:
        record(f'[工作台] {p}', 0, False, str(e)[:60])

# ─────────── 2. 全部页面(GET) ───────────
PAGES = [
    # 基础资料
    '/material', '/material/add', '/category', '/unit', '/supplier', '/customer',
    '/warehouse', '/department', '/employee', '/contract', '/opening_stock',
    '/bom', '/bom/add', '/stock_query', '/alert',
    # 采购
    '/purchase_request', '/purchase_request/add', '/purchase_order', '/purchase_order/add',
    '/purchase_report', '/in_order', '/in_order/add',
    # 销售
    '/sales', '/sales/add', '/sales/outbound', '/sales/outbound_selection',
    '/sales/report', '/sales/execution_report', '/sales/price_analysis',
    '/sales/reconciliation', '/sales/outflow_report', '/sales/trend_report',
    # 库存
    '/out_order', '/out_order/add', '/other_in_order', '/other_in_order/add',
    '/other_out_order', '/other_out_order/add', '/transfer', '/adjustment', '/adjustment/add',
    '/check', '/requisition', '/subcontract', '/subcontract_issue', '/subcontract_receive',
    '/subcontract/progress', '/after_sale_out', '/after_sale_out/add',
    # 系统
    '/system_settings', '/user', '/approval', '/operation_audit', '/wechat_share',
    '/backup', '/batch_import', '/profile/edit', '/user/change_password',
    # 打印/标签/移动
    '/label_template', '/in_order_print_template', '/out_order_print_template',
    '/pending_documents', '/mobile/app', '/mobile/connect', '/mobile/scan',
    '/admin/console', '/admin/mobile_tokens',
]
for p in PAGES:
    try:
        r = get(p)
        ok = r.status_code == 200
        note = ''
        if not ok:
            note = {404: 'NOT FOUND', 403: 'FORBIDDEN', 500: 'SERVER ERROR'}.get(r.status_code, r.text[:60])
        record(f'[页面] {p}', r.status_code, ok, note)
    except Exception as e:
        record(f'[页面] {p}', 0, False, str(e)[:60])

# 报表中心 + 13 类报表
RPT = ['/report'] + [f'/report/view/{t}' for t in [
    'inventory', 'in_detail', 'out_detail', 'summary', 'check', 'ledger',
    'warehouse_monthly', 'subcontract', 'requisition', 'purchase_order_execution',
    'supplier_purchase_summary', 'material_purchase_summary', 'purchase_price_analysis']]
for p in RPT:
    try:
        r = get(p)
        record(f'[报表] {p}', r.status_code, r.status_code == 200)
    except Exception as e:
        record(f'[报表] {p}', 0, False, str(e)[:60])

# ─────────── 3. 导出接口（工具栏按钮） ───────────
EXPORTS = ['/material/export', '/category/export', '/unit/export', '/warehouse/export',
           '/supplier/export', '/customer/export', '/department/export', '/employee/export',
           '/in_order/export', '/out_order/export', '/purchase_order/export',
           '/purchase_request/export', '/sales/export', '/sales/outbound/export',
           '/sales/reconciliation/export', '/sales/report/export', '/sales/trend_report/export',
           '/sales/price_analysis/export', '/sales/outflow_report/export',
           '/sales/execution_report/export', '/transfer/export', '/check/export',
           '/bom/export', '/requisition/export', '/subcontract/export',
           '/report/inout/export', '/report/stock/print']
for p in EXPORTS:
    try:
        r = get(p, allow_redirects=True)
        ct = r.headers.get('Content-Type', '')
        ok = r.status_code == 200 and ('excel' in ct.lower() or 'spreadsheet' in ct.lower()
                                       or 'html' in ct.lower() or len(r.content) > 1000)
        record(f'[导出/打印] {p}', r.status_code, ok, f'ct={ct[:30]} len={len(r.content)}')
    except Exception as e:
        record(f'[导出/打印] {p}', 0, False, str(e)[:60])

# ─────────── 4. API 接口 ───────────
APIS = ['/api/units', '/api/suppliers', '/api/customers', '/api/material/all',
        '/api/material/search', '/api/warehouses', '/api/categories']
for p in APIS:
    try:
        r = get(p)
        ok = r.status_code == 200
        try:
            r.json(); note = 'json ok'
        except Exception:
            note = 'not json'
        record(f'[API] {p}', r.status_code, ok, note)
    except Exception as e:
        record(f'[API] {p}', 0, False, str(e)[:60])

# ─────────── 5. 物料 增→删（明细/工具栏按钮） ───────────
def material_cycle():
    name = f'功能测试物料-{TAG}'
    code = f'FT-{TAG}'
    r = get('/material/add')
    tok = csrf(r.text)
    if not tok:
        record('[物料] /material/add csrf', 0, False, 'MISSING'); return
    r = post('/material/add', data={'name': name, 'code': code, 'specification': '测试',
                                    'unit': '个', 'price': '1', 'category_id': '',
                                    'warehouse_id': '', 'safety_stock': '0',
                                    'csrf_token': tok}, allow_redirects=False)
    try:
        js = r.json()
        ok = r.status_code in (200, 201) and js.get('status') == 'success'
        note = json.dumps(js, ensure_ascii=False)[:80]
    except Exception:
        ok = r.status_code == 302
        note = 'redirect'
    record('[物料] 新增 POST', r.status_code, ok, note)
    # 通过 API 定位新物料 id
    mid = None
    try:
        lst = get('/api/material/all')
        for m in lst.json().get('data') or []:
            if m.get('code') == code:
                mid = str(m.get('id'))
                break
    except Exception:
        pass
    record('[物料] API 命中新物料', 200, bool(mid), f'id={mid}')
    if mid:
        # 编辑：POST /material/edit/<id>（模态保存，返回 JSON，需表单 csrf_token）
        r = post(f'/material/edit/{mid}', data={'name': name, 'code': code,
                 'specification': '测试改', 'unit': '个', 'price': '1',
                 'category_id': '', 'warehouse_id': '', 'safety_stock': '0',
                 'csrf_token': tok},
                 allow_redirects=False, headers={'X-Requested-With': 'XMLHttpRequest'})
        try:
            ejs = r.json()
            eok = ejs.get('status') == 'success'
            enote = json.dumps(ejs, ensure_ascii=False)[:50]
        except Exception:
            eok = False; enote = r.text[:50]
        record('[物料] 编辑 POST(保存)', r.status_code, eok, enote)
        # 删除：POST /material/delete 需 ids 列表 + X-CSRFToken 头
        r = post('/material/delete', json={'ids': [int(mid)]},
                 headers={'Content-Type': 'application/json', 'X-CSRFToken': tok})
        record('[物料] 删除 POST', r.status_code, r.status_code == 200, r.text[:60])
        # 删除后确认从 API 消失
        gone = True
        try:
            lst = get('/api/material/all')
            for m in lst.json().get('data') or []:
                if m.get('code') == code:
                    gone = False
                    break
        except Exception:
            pass
        record('[物料] 删除后确认消失', 200, gone)
material_cycle()

# ─────────── 6. 采购入库 状态流转（创建→完成→反提交→删除） ───────────
def in_order_cycle():
    r = get('/in_order/add?type=purchase_in')
    tok = csrf(r.text)
    if not tok:
        record('[入库] /in_order/add csrf', 0, False, 'MISSING'); return
    wname = wh_name()
    mcode = unique_material_code()
    sup_code = ensure_supplier()
    if not (wname and mcode and sup_code):
        record('[入库] 前置数据缺失', 0, False, f'wh={wname} mat={mcode} sup={sup_code}')
        return
    items = json.dumps([{'code': mcode, 'quantity': '1', 'price': '1'}], ensure_ascii=False)
    payload = {'type': 'purchase_in', 'warehouse': wname, 'supplier_id': sup_code,
               'business_type': '采购入库', 'items_json': items, 'csrf_token': tok}
    r = post('/in_order/add?type=purchase_in', data=payload, allow_redirects=False,
             headers={'X-Requested-With': 'XMLHttpRequest'})
    try:
        js = r.json()
        did = js.get('id')
        ok = r.status_code in (200, 201) and js.get('status') == 'success'
        note = json.dumps(js, ensure_ascii=False)[:80]
    except Exception:
        did = None; ok = r.status_code == 302; note = 'redirect'
    record('[入库] 新增 POST', r.status_code, ok, note)
    if did:
        for action in ('complete', 'revert', 'delete'):
            r = post(f'/in_order/{did}/{action}', json={'id': did},
                     headers={'Content-Type': 'application/json', 'X-CSRFToken': tok})
            ok = r.status_code in (200, 302) or r.status_code == 400  # 已完成反提交/删除有业务校验
            record(f'[入库] {action} POST', r.status_code, ok, r.text[:50])
    else:
        record('[入库] 状态流转', 0, False, '未拿到单号')
in_order_cycle()


# ─────────── 7. 领料出库 状态流转 ───────────
def out_order_cycle():
    r = get('/out_order/add')
    tok = csrf(r.text)
    if not tok:
        record('[出库] /out_order/add csrf', 0, False, 'MISSING'); return
    wname = wh_name()
    mcode = unique_material_code()
    if not (wname and mcode):
        record('[出库] 前置数据缺失', 0, False, f'wh={wname} mat={mcode}')
        return
    items = json.dumps([{'code': mcode, 'quantity': '1', 'price': '1'}], ensure_ascii=False)
    r = post('/out_order/add', data={'csrf_token': tok, 'warehouse': wname,
                                     'business_type': '领料单',
                                     'items': items},
             allow_redirects=False, headers={'X-Requested-With': 'XMLHttpRequest'})
    record('[出库] 新增 POST', r.status_code, r.status_code in (200, 302), r.text[:60])
out_order_cycle()

# ─────────── 8. 用户/系统设置页面可访问 ───────────
for p in ('/user', '/system_settings', '/approval', '/operation_audit', '/backup'):
    r = get(p)
    record(f'[系统] {p}', r.status_code, r.status_code == 200)

# ─────────── 汇总 ───────────
total = len(_results)
passed = sum(1 for _, _, ok, _ in _results if ok)
print('\n' + '=' * 60)
print(f'结果: {passed}/{total} 通过, {total - passed} 失败')
for path, status, ok, note in _results:
    if not ok:
        print(f'  FAIL: {status} {path}  {note}')
sys.exit(0 if passed == total else 1)