#!/usr/bin/env python3
"""Targeted test: category add via CSRF-protected POST (simulating browser)."""
import json, re, sys, time, requests

BASE = 'http://127.0.0.1:8080'
_s = requests.Session()

def csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html) or re.search(r'meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None

def login():
    r = _s.get(BASE+'/login', timeout=20); tok = csrf(r.text)
    return _s.post(BASE+'/login', data={'username':'admin','password':'admin','csrf_token':tok,'login_mode':'admin'}, allow_redirects=False, timeout=20).status_code == 302

if not login():
    print('FATAL login'); sys.exit(1)

# 1. Page GET
r = _s.get(BASE+'/category', timeout=20)
print('GET /category:', r.status_code, 'len', len(r.text))
tok = csrf(r.text)
print('csrf token present:', bool(tok))

# 2. POST add - simulate browser: FormData via X-CSRFToken header
code = 'TC-'+str(int(time.time())%100000)
data = {'code': code, 'name': '测试分类'+str(int(time.time())%1000), 'parent_id': ''}
hdr = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest'}
r2 = _s.post(BASE+'/category/add', data=data, headers=hdr, allow_redirects=False, timeout=20)
print('POST /category/add (header CSRF):', r2.status_code)
try:
    print('  body:', json.dumps(r2.json(), ensure_ascii=False)[:120])
except Exception:
    print('  body(raw):', r2.text[:150])

# 3. POST add - simulate browser form POST with csrf_token field (no header)
r3 = _s.post(BASE+'/category/add', data={**data, 'csrf_token': tok}, allow_redirects=False, timeout=20)
print('POST /category/add (field CSRF):', r3.status_code)
try:
    print('  body:', json.dumps(r3.json(), ensure_ascii=False)[:120])
except Exception:
    print('  body(raw):', r3.text[:150])