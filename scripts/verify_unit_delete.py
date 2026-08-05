#!/usr/bin/env python3
"""Verify unit add + delete with correct JSON payload."""
import json, re, sys, time, requests
BASE='http://127.0.0.1:8080'; _s=requests.Session()
def csrf(h):
    m=re.search(r'name="csrf_token"\s+value="([^"]+)"',h) or re.search(r'meta name="csrf-token" content="([^"]+)"',h)
    return m.group(1) if m else None
def login():
    r=_s.get(BASE+'/login'); t=csrf(r.text)
    return _s.post(BASE+'/login',data={'username':'admin','password':'admin','csrf_token':t,'login_mode':'admin'},allow_redirects=False).status_code==302
if not login(): print('FATAL'); sys.exit(1)
tag=str(int(time.time())%100000)
g=_s.get(BASE+'/unit'); tok=csrf(g.text)
r=_s.post(BASE+'/unit/add',data={'name':'单位'+tag,'code':'UD'+tag,'csrf_token':tok},headers={'X-Requested-With':'XMLHttpRequest'},timeout=20)
print('add:',r.status_code,r.text[:80])
uid=None
try: uid=r.json().get('id')
except: pass
# verify list contains it
rl=_s.get(BASE+'/unit').text
print('present in page:', ('单位'+tag) in rl)
# delete with correct JSON
h={'Content-Type':'application/json','X-CSRFToken':tok,'X-Requested-With':'XMLHttpRequest'}
if uid:
    rd=_s.post(BASE+'/unit/delete',json={'ids':[uid]},headers=h,timeout=20)
    print('delete:',rd.status_code,rd.text[:100])
    rl2=_s.get(BASE+'/unit').text
    print('still present after delete:', ('单位'+tag) in rl2)