#!/usr/bin/env python3
"""Category toolbar: export, download_template, import template."""
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

for path, label in [('/category/export','导出'), ('/category/download_template','下载模板')]:
    r = _s.get(BASE+path, timeout=30)
    ct = r.headers.get('Content-Type','')
    disp = r.headers.get('Content-Disposition','')
    print(f'GET {path} [{label}]:', r.status_code, 'len', len(r.content), 'CT', ct[:40])
    if disp: print('   Content-Disposition:', disp[:80])
    if r.status_code == 200 and len(r.content) == 0:
        print('   !! EMPTY content (potential bug)')

# batch_import page
r = _s.get(BASE+'/batch_import?type=category', timeout=20)
print('GET /batch_import?type=category:', r.status_code, 'len', len(r.text))