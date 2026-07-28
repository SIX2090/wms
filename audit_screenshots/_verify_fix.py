import urllib.request, urllib.parse, http.cookiejar, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8080'
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
b = op.open(BASE + '/login', timeout=10).read().decode('utf-8', 'ignore')
csrf = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', b).group(1)
op.open(BASE + '/login', data=urllib.parse.urlencode({
    'username': 'admin', 'password': 'AAAA1234', 'usage_consent': '1',
    'login_mode': 'admin', 'csrf_token': csrf
}).encode())

for p in ['/ai/replenishment_live', '/ai/inventory_health_live']:
    try:
        r = op.open(BASE + p, timeout=15)
        body = r.read().decode('utf-8', 'ignore')
        print(f'{p} -> {r.status} len={len(body)}')
        if r.status == 200:
            has_err = 'UndefinedError' in body or 'is undefined' in body
            has_data = '物料' in body or 'AI' in body
            print(f'  {"BUG: 仍有模板错误" if has_err else "OK: 正常渲染"} | 含业务内容: {has_data}')
        else:
            print(f'  FAIL: 非200状态码')
    except Exception as e:
        print(f'{p} -> ERROR: {e}')
