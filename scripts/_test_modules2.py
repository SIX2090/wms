"""综合验证基础资料/报表/系统设置模块：页面可访问性、工具栏占位按钮检测、导出/接口。
检测每页是否存在"功能待开发/待开发/暂未实现/待接入"占位文案（占位=潜在缺陷，需人工判定）。"""
import sys, re
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

PLACEHOLDER_PATTERNS = ['功能待开发', '待开发', '暂未实现', '待接入', '暂未支持', '敬请期待']

def check_page(path, label, detect_placeholder=True):
    try:
        r = h.s.get(BASE + path, timeout=25)
        html = r.text
        err = r.status_code >= 500 or 'Internal Server Error' in html
        ok = r.status_code == 200 and not err
        ph = []
        if detect_placeholder:
            for pat in PLACEHOLDER_PATTERNS:
                if pat in html:
                    ph.append(pat)
        h.rec(f'{label} {path}', ok and not ph, f'HTTP {r.status_code} len={len(html)} placeholder={ph}')
    except Exception as e:
        h.rec(f'{label} {path}', False, f'EXC {e}')

print('===== 基础资料 =====')
BASE_PAGES = [
    '/material', '/material/add', '/category', '/unit', '/supplier',
    '/customer', '/warehouse', '/department', '/employee', '/contract',
    '/opening_stock', '/bom',
]
for p in BASE_PAGES:
    check_page(p, '基础')

print('===== 报表 =====')
REPORT_TYPES = ['inventory','in_detail','out_detail','summary','check','ledger',
                'warehouse_monthly','subcontract','requisition',
                'purchase_order_execution','supplier_purchase_summary',
                'material_purchase_summary','purchase_price_analysis']
for t in REPORT_TYPES:
    check_page(f'/report/view/{t}', '报表视图')
    try:
        r = h.s.get(BASE + f'/report/api/{t}', timeout=30)
        ok = r.status_code == 200 and not r.text.startswith('<!doctype')
        h.rec(f'报表API[{t}]', ok, f'HTTP {r.status_code} {r.text[:60]}')
    except Exception as e:
        h.rec(f'报表API[{t}]', False, f'EXC {e}')
    try:
        r = h.s.get(BASE + f'/report/api/{t}?export=excel', timeout=30)
        ct = r.headers.get('Content-Type','')
        ok = r.status_code==200 and ('spreadsheet' in ct or 'octet-stream' in ct or 'excel' in ct.lower())
        h.rec(f'报表导出[{t}]', ok, f'HTTP {r.status_code} len={len(r.content)} CT={ct[:25]}')
    except Exception as e:
        h.rec(f'报表导出[{t}]', False, f'EXC {e}')

print('===== 系统设置 =====')
SYS_PAGES = [
    '/system_settings', '/user', '/operation_audit', '/approval',
    '/wechat_share', '/backup', '/admin/console', '/admin/mobile_tokens',
    '/ai/prelaunch', '/ai/purchase_workbench', '/ai/sales_workbench',
    '/ai/warehouse_workbench', '/batch_import', '/pending_documents',
]
for p in SYS_PAGES:
    check_page(p, '系统')

h.report('comprehensive')