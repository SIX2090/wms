"""验证基础资料CRUD、报表打印、系统设置操作。"""
import sys, re
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

tok = h.csrf()
hdr = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest'}

print('===== 报表打印 =====')
for t in ['inventory','ledger','in_detail','out_detail']:
    try:
        r = h.s.get(BASE + f'/report/print?type={t}', timeout=30)
        h.rec(f'报表打印[{t}]', r.status_code==200, f'HTTP {r.status_code} len={len(r.text)}')
    except Exception as e:
        h.rec(f'报表打印[{t}]', False, f'EXC {e}')

print('===== 基础资料CRUD =====')
import time
ts = str(int(time.time()))[-6:]

# 分类新增
r = h.s.post(BASE+'/category/add', data={'name': f'测试分类{ts}', 'code': f'TC{ts}'}, headers=hdr, timeout=25)
h.rec('分类-新增', r.status_code<400, f'HTTP {r.status_code} {r.text[:80]}')

# 单位新增
r = h.s.post(BASE+'/unit/add', data={'name': f'测试单位{ts}', 'code': f'TU{ts}'}, headers=hdr, timeout=25)
h.rec('单位-新增', r.status_code<400, f'HTTP {r.status_code} {r.text[:80]}')

# 供应商新增
r = h.s.post(BASE+'/supplier/add', data={'name': f'测试供应商{ts}', 'code': f'TS{ts}'}, headers=hdr, timeout=25)
h.rec('供应商-新增', r.status_code<400, f'HTTP {r.status_code} {r.text[:80]}')

# 客户新增
r = h.s.post(BASE+'/customer/add', data={'name': f'测试客户{ts}', 'code': f'TCUST{ts}'}, headers=hdr, timeout=25)
h.rec('客户-新增', r.status_code<400, f'HTTP {r.status_code} {r.text[:80]}')

# 仓库新增
r = h.s.post(BASE+'/warehouse/add', data={'name': f'测试仓{ts}', 'code': f'TW{ts}'}, headers=hdr, timeout=25)
h.rec('仓库-新增', r.status_code<400, f'HTTP {r.status_code} {r.text[:80]}')

# 部门新增
r = h.s.post(BASE+'/department/add', data={'name': f'测试部门{ts}'}, headers=hdr, timeout=25)
h.rec('部门-新增', r.status_code<400, f'HTTP {r.status_code} {r.text[:80]}')

# 员工新增
r = h.s.post(BASE+'/employee/add', data={'name': f'测试员工{ts}', 'employee_no': f'E{ts}'}, headers=hdr, timeout=25)
h.rec('员工-新增', r.status_code<400, f'HTTP {r.status_code} {r.text[:80]}')

print('===== 系统设置操作 =====')
# 备份创建
r = h.s.post(BASE+'/backup/create', headers=hdr, timeout=120)
h.rec('备份-创建', r.status_code<400 and 'success' in r.text, f'HTTP {r.status_code} {r.text[:100]}')

# 用户新增
uname = f'user{ts}'
r = h.s.post(BASE+'/user/add', data={'username': uname, 'name': f'测试用户{ts}', 'password': 'Test@123456', 'role': 'warehouse'}, headers=hdr, timeout=25)
h.rec('用户-新增', r.status_code<400 and 'success' in r.text, f'HTTP {r.status_code} {r.text[:100]}')

h.report('modules_ops')