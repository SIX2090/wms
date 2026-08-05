"""系统设置模块测试：页面访问 + 备份 + 设置保存 + 初始化预览。"""
import sys, re, time
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

tok = h.csrf()
hdr = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest'}

# 页面访问
for p in ['/system_settings','/backup','/wechat_share','/approval','/user','/operation_audit',
          '/admin/console','/admin/mobile_tokens']:
    h.page(p, f'页面{p}')

# 备份创建(安全:生成备份文件)
try:
    r = h.s.post(BASE+'/backup/create', headers=hdr, timeout=120)
    ok = r.status_code<400 and 'success' in r.text
    h.rec('备份-创建', ok, f'HTTP {r.status_code} {r.text[:120]}')
    try:
        j = r.json()
        dl = j.get('download') or j.get('filename')
        if dl:
            h.export(f'/backup/download/{dl}', '备份-下载')
    except: pass
except Exception as e:
    h.rec('备份-创建', False, f'EXC {e}')

# 初始化业务数据预览
h.page('/system_settings/init_business_data/preview', '初始化数据-预览')

# 系统设置保存(POST 回读当前表单字段)
try:
    r = h.s.get(BASE+'/system_settings', timeout=25)
    # 提取所有 input select 的 name/value
    names = set(re.findall(r'name="([^"]+)"', r.text))
    data = {}
    for n in names:
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(n), r.text)
        if m: data[n] = m.group(1)
    # 排除 csrf
    data.pop('csrf_token', None)
    rr = h.s.post(BASE+'/system_settings/save', data=data, headers=hdr, timeout=25)
    ok = rr.status_code<400
    h.rec('系统设置-保存', ok, f'HTTP {rr.status_code} {rr.text[:100]}')
except Exception as e:
    h.rec('系统设置-保存', False, f'EXC {e}')

h.report('系统设置模块')