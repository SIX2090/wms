#!/usr/bin/env python3
import re, requests, sys
BASE='http://127.0.0.1:8080'; _s=requests.Session()
def csrf(h):
    m=re.search(r'name="csrf_token"\s+value="([^"]+)"',h) or re.search(r'meta name="csrf-token" content="([^"]+)"',h)
    return m.group(1) if m else None
r=_s.get(BASE+'/login'); print('GET /login',r.status_code,'len',len(r.text)); tok=csrf(r.text); print('tok',bool(tok))
for mode in ['admin','']:
    data={'username':'admin','password':'admin','csrf_token':tok}
    if mode: data['login_mode']=mode
    rr=_s.post(BASE+'/login',data=data,allow_redirects=False,timeout=20)
    print(f'POST login mode={mode!r}:',rr.status_code,'loc',rr.headers.get('Location'),'body',rr.text[:80])