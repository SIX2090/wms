"""报表模块测试：13类报表 视图页 + API 查询 + Excel导出。"""
import sys, time
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

TYPES = ['inventory','in_detail','out_detail','summary','check','ledger',
         'warehouse_monthly','subcontract','requisition',
         'purchase_order_execution','supplier_purchase_summary',
         'material_purchase_summary','purchase_price_analysis']

for t in TYPES:
    # 视图页
    h.page(f'/report/view/{t}', f'报表视图[{t}]')
    # API 查询(JSON)
    try:
        r = h.s.get(BASE+f'/report/api/{t}', timeout=30)
        ok = r.status_code==200
        h.rec(f'报表API[{t}]', ok, f'HTTP {r.status_code} {r.text[:80]}')
    except Exception as e:
        h.rec(f'报表API[{t}]', False, f'EXC {e}')
    # Excel 导出
    try:
        r = h.s.get(BASE+f'/report/api/{t}?export=excel', timeout=30)
        ct = r.headers.get('Content-Type','')
        ok = r.status_code==200 and ('spreadsheet' in ct or 'octet-stream' in ct or 'excel' in ct.lower())
        h.rec(f'报表导出[{t}]', ok, f'HTTP {r.status_code} len={len(r.content)} CT={ct[:30]}')
    except Exception as e:
        h.rec(f'报表导出[{t}]', False, f'EXC {e}')

# 报表中心首页 + dashboard
h.page('/report', '报表中心')
h.page('/report/dashboard', '报表dashboard')
h.page('/purchase_report', '采购报表')
h.page('/stock_query', '库存查询')
h.page('/alert', '库存预警')
# 打印端点
h.page('/report/print', '报表打印')
h.page('/report/inout/print', '出入库打印')

h.report('报表模块')