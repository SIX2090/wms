"""全量爬取所有页面路由，检测 500/404/渲染错误。真实 HTTP 请求 + 登录会话。"""
import re
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import requests

BASE = "http://127.0.0.1:8080"
S = requests.Session()

# 需要替换的 <int:id> 等动态段
def fill_route(r):
    r = re.sub(r"<int:\w+>", "1", r)
    r = re.sub(r"<path:\w+>", "x", r)
    r = re.sub(r"<(\w+)>", "1", r)
    return r

def main():
    from app import app  # 本地导入拿路由表
    routes = sorted({str(r) for r in app.url_map.iter_rules()
                     if '<' not in str(r) or 'int:' in str(r)})
    # 只测 GET 页面路由（排除 api/static/动作类）
    skip_sub = ('/api/', '/static/', '/debug/', '/export/', '/import/',
                '/download_template', '/print', '/batch_', '/save', '/delete',
                '/complete', '/revert', '/update', '/add', '/item',
                '/approve', '/reject', '/confirm', '/cancel', '/copy',
                '/create_', '/selectable', '/selection', '/generate')
    targets = []
    for r in routes:
        if re.search(r'<(?!int:)\w+>', r):
            continue
        if any(r == sk or r.startswith(sk) for sk in skip_sub):
            continue
        if r in ('/', '/login', '/logout'):
            continue
        targets.append(r)
    targets = sorted(set(targets))

    # 登录
    g = S.get(BASE + "/login", timeout=10)
    tok = re.search(r'name="csrf_token" value="([^"]+)"', g.text)
    csrf = tok.group(1) if tok else ""
    # 管理员登录
    S.post(BASE + "/login", data={
        "username": "admin", "password": "admin",
        "csrf_token": csrf, "login_type": "admin",
    }, allow_redirects=True, timeout=10, headers={"X-Requested-With": "XMLHttpRequest"})

    results = []
    for r in targets:
        url = BASE + fill_route(r)
        try:
            resp = S.get(url, timeout=20, allow_redirects=True)
            code = resp.status_code
            title = re.search(r'<title>(.*?)</title>', resp.text, re.S)
            title = (title.group(1).strip() if title else "")[:30]
            tag = "OK" if code == 200 else ("ERR" if code in (500, 502, 503, 404) else "WARN")
            results.append((tag, code, r, title))
        except Exception as e:
            results.append(("EXC", 0, r, str(e)[:40]))

    errs = [x for x in results if x[0] in ("ERR", "EXC")]
    warns = [x for x in results if x[0] == "WARN"]
    print(f"=== 共 {len(results)} 个页面路由，OK {len(results)-len(errs)-len(warns)}，异常 {len(errs)}，非200 {len(warns)} ===")
    for tag, code, r, title in sorted(results, key=lambda x: (x[0] != "OK", x[1])):
        if tag != "OK":
            print(f"[{tag}] {code} {r}  <title>{title}</title>")
    print("\n--- 全部结果 ---")
    for tag, code, r, title in sorted(results):
        print(f"[{tag}] {code} {r}")

if __name__ == "__main__":
    main()