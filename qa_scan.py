#!/usr/bin/env python3
"""WMS Menu Availability Scan - HTTP status code batch check."""
import requests
import json
import re
from datetime import datetime

base = 'http://127.0.0.1:8080'
s = requests.Session()

# Login
r = s.post(f'{base}/login', data={
    'username': 'admin', 'password': 'admin',
    'login_mode': 'user', 'next': '',
}, allow_redirects=True)
print(f'Login: {r.status_code}, authenticated: {"首页" in r.text or "仓库管理" in r.text}')

pages = [
    ('/', '首页', '首页'),
    ('/purchase_request', '采购申请列表', '采购管理'),
    ('/purchase_order?view=list', '采购订单列表', '采购管理'),
    ('/in_order', '入库明细', '采购/库存'),
    ('/supplier', '供应商管理', '采购/基础资料'),
    ('/purchase_report', '采购报表', '采购管理'),
    ('/ai/replenishment', 'AI补货建议', '采购管理'),
    ('/report/view/purchase_order_execution', '采购订单执行统计表', '采购报表'),
    ('/report/view/supplier_purchase_summary', '供应商采购汇总表', '采购报表'),
    ('/report/view/material_purchase_summary', '物料采购汇总表', '采购报表'),
    ('/report/view/purchase_price_analysis', '采购价格分析表', '采购报表'),
    ('/report/view/in_detail', '采购入库明细报表', '采购报表'),
    ('/sales/dashboard', '销售工作台', '销售管理'),
    ('/sales/exceptions', '销售异常工作台', '销售管理'),
    ('/sales', '销售订单列表', '销售管理'),
    ('/sales/outbound_selection', '销售出库选单', '销售管理'),
    ('/sales/outbound', '销售出库列表', '销售管理'),
    ('/customer', '客户管理', '销售/基础资料'),
    ('/sales/report', '销售报表', '销售管理'),
    ('/sales/execution_report', '销售订单执行', '销售管理'),
    ('/sales/price_analysis', '销售价格分析', '销售管理'),
    ('/sales/reconciliation', '销售对账', '销售管理'),
    ('/transfer', '库存调拨', '库存管理'),
    ('/check', '库存盘点', '库存管理'),
    ('/out_order', '领料明细', '库存管理'),
    ('/bom', 'BOM管理', '库存管理'),
    ('/requisition', '工单领料', '库存管理'),
    ('/subcontract', '委外管理', '库存管理'),
    ('/report/dashboard', '数据仪表盘', '库存管理'),
    ('/ai/replenishment_smart', '智能补货建议', '库存-AI'),
    ('/ai/inventory_health', '库存健康度', '库存-AI'),
    ('/ai/document_ocr', '单据OCR识别', '库存-AI'),
    ('/ai/supplier_evaluation', '供应商智能评估', '库存-AI'),
    ('/ai/location_recommendation', '智能库位推荐', '库存-AI'),
    ('/ai/demand_forecast', '需求预测', '库存-AI'),
    ('/report/view/inventory', '库存报表', '库存报表'),
    ('/report/view/out_detail', '领料明细报表', '库存报表'),
    ('/report/view/summary', '出入库汇总报表', '库存报表'),
    ('/report/view/check', '盘点报表', '库存报表'),
    ('/report/view/ledger', '库存台账', '库存报表'),
    ('/report/view/warehouse_monthly', '仓库月报表', '库存报表'),
    ('/report/view/requisition', '工单领料报表', '库存报表'),
    ('/report/view/subcontract', '委外加工报表', '库存报表'),
    ('/material', '物料管理', '基础资料'),
    ('/opening_stock', '期初库存', '基础资料'),
    ('/category', '物料分类', '基础资料'),
    ('/unit', '计量单位', '基础资料'),
    ('/warehouse', '仓库档案', '基础资料'),
    ('/department', '部门档案', '基础资料'),
    ('/employee', '员工管理', '基础资料'),
    ('/system_settings', '系统设置', '系统管理'),
    ('/ai/ops', 'AI运维看板', '系统管理'),
    ('/ai/business_quality', 'AI质量运营', '系统管理'),
    ('/ai/prelaunch', 'AI上线预检', '系统管理'),
    ('/ai/acceptance', 'AI七日验收', '系统管理'),
    ('/user', '用户管理', '系统管理'),
    ('/approval', '审批中心', '系统管理'),
    ('/operation_audit', '操作审计', '系统管理'),
    ('/mobile/app', '下载扫码APP', '手机扫码'),
    ('/mobile/scan?mode=in', '手工入库', '手机扫码'),
    ('/mobile/scan?mode=out', '手工出库', '手机扫码'),
    ('/mobile/scan?mode=check', '手工盘点', '手机扫码'),
    ('/mobile/scan?mode=query', '手工查询', '手机扫码'),
]

