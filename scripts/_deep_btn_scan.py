"""深度按钮扫描：登录后逐页抓取页面内所有内部链接(href)与按钮,读取真实URL并验证有无404/500/异常。
不会猜测URL,而是从渲染后的HTML中提取真实按钮链接,避免误报。"""
import requests, re, sys, time
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

# 需要扫描的页面(模块 -> 页面路径列表)
PAGES = {
    '基础资料': ['/material','/category','/unit','/supplier','/customer','/warehouse',
              '/department','/employee','/contract','/opening_stock','/bom'],
    '采购': ['/purchase_request','/purchase_order','/in_order','/other_in_order'],
    '销售': ['/sales','/sales/outbound','/after_sale_out'],
    '库存': ['/out_order','/other_out_order','/transfer','/check','/adjustment','/requisition','/subcontract'],
    '报表': ['/report','/stock_query','/alert','/sales/report','/sales/reconciliation',
            '/sales/outflow_report','/sales/trend_report','/sales/execution_report','/sales/price_analysis',
            '/sales/exceptions','/sales/dashboard'],
    '系统': ['/admin/console','/user','/operation_audit','/system_settings','/approval','/wechat_share',
            '/ai/prelaunch','/ai/acceptance'],
    '工作台': ['/','/ai/purchase_workbench','/ai/sales_workbench','/ai/warehouse_workbench','/batch_import',
              '/pending_documents'],
}

def norm(u):
    if u.startswith('/'): return u.split('?')[0]
    return None

def is_internal(p):
    return p and p.startswith('/') and not p.startswith('//')

existing_endpoints = set()
# 预收集所有已注册路由,用于判断返回404是"路由不存在"还是"仅方法不符"
# 用 GET 探测所有收集到的内部路径

all_links = {}
for mod, paths in PAGES.items():
    for page in paths:
        try:
            r = h.s.get(BASE+page, timeout=25)
            if r.status_code != 200:
                h.rec(f'{mod} 页面[{page}]', False, f'HTTP {r.status_code}')
                continue
            # 提取所有 a[href] 内部链接
            hrefs = set()
            for m in re.finditer(r'href=["\'](/[^"\'#?]+)(\?[^"\']*)?["\']', r.text):
                p = m.group(1)
                if is_internal(p):
                    hrefs.add(p)
            # 排除静态资源与导航(导航链接不代表当前页功能,但也可测)
            all_links[page] = sorted(hrefs)
        except Exception as e:
            h.rec(f'{mod} 页面[{page}]', False, f'EXC {e}')

# 汇总所有要去重的内部路径
candidates = set()
for page, links in all_links.items():
    for l in links:
        candidates.add(l)

# 逐个 GET 探测
print(f'\n=== 共收集 {len(candidates)} 个内部链接,逐一探测 ===')
for p in sorted(candidates):
    try:
        r = h.s.get(BASE+p, timeout=25)
        ct = r.headers.get('Content-Type','')
        is_html = 'text/html' in ct
        if r.status_code == 404:
            h.rec(f'404 {p}', False, f'HTTP 404')
        elif r.status_code >= 500:
            h.rec(f'5xx {p}', False, f'HTTP {r.status_code}')
        elif r.status_code == 200 and is_html and ('Internal Server Error' in r.text or 'Traceback (most recent call last)' in r.text):
            h.rec(f'500内嵌 {p}', False, '页面内含500 traceback')
    except Exception as e:
        h.rec(f'EXC {p}', False, f'EXC {e}')

fails = h.report('深度链接扫描')
print('\n=== 各页面收集到的内部链接数量 ===')
for page, links in all_links.items():
    print(f'{page}: {len(links)} 链接')