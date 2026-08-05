"""用户管理测试:新增/编辑/删除测试用户 + 审批中心 + 操作审计。"""
import sys, time
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login('admin'):
    print('LOGIN FAILED'); sys.exit(1)
tok = h.csrf()
hdr = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json'}

ts = str(int(time.time())%1000000)
uname = f'testuser{ts}'

# 用户新增
try:
    r = h.s.post(BASE+'/user/add', json={'username': uname, 'name': f'测试用户{ts}', 'password': 'Test@123456', 'role': 'warehouse'}, headers=hdr, timeout=25)
    ok = r.status_code<400 and 'success' in r.text
    h.rec('用户-新增', ok, f'HTTP {r.status_code} {r.text[:120]}')
    try: uid = r.json().get('id')
    except: uid = None
except Exception as e:
    h.rec('用户-新增', False, f'EXC {e}'); uid=None

# 用户编辑
if uid:
    try:
        r = h.s.post(BASE+f'/user/{uid}/edit', json={'name': f'测试用户{ts}改'}, headers=hdr, timeout=25)
        h.rec('用户-编辑', r.status_code<400, f'HTTP {r.status_code} {r.text[:100]}')
    except Exception as e:
        h.rec('用户-编辑', False, f'EXC {e}')
    # 用户删除
    try:
        r = h.s.post(BASE+'/user/delete', json={'ids':[uid]}, headers=hdr, timeout=25)
        h.rec('用户-删除', r.status_code<400, f'HTTP {r.status_code} {r.text[:100]}')
    except Exception as e:
        h.rec('用户-删除', False, f'EXC {e}')

# 审批中心页面 & 操作审计 & 审计导出
h.page('/approval', '审批中心')
h.page('/operation_audit', '操作审计')
h.export('/operation_audit/export', '操作审计-导出')

h.report('用户管理系统')