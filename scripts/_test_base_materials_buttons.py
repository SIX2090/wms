"""基础资料模块深挖：逐页提取工具栏/行内按钮 + 按钮端点调用 + CRUD。"""
import requests, re, sys, json, time
from _btn_harness import H, BASE, PASS

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

# 页面 -> 需要验证的按钮动作端点
PAGES = {
    '/material':      {'add': '/material/add',      'export': '/material/export', 'template': '/material/download_template'},
    '/category':      {'add': '/category/add'},
    '/unit':          {'add': '/unit/add'},
    '/supplier':      {'add': '/supplier/add',      'import': '/unit_supplier_import', 'template': '/supplier/download_template'},
    '/customer':      {'add': '/customer/add'},
    '/warehouse':     {'add': '/warehouse/add'},
    '/department':    {'add': '/department/add'},
    '/employee':      {'add': '/employee/add'},
    '/contract':      {'add': '/contract/add'},
    '/opening_stock': {'add': '/opening_stock/add'},
    '/bom':           {'add': '/bom/add'},
}

def extract_buttons(path):
    """从渲染 HTML 提取工具栏按钮文本与 href/onclick。"""
    try:
        r = h.s.get(BASE+path, timeout=25)
        html = r.text
        btns = []
        # data-action / 按钮文本
        for m in re.finditer(r'<button[^>]*(?:data-action|class="[^"]*btn)[^>]*>(.*?)</button>', html, re.S):
            label = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            attrs = m.group(0)
            a = re.search(r'data-action="([^"]+)"', attrs)
            o = re.search(r'onclick="([^"]+)"', attrs)
            i = re.search(r'id="([^"]+)"', attrs)
            if label or a or o:
                btns.append({'label': label[:20], 'action': a.group(1) if a else '', 'onclick': (o.group(1)[:60] if o else ''), 'id': i.group(1) if i else ''})
        return r, btns
    except Exception as e:
        return None, []

timestamp = int(time.time())
uid = f'T{timestamp}'

for path, acts in PAGES.items():
    r, btns = extract_buttons(path)
    if r is None:
        h.rec(f'open {path}', False, 'EXC')
        continue
    h.rec(f'open {path}', r.status_code==200, f'HTTP {r.status_code} found {len(btns)} buttons')
    # 打印按钮清单（供人工核对）
    print(f'  [{path}] buttons: {[b["label"] or b["id"] or b["action"] for b in btns]}')
    # 测试新增端点
    if 'add' in acts:
        h.s.get(BASE+path, timeout=15)
        tok = h.csrf()
        hdr = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}
        # 空提交应 400（防 BUG 规则）
        r2 = h.s.post(BASE+acts['add'], json={}, headers=hdr, timeout=25)
        h.rec(f'{path} add-empty', r2.status_code==400, f'HTTP {r2.status_code} {r2.text[:80]}')
    # 导出/模板
    if 'export' in acts:
        r2 = h.s.get(BASE+acts['export'], timeout=30)
        ct = r2.headers.get('Content-Type','')
        h.rec(f'{path} export', r2.status_code==200 and len(r2.content)>0, f'HTTP {r2.status_code} len={len(r2.content)} CT={ct[:30]}')
    if 'template' in acts:
        r2 = h.s.get(BASE+acts['template'], timeout=30)
        h.rec(f'{path} template', r2.status_code==200 and len(r2.content)>0, f'HTTP {r2.status_code} len={len(r2.content)}')

# 分类 CRUD（add 路由用 request.form，须发表单数据）
tok = h.csrf()
hdr = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest'}
r = h.s.post(BASE+'/category/add', data={'name': f'测试分类{uid}', 'code': f'TC{uid[-6:]}'}, headers=hdr, timeout=25)
h.rec('category add', r.status_code in (200,302) and r.text and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

# 单位
r = h.s.post(BASE+'/unit/add', data={'name': f'测试单位{uid}', 'code': f'U{uid[-6:]}'}, headers=hdr, timeout=25)
h.rec('unit add', r.status_code in (200,302) and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

# 供应商
r = h.s.post(BASE+'/supplier/add', data={'code': f'S{uid[-6:]}', 'name': f'测试供应商{uid}', 'contact': '张三', 'phone': '13800000000', 'address': '测试地址'}, headers=hdr, timeout=25)
h.rec('supplier add', r.status_code in (200,302) and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

# 客户
r = h.s.post(BASE+'/customer/add', data={'code': f'C{uid[-6:]}', 'name': f'测试客户{uid}', 'contact': '李四', 'phone': '13900000000', 'address': '客户地址'}, headers=hdr, timeout=25)
h.rec('customer add', r.status_code in (200,302) and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

# 仓库
r = h.s.post(BASE+'/warehouse/add', data={'code': f'W{uid[-6:]}', 'name': f'测试仓库{uid}'}, headers=hdr, timeout=25)
h.rec('warehouse add', r.status_code in (200,302) and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

# 合同
r = h.s.post(BASE+'/contract/add', data={'contract_no': f'HT{uid[-6:]}', 'project_name': f'测试工程{uid}'}, headers=hdr, timeout=25)
h.rec('contract add', r.status_code in (200,302) and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

# 部门（department/add，需部门编码）
r = h.s.post(BASE+'/department/add', data={'code': f'D{uid[-6:]}', 'name': f'测试部门{uid}'}, headers=hdr, timeout=25)
h.rec('department add', r.status_code in (200,302) and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

# 员工（employee/add）
r = h.s.post(BASE+'/employee/add', data={'code': f'E{uid[-6:]}', 'name': f'测试员工{uid}'}, headers=hdr, timeout=25)
h.rec('employee add', r.status_code in (200,302) and 'error' not in r.text.lower(), f'HTTP {r.status_code} {r.text[:80]}')

fails = h.report('基础资料模块-工具栏与CRUD深挖')
sys.exit(1 if fails else 0)