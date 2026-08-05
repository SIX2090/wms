#!/usr/bin/env python3
"""基础资料模块工具栏/增删改查综合测试（API 级）。"""
import json, re, sys, time, requests

BASE = 'http://127.0.0.1:8080'
_s = requests.Session()
TAG = str(int(time.time())%100000)
_results = []

def record(name, ok, note=''):
    _results.append((name, ok, note))
    print(f'[{"PASS" if ok else "FAIL"}] {name}: {note}')

def csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html) or re.search(r'meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None

def login():
    r = _s.get(BASE+'/login', timeout=20); tok = csrf(r.text)
    return _s.post(BASE+'/login', data={'username':'admin','password':'admin','csrf_token':tok,'login_mode':'admin'}, allow_redirects=False, timeout=20).status_code == 302

if not login():
    print('FATAL login'); sys.exit(1)

def page_ok(path, label):
    r = _s.get(BASE+path, timeout=20)
    record(f'页面 {label} ({path})', r.status_code==200, f'HTTP {r.status_code} len {len(r.text)}')

def exp_ok(path, label):
    r = _s.get(BASE+path, timeout=30)
    ok = r.status_code==200 and len(r.content)>0 and 'spreadsheet' in r.headers.get('Content-Type','')
    record(f'导出 {label}', ok, f'HTTP {r.status_code} len {len(r.content)} CT {r.headers.get("Content-Type","")[:30]}')

def tpl_ok(path, label):
    r = _s.get(BASE+path, timeout=30)
    ok = r.status_code==200 and len(r.content)>0
    record(f'下载模板 {label}', ok, f'HTTP {r.status_code} len {len(r.content)}')

# ── 页面可访问性 ──
for path,label in [('/unit','计量单位'),('/supplier','供应商'),('/customer','客户'),
                   ('/warehouse','仓库'),('/department','部门'),('/employee','员工'),
                   ('/contract','合同'),('/opening_stock','期初库存'),('/bom','BOM'),
                   ('/material','物料档案'),('/category','物料分类')]:
    page_ok(path, label)

# ── 导出 / 下载模板 ──
export_tests = [('/unit/export','计量单位'),('/supplier/export','供应商'),('/customer/export','客户'),
                ('/warehouse/export','仓库'),('/department/export','部门'),('/employee/export','员工'),
                ('/contract/export','合同'),('/opening_stock/export','期初库存'),('/bom/export','BOM'),
                ('/material/export','物料'),('/category/export','分类')]
tpl_tests = [('/unit/download_template','计量单位'),('/supplier/download_template','供应商'),('/customer/download_template','客户'),
             ('/warehouse/download_template','仓库'),('/department/download_template','部门'),('/employee/download_template','员工'),
             ('/contract/download_template','合同'),('/material/download_template','物料'),('/category/download_template','分类')]
for p,l in export_tests: exp_ok(p, l)
for p,l in tpl_tests: tpl_ok(p, l)

# ── 新增/编辑/删除：计量单位 ──
def unit_crud():
    g = _s.get(BASE+'/unit', timeout=20); tok = csrf(g.text)
    code = 'U-'+TAG
    u = {'name':'测试单位'+TAG,'code':code}
    r = _s.post(BASE+'/unit/add', data={**u,'csrf_token':tok}, headers={'X-Requested-With':'XMLHttpRequest'}, allow_redirects=False, timeout=20)
    try: js=r.json(); ok = js.get('status')=='success'; note=json.dumps(js,ensure_ascii=False)[:60]
    except Exception: ok=False; note=r.text[:80]
    record('单位新增', ok, note)
    if ok:
        # find id
        rl = _s.get(BASE+'/unit', timeout=20).text
        # delete via form
        rd = _s.post(BASE+'/unit/delete', data={'id':None,'csrf_token':tok}, headers={'X-Requested-With':'XMLHttpRequest'}, timeout=20, json={'id':js.get('id')})
        try: jd=rd.json(); record('单位删除', jd.get('status')=='success', json.dumps(jd,ensure_ascii=False)[:60])
        except Exception: record('单位删除', rd.status_code==200, rd.text[:80])
unit_crud()

# ── 供应商新增/删除 ──
def supplier_crud():
    g = _s.get(BASE+'/supplier', timeout=20); tok = csrf(g.text)
    code='S-'+TAG
    r = _s.post(BASE+'/supplier/add', data={'code':code,'name':'测试供应商'+TAG,'contact':'','phone':'','address':'','csrf_token':tok}, headers={'X-Requested-With':'XMLHttpRequest'}, allow_redirects=False, timeout=20)
    try: js=r.json(); ok=js.get('status')=='success'; note=json.dumps(js,ensure_ascii=False)[:60]
    except Exception: ok=False; note=r.text[:80]
    record('供应商新增', ok, note)
    if ok:
        rd=_s.post(BASE+'/supplier/delete', json={'id':js.get('id')}, headers={'X-Requested-With':'XMLHttpRequest','X-CSRFToken':tok}, timeout=20)
        try: jd=rd.json(); record('供应商删除', jd.get('status')=='success', json.dumps(jd,ensure_ascii=False)[:60])
        except Exception: record('供应商删除', rd.status_code==200, rd.text[:80])
supplier_crud()

# ── 汇总 ──
ok_c = sum(1 for _,ok,_ in _results if ok); fail = [r for r in _results if not r[1]]
print(f'\n=== 结果: {ok_c}/{len(_results)} PASS, {len(fail)} FAIL ===')
for r in fail: print('  FAIL:', r[0], '->', r[2])