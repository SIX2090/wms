"""基础资料模块按钮/CRUD 全量测试。"""
import sys, time
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

# ---------- 工具栏 GET 端点：导出 + 下载模板 + 新增页 ----------
base = ['material','category','unit','supplier','customer','warehouse',
        'department','employee','contract','opening_stock','bom']
for m in base:
    h.export(f'/{m}/export', f'导出[{m}]')
    h.export(f'/{m}/download_template', f'下载模板[{m}]')
    # 新增页（仅 GET 新增页；其余为弹窗式 POST add）
    add_map = {'material':'/material/add','bom':'/bom/add'}
    p = add_map.get(m)
    if p:
        h.page(p, f'新增页[{m}] {p}')

# 特殊：supplier 下载模板走 /supplier/download_template（前面已验证200）
h.export('/export/template/bom', 'bom导入模板[export/template]')

tok = h.csrf()
hdr = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest'}

ts = str(int(time.time())%1000000)

def form_post(path, fields, label):
    r = h.s.post(BASE+path, data=fields, headers=hdr, timeout=25)
    ok = r.status_code<400 and 'success' in r.text
    h.rec(label, ok, f'HTTP {r.status_code} {r.text[:100]}')
    try: return r.json()
    except: return {}

# 计量单位新增+删除
j = form_post('/unit/add', {'code': f'UT{ts}', 'name': f'测试单位{ts}'}, '单位-新增')
uid = j.get('id')
if uid:
    rd = h.s.post(BASE+'/unit/delete', json={'ids':[uid]},
                  headers={'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}, timeout=25)
    h.rec('单位-删除', rd.status_code<400, f'HTTP {rd.status_code} {rd.text[:80]}')

# 物料分类新增
form_post('/category/add', {'code': f'TC{ts}', 'name': f'测试分类{ts}'}, '分类-新增')
# 供应商新增
form_post('/supplier/add', {'code': f'S{ts}', 'name': f'测试供应商{ts}'}, '供应商-新增')
# 客户新增
form_post('/customer/add', {'code': f'C{ts}', 'name': f'测试客户{ts}'}, '客户-新增')
# 部门新增
form_post('/department/add', {'code': f'D{ts}', 'name': f'测试部门{ts}'}, '部门-新增')
# 员工新增（字段名待确认）
form_post('/employee/add', {'name': f'测试员工{ts}', 'code': f'E{ts}'}, '员工-新增')
# 仓库新增
form_post('/warehouse/add', {'code': f'W{ts}', 'name': f'测试仓库{ts}'}, '仓库-新增')
# 合同新增（字段 contract_no / project_name）
form_post('/contract/add', {'contract_no': f'CT{ts}', 'project_name': f'测试工程{ts}'}, '合同-新增')

h.report('基础资料模块')