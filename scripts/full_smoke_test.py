#!/usr/bin/env python3
"""WMS 全面冒烟测试：登录 + 页面遍历 + 表单提交 + 导出接口"""
import requests
import re
import json
import sys
import time

BASE = 'http://127.0.0.1:8080'
s = requests.Session()

results = []


def record(path, status, ok, note=''):
    results.append((path, status, ok, note))
    marker = 'PASS' if ok else 'FAIL'
    print(f'[{marker}] {status} {path} {note}')


def get_csrf_from_html(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'meta name="csrf-token" content="([^"]+)"', html)
    if m:
        return m.group(1)
    return None


def try_login(username, password):
    """尝试登录，返回是否成功"""
    r = s.get(BASE + '/login')
    if r.status_code != 200:
        return False
    token = get_csrf_from_html(r.text)
    if not token:
        return False
    
    r = s.post(BASE + '/login', data={
        'username': username,
        'password': password,
        'csrf_token': token,
        'login_mode': 'admin',
    }, allow_redirects=False)
    
    if r.status_code == 302:
        loc = r.headers.get('Location', '')
        r2 = s.get(BASE + loc)
        return r2.status_code == 200
    return False


# ─────────── 1. 登录页 ───────────
print('=== 1. Login page ===')
r = s.get(BASE + '/login')
record('/login', r.status_code, r.status_code == 200)
token = get_csrf_from_html(r.text)
assert token, '登录页无 CSRF token'
record('CSRF token on login page', 200, True, 'found')

# ─────────── 2. 登录尝试（多个密码） ───────────
print('\n=== 2. Login submit ===')
passwords_to_try = ['admin', 'Admin@123', 'Admin123', '123456', 'admin123']
login_ok = False
used_password = None

for pwd in passwords_to_try:
    if try_login('admin', pwd):
        login_ok = True
        used_password = pwd
        print(f'[PASS] Login successful with password: {pwd}')
        break
    else:
        print(f'[INFO] Login failed with password: {pwd}')
        s = requests.Session()  # reset session

record('/login (POST)', 200 if login_ok else 401, login_ok,
       f'password={used_password}' if login_ok else 'all passwords failed')

if not login_ok:
    print('\nFATAL: Cannot login. Aborting test.')
    sys.exit(1)

# ─────────── 3. 修改密码（首次登录强制） ───────────
print('\n=== 3. Change password (if needed) ===')
r = s.get(BASE + '/user/change_password')
record('/user/change_password', r.status_code, r.status_code == 200)

