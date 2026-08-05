"""按钮/端点综合测试工具：登录后逐一验证各模块工具栏按钮与行内操作端点。"""
import requests, re, sys, json, time

BASE = 'http://127.0.0.1:8080'
PASS = 'admin'

class H:
    def __init__(self):
        self.s = requests.Session()
        self.results = []
    def login(self, user='admin'):
        r = self.s.get(BASE+'/login', timeout=15)
        m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
        d = {'username': user, 'password': PASS}
        if m: d['csrf_token'] = m.group(1)
        rr = self.s.post(BASE+'/login', data=d, allow_redirects=False, timeout=15)
        self.rec('登录', rr.status_code==302, f'HTTP {rr.status_code} loc={rr.headers.get("Location")}')
        return rr.status_code in (302, 200)
    def csrf(self):
        # 已登录后 /login 会 302；改从已认证页面取 csrf_token
        for path in ['/material', '/unit', '/purchase_order', '/']:
            try:
                r = self.s.get(BASE+path, timeout=15)
                m = re.search(r'name="csrf_token" value="([^"]+)"', r.text)
                if m: return m.group(1)
            except Exception:
                pass
        return ''
    def rec(self, label, ok, detail=''):
        self.results.append((label, bool(ok), detail))
        print(('PASS' if ok else 'FAIL'), label, '|', detail)
    def page(self, path, label):
        try:
            r = self.s.get(BASE+path, timeout=25)
            # Flask error page marker: <title>下钻</title> not typical; use 500 traceback marker
            err_page = ('Internal Server Error' in r.text or
                        (r.status_code >= 500))
            ok = r.status_code==200 and not err_page
            self.rec(label or path, ok, f'HTTP {r.status_code} len={len(r.text)}')
        except Exception as e:
            self.rec(label or path, False, f'EXC {e}')
    def export(self, path, label):
        try:
            r = self.s.get(BASE+path, timeout=30)
            ct = r.headers.get('Content-Type','')
            ok = r.status_code==200 and len(r.content)>0 and ('spreadsheet' in ct or 'octet-stream' in ct or 'excel' in ct.lower())
            self.rec(label or path, ok, f'HTTP {r.status_code} len={len(r.content)} CT={ct[:30]}')
        except Exception as e:
            self.rec(label or path, False, f'EXC {e}')
    def api(self, method, path, label, json_body=None, expect_success=True):
        try:
            tok = self.csrf()
            h = {'X-CSRFToken': tok, 'X-Requested-With': 'XMLHttpRequest'}
            if json_body is not None: h['Content-Type'] = 'application/json'
            r = self.s.request(method, BASE+path, json=json_body, headers=h, timeout=30)
            txt = r.text[:150]
            body_ok = True
            if expect_success:
                try:
                    j = r.json()
                    body_ok = j.get('status') in ('success','ok') or 'status' not in j
                except Exception:
                    body_ok = r.status_code < 400
            ok = r.status_code < 400 and not r.text.startswith('<!doctype') and body_ok
            self.rec(label or path, ok, f'HTTP {r.status_code} {txt}')
        except Exception as e:
            self.rec(label or path, False, f'EXC {e}')
    def report(self, name):
        total = len(self.results)
        passed = sum(1 for _,ok,_ in self.results if ok)
        print(f'\n==== {name}: {passed}/{total} PASS ====')
        fails = [r for r in self.results if not r[1]]
        return fails

if __name__ == '__main__':
    h = H()
    if not h.login():
        print('LOGIN FAILED'); sys.exit(1)
    # 冒烟：基础资料页
    for p in ['/material','/category','/unit','/supplier','/customer','/warehouse',
              '/department','/employee','/contract','/opening_stock','/bom']:
        h.page(p, 'page '+p)
    h.report('smoke')