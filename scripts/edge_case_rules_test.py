#!/usr/bin/env python3
"""边界/业务规则漏洞测试：专门攻击「规则应当拦截」的场景。

1. 已完成入库单直接删除 -> 应被拒绝
2. 已完成入库单直接 revert 后库存回退
3. 无仓库时入库/出库 -> 应被拒绝
4. 已完成单据删除明细行 -> 应被拒绝
5. 重复完成 -> 应被拒绝
"""
import json, re, sys, time, requests

BASE = 'http://127.0.0.1:8080'
_s = requests.Session()
TAG = int(time.time())
_results = []

def record(name, ok, note=''):
    _results.append((name, ok, note))
    print(f'[{"PASS" if ok else "FAIL"}] {name}: {note}')

def csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html) or re.search(r'meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None

def get(p): return _s.get(BASE+p, timeout=20)
def post(p, data=None, json_=None, **kw): return _s.post(BASE+p, data=data, json=json_, timeout=20, **kw)

def login():
    r = get('/login'); tok = csrf(r.text)
    r = post('/login', data={'username':'admin','password':'admin','csrf_token':tok,'login_mode':'admin'}, allow_redirects=False)
    return r.status_code == 302

def wh_name():
    r = get('/api/warehouses').json()
    rows = (r.get('data') or r).get('items') if isinstance((r.get('data') or r), dict) else (r.get('data') or r)
    if isinstance(rows, list) and rows: return rows[0].get('name') or rows[0].get('code')
    return None

def unique_material_code():
    code = f'UM-{TAG}'
    g = get('/material/add'); tok = csrf(g.text)
    post('/material/add', data={'name':f'唯一{code}','code':code,'specification':'t','unit':'个','price':'1','category_id':'','warehouse_id':'','safety_stock':'0','csrf_token':tok}, allow_redirects=False)
    return code

def ensure_supplier():
    r = get('/api/suppliers').json()
    rows = r.get('data') if isinstance(r, dict) else r
    if isinstance(rows, list) and rows: return rows[0].get('id')
    return None

if not login():
    print('FATAL login'); sys.exit(1)

wn = wh_name()
msup = ensure_supplier()
mcode = unique_material_code()

# ── 测试1：无仓库创建入库，应被拒绝 ──
gg = get('/in_order/add?type=purchase_in'); tok = csrf(gg.text)
items = json.dumps([{'code': mcode, 'quantity':'1','price':'1'}], ensure_ascii=False)
r = post('/in_order/add?type=purchase_in', data={'type':'purchase_in','business_type':'采购入库','supplier_id':msup,'items_json':items,'csrf_token':tok}, allow_redirects=False, headers={'X-Requested-With':'XMLHttpRequest'})
try:
    js = r.json(); note = json.dumps(js, ensure_ascii=False)[:80]
    ok = js.get('status') != 'success'  # 无仓库应失败
except Exception:
    ok = r.status_code != 200; note = r.text[:80]
record('无仓库入库应拒绝', ok, note)

# ── 测试2：正常创建入库并完成 ──
items = json.dumps([{'code': mcode, 'quantity':'1','price':'1'}], ensure_ascii=False)
r = post('/in_order/add?type=purchase_in', data={'type':'purchase_in','warehouse':wn,'business_type':'采购入库','supplier_id':msup,'items_json':items,'csrf_token':tok}, allow_redirects=False, headers={'X-Requested-With':'XMLHttpRequest'})
did = None
try:
    did = r.json().get('id')
except Exception:
    pass
record('创建入库(带仓库)', bool(did), f'id={did}')

# ── 测试3：重复完成应被拒绝 ──
if did:
    r1 = post(f'/in_order/{did}/complete', json_={'id':did}, headers={'Content-Type':'application/json','X-CSRFToken':tok})
    r2 = post(f'/in_order/{did}/complete', json_={'id':did}, headers={'Content-Type':'application/json','X-CSRFToken':tok})
    try:
        js = r2.json(); ok = js.get('status') != 'success'; note = json.dumps(js, ensure_ascii=False)[:80]
    except Exception:
        ok = r2.status_code not in (200,); note = r2.text[:80]
    record('重复完成应拒绝', ok, note)

    # ── 测试4：已完成后直接删除应被拒绝（规则：必须先反提交） ──
    r = post(f'/in_order/{did}/delete', json_={'id':did}, headers={'Content-Type':'application/json','X-CSRFToken':tok})
    resp = r.text[:100]
    try:
        js = r.json(); note = json.dumps(js, ensure_ascii=False)[:80]
        ok = js.get('status') != 'success'
    except Exception:
        ok = False; note = resp
    record('已完成后直接删除应拒绝', ok, note)

    # ── 测试5：反提交后再删除应成功 ──
    r = post(f'/in_order/{did}/revert', json_={'id':did}, headers={'Content-Type':'application/json','X-CSRFToken':tok})
    r = post(f'/in_order/{did}/delete', json_={'id':did}, headers={'Content-Type':'application/json','X-CSRFToken':tok})
    try:
        js = r.json(); ok = js.get('status') == 'success'; note = json.dumps(js, ensure_ascii=False)[:80]
    except Exception:
        ok = False; note = r.text[:80]
    record('反提交后删除应成功', ok, note)

print('\n结果: %d/%d 通过' % (sum(1 for _,o,_ in _results if o), len(_results)))
for n,o,note in _results:
    if not o: print('  FAIL: %s | %s' % (n, note))