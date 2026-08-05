"""全面验证所有单据/库存/售后模块的列表页、新增页、列表导出、模板下载路由可访问性，
并检测各新增页是否存在"待开发/暂未实现/待接入"占位工具栏分支。"""
import sys
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

# (路径, 标签) 列表页
LIST_PAGES = [
    ('/purchase_request', '采购申请-列表'),
    ('/purchase_order', '采购订单-列表'),
    ('/in_order', '采购入库-列表'),
    ('/other_in_order', '其他入库-列表'),
    ('/other_out_order', '其他出库-列表'),
    ('/sales', '销售订单-列表'),
    ('/sales/outbound', '销售出库-列表'),
    ('/after_sale_out', '售后出库-列表'),
    ('/transfer', '库存调拨-列表'),
    ('/check', '库存盘点-列表'),
    ('/adjustment', '库存调整-列表'),
    ('/requisition', '领料出库-列表'),
    ('/subcontract', '委外-列表'),
]

# 新增页路径
ADD_PAGES = [
    '/purchase_request/add',
    '/purchase_order/add',
    '/in_order/add',
    '/other_in_order/add',
    '/other_out_order/add',
    '/sales/add',
    '/after_sale_out/add',
    '/transfer/add',
    '/check/add',
    '/adjustment/add',
    '/requisition/add',
    '/subcontract/add',
]

print('\n===== 列表页 =====')
for p, label in LIST_PAGES:
    h.page(p, f'列表[{label}] {p}')

print('\n===== 新增页 =====')
for p in ADD_PAGES:
    h.page(p, f'新增页 {p}')

print('\n===== 列表导出/模板路由 =====')
h.export('/in_order/export', '采购入库-列表导出')
h.export('/out_order/export', '销售出库-列表导出')

print('\n===== 新增页占位工具栏检测 =====')
# 检测复用 _other_order_toolbar 的页面及其 handleOtherOrderToolbar 是否含待开发占位
for p in ['/in_order/add', '/other_in_order/add', '/out_order/add', '/other_out_order/add']:
    try:
        r = h.s.get(BASE + p, timeout=25)
        html = r.text
        has_toolbar = '_other_order_toolbar' in html or 'other-order-toolbar' in html
        has_placeholder = ('功能待开发' in html or '待接入' in html or '暂未实现' in html)
        # 提取 handleOtherOrderToolbar 中 import/export 分支
        import re
        m = re.search(r"function handleOtherOrderToolbar\((.*?)</script>", html, re.S)
        branch = ''
        if m:
            seg = m.group(1)
            if '功能待开发' in seg:
                branch = 'import/export/smart-share 均走待开发占位'
        detail = f'reused_toolbar={has_toolbar} placeholder={has_placeholder} {branch}'
        h.rec(f'占位检测 {p}', has_toolbar and has_placeholder, detail)
    except Exception as e:
        h.rec(f'占位检测 {p}', False, f'EXC {e}')

h.report('all_docs_pages')