#!/usr/bin/env python3
"""全量路由端点扫描：带合法 admin 会话+CSRF 真实调用每个路由，捕捉 500(真bug) / 404(断裂)。

- GET 路由：期望 200；500 视为页面渲染崩溃bug；404 记录
- POST 路由：期望不抛 500；500 视为真实服务端 bug
- 统计并按严重度输出。
"""
import json, re, sys, time, requests

BASE = 'http://127.0.0.1:8080'
_s = requests.Session()
routes = json.load(open('/workspace/scripts/_routes.json', encoding='utf-8'))

def csrf(html):
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html) or re.search(r'meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else None

def fill(p):
    p = re.sub(r'<int:(\w+)>', '1', p)
    p = re.sub(r'<path:(\w+)>', 'x', p)
    p = re.sub(r'<float:(\w+)>', '1', p)
    p = re.sub(r'<(\w+)>', '1', p)
    return p

# 登录
r = _s.get(BASE + '/login', timeout=20); tok = csrf(r.text)
lr = _s.post(BASE + '/login', data={'username':'admin','password':'admin','csrf_token':tok,'login_mode':'admin'}, allow_redirects=False, timeout=20)
if lr.status_code != 302:
    print('FATAL 登录失败'); sys.exit(1)
print('登录成功')

g_500, g_404, p_500 = [], [], []
g_ok = p_ok = 0

for rte in routes:
    path, methods = rte['path'], rte['methods']
    url = fill(path)
    try:
        if 'GET' in methods:
            resp = _s.get(BASE + url, timeout=25, allow_redirects=False)
            if resp.status_code == 500:
                g_500.append((path, resp.text[:120]))
            elif resp.status_code == 404:
                g_404.append(path)
            else:
                g_ok += 1
        elif 'POST' in methods:
            hdr = {'X-Requested-With':'XMLHttpRequest','X-CSRFToken': tok, 'Content-Type':'application/json'}
            resp = _s.post(BASE + url, json={}, headers=hdr, timeout=25, allow_redirects=False)
            if resp.status_code == 500:
                p_500.append((path, resp.text[:120]))
            elif resp.status_code == 404:
                g_404.append(path)
            else:
                p_ok += 1
    except Exception as e:
        p_500.append((path, f'EXC:{str(e)[:60]}'))

print('\n===== 汇总 =====')
print(f'GET 非500/404: {g_ok}, POST 非500/404: {p_ok}')
print(f'\n[严重] GET 500 数量: {len(g_500)}')
for p, t in g_500:
    print(f'  GET-500 {p} :: {t}')
print(f'\n[严重] POST 500 数量: {len(p_500)}')
for p, t in p_500:
    print(f'  POST-500 {p} :: {t}')
print(f'\n[提示] 404 数量: {len(g_404)}')
for p in g_404:
    print(f'  404 {p}')