cp_token = get_csrf_from_html(r.text)
if cp_token:
    record('change_password csrf', 200, True, 'token found')
    
    if used_password == 'admin':
        r = s.post(BASE + '/user/change_password', data={
            'current_password': 'admin',
            'new_password': 'Admin@123',
            'confirm_password': 'Admin@123',
            'csrf_token': cp_token
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        record('/user/change_password (POST)', r.status_code, r.status_code == 200)
        try:
            d = r.json()
            ok = d.get('status') == 'success'
            record('  result', 200, ok, d.get('msg', ''))
        except:
            record('  result', 0, False, 'not JSON - might be redirect (success)')
            if r.status_code in (200, 302):
                used_password = 'Admin@123'
else:
    record('change_password csrf', 0, False, 'MISSING csrf_token!')

# ─────────── 4. 首页 / Dashboard ───────────
print('\n=== 4. Dashboard ===')
r = s.get(BASE + '/')
record('/', r.status_code, r.status_code == 200)

r = s.get(BASE + '/report/dashboard')
record('/report/dashboard', r.status_code, r.status_code == 200)

# ─────────── 5. 列表页遍历（GET） ───────────
print('\n=== 5. List pages (GET) ===')

list_pages = [
    '/material', '/material/add',
    '/category',
    '/unit',
    '/warehouse',
    '/supplier', '/customer',
    '/department', '/employee',
    '/stock_query',
    '/opening_stock',
    '/in_order', '/in_order/add',
    '/out_order', '/out_order/add',
    '/purchase_request', '/purchase_request/add',
    '/purchase_order', '/purchase_order/add',
    '/purchase_report',
    '/sales', '/sales/add',
    '/sales/dashboard',
    '/sales/outbound',
    '/sales/reconciliation',
    '/sales/report',
    '/sales/trend_report',
    '/sales/price_analysis',
    '/sales/outflow_report',
    '/sales/execution_report',
    '/sales/exceptions',
    '/transfer',
    '/check',
    '/bom', '/bom/add',
    '/requisition',
    '/subcontract',
    '/subcontract_issue', '/subcontract_receive',
    '/approval',
    '/user',
    '/system_settings',
    '/backup',
    '/operation_audit',
    '/batch_import',
    '/label_template',
    '/in_order_print_template',
    '/out_order_print_template',
    '/report',
    '/report/dashboard',
    '/pending_documents',
    '/ai/sales_workbench',
    '/ai/purchase_workbench',
    '/ai/warehouse_workbench',
    '/ai/replenishment',
    '/ai/replenishment_smart',
    '/ai/inventory_health',
    '/ai/document_jobs',
    '/ai/material_alias',
    '/ai/agent_tasks',
    '/ai/data-retention',
    '/ai/business_quality',
    '/mobile/app',
    '/mobile/connect',
    '/mobile/scan',
    '/wechat_share',
    '/admin/console',
    '/admin/mobile_tokens',
    '/adjustment',
    '/adjustment/add',
    '/after_sale_out',
    '/after_sale_out/add',
    '/alert',
    '/ai/ops',
    '/ai/prelaunch',
    '/ai/acceptance',
    '/ai/location_recommendation',
    '/ai/demand_forecast',
    '/ai/supplier_evaluation',
]

for path in list_pages:
    try:
        r = s.get(BASE + path, timeout=15)
        ok = r.status_code == 200
        note = ''
        if not ok:
            if r.status_code == 404:
                note = 'NOT FOUND'
            elif r.status_code == 401:
                note = 'NOT LOGGED IN'
            elif r.status_code == 403:
                note = 'FORBIDDEN'
            else:
                note = r.text[:80].replace('\n', ' ')
        record(path, r.status_code, ok, note)
    except Exception as e:
        record(path, 0, False, str(e)[:80])

# ─────────── 6. 导出接口 ───────────
print('\n=== 6. Export endpoints ===')
export_pages = [
    '/material/export',
    '/category/export',
    '/unit/export',
    '/warehouse/export',
    '/supplier/export',
    '/customer/export',
    '/department/export',
    '/employee/export',
    '/in_order/export',
    '/out_order/export',
    '/purchase_order/export',
    '/purchase_request/export',
    '/sales/export',
    '/sales/outbound/export',
    '/sales/reconciliation/export',
    '/sales/report/export',
    '/sales/trend_report/export',
    '/sales/price_analysis/export',
    '/sales/outflow_report/export',
    '/sales/execution_report/export',
    '/transfer/export',
    '/check/export',
    '/bom/export',
    '/requisition/export',
    '/subcontract/export',
]

for path in export_pages:
    try:
        r = s.get(BASE + path, timeout=15, allow_redirects=True)
        ok = r.status_code == 200
        ct = r.headers.get('Content-Type', '')[:50]
        note = f'content-type={ct} len={len(r.content)}'
        if 'excel' in ct.lower() or 'spreadsheet' in ct.lower() or len(r.content) > 1000:
            ok = True
        record(path, r.status_code, ok, note)
    except Exception as e:
        record(path, 0, False, str(e)[:80])

# ─────────── 7. 新增物料（表单提交测试） ───────────
print('\n=== 7. Material add (form submit) ===')
r = s.get(BASE + '/material/add')
record('/material/add (GET)', r.status_code, r.status_code == 200)
mat_token = get_csrf_from_html(r.text)
if mat_token:
    record('/material/add CSRF', 200, True, 'token found')
    r = s.post(BASE + '/material/add', data={
        'name': '测试物料-' + str(int(time.time())),
        'code': 'TEST' + str(int(time.time())),
        'specification': '测试规格',
        'unit': '个',
        'category_id': '',
        'warehouse_id': '',
        'safety_stock': 0,
        'price': 0,
        'csrf_token': mat_token
    }, allow_redirects=False)
    ok = r.status_code in (200, 302)
    record('/material/add (POST)', r.status_code, ok,
           'redirected' if r.status_code == 302 else '')
else:
    record('/material/add csrf', 0, False, 'MISSING')

# ─────────── 8. API 接口 ───────────
print('\n=== 8. API endpoints (GET) ===')
api_pages = [
    '/api/units',
    '/api/suppliers',
    '/api/customers',
    '/api/material/all',
    '/api/material/search',
]

for path in api_pages:
    try:
        r = s.get(BASE + path, timeout=10)
        ok = r.status_code == 200
        try:
            r.json()
            note = 'json ok'
        except:
            note = 'not json'
        if r.status_code == 401:
            note = 'NOT LOGGED IN'
        record(path, r.status_code, ok, note)
    except Exception as e:
        record(path, 0, False, str(e)[:80])

# ─────────── 总结 ───────────
print('\n' + '=' * 60)
total = len(results)
passed = sum(1 for _, _, ok, _ in results if ok)
failed = total - passed
print(f'Results: {passed}/{total} passed, {failed} failed')

if failed > 0:
    print('\nFAILED ITEMS:')
    for path, status, ok, note in results:
        if not ok:
            print(f'  FAIL: {status} {path}  {note}')
    sys.exit(1)
else:
    print('All tests passed!')
    sys.exit(0)