results = []
errors = []
ok = 0
redir = 0
c4 = 0
c5 = 0

print(f'\n{"="*70}')
print(f'WMS Menu Scan - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print(f'{"="*70}')

for url, name, group in pages:
    try:
        r = s.get(f'{base}{url}', allow_redirects=False, timeout=10)
        st = r.status_code
        title = ''
        if st == 200:
            m = re.search(r'<title>(.*?)</title>', r.text, re.I | re.DOTALL)
            title = m.group(1).strip() if m else '(no title)'
        if 200 <= st < 300:
            ok += 1
            results.append({'url': url, 'name': name, 'group': group, 'status': st, 'title': title, 'result': 'OK'})
        elif 300 <= st < 400:
            loc = r.headers.get('Location', '')
            if '/login' in loc:
                errors.append({'url': url, 'name': name, 'group': group, 'status': st, 'detail': 'Redirect to login'})
                results.append({'url': url, 'name': name, 'group': group, 'status': st, 'title': '', 'result': 'FAIL-LOGIN'})
            else:
                redir += 1
                results.append({'url': url, 'name': name, 'group': group, 'status': st, 'title': f'-> {loc}', 'result': 'REDIRECT'})
        elif 400 <= st < 500:
            c4 += 1
            errors.append({'url': url, 'name': name, 'group': group, 'status': st, 'detail': r.text[:200]})
            results.append({'url': url, 'name': name, 'group': group, 'status': st, 'title': '', 'result': f'FAIL-{st}'})
        elif st >= 500:
            c5 += 1
            errors.append({'url': url, 'name': name, 'group': group, 'status': st, 'detail': r.text[:200]})
            results.append({'url': url, 'name': name, 'group': group, 'status': st, 'title': '', 'result': f'FAIL-{st}'})
        icon = '\033[92m' if st == 200 else '\033[91m' if st >= 400 else '\033[93m'
        print(f'  [{icon}{st}\033[0m] [{group:12s}] {name:28s} -> {title or "(redirect/error)"}')
    except Exception as e:
        errors.append({'url': url, 'name': name, 'group': group, 'status': 0, 'detail': str(e)})
        results.append({'url': url, 'name': name, 'group': group, 'status': 0, 'title': '', 'result': f'EXC: {e}'})
        print(f'  [\033[91mERR\033[0m] [{group:12s}] {name:28s} -> {e}')

print(f'\n{"="*70}')
print(f'Summary: {ok} OK, {redir} Redirect, {c4} 4xx, {c5} 5xx, Total: {len(pages)}')
if errors:
    print(f'\nERRORS ({len(errors)}):')
    for e in errors:
        print(f'  [{e["status"]}] {e["name"]}: {e["detail"][:100]}')

with open('/workspace/qa_scan_results.json', 'w', encoding='utf-8') as f:
    json.dump({
        'scan_time': datetime.now().isoformat(),
        'total': len(pages), 'ok': ok, 'redirect': redir,
        'client_errors': c4, 'server_errors': c5,
        'results': results, 'errors': errors,
    }, f, ensure_ascii=False, indent=2)
print(f'\nSaved to /workspace/qa_scan_results.json')
