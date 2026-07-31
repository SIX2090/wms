#!/usr/bin/env python3
"""
BUG-2026-07-29-001~010 综合验证脚本

覆盖：
  BUG-001  auto_migrate_database 空库保护
  BUG-002  name 字段 HTML 净化
  BUG-003  POST 校验错误返回 400
  BUG-004  CSRF 过期 30 分钟
  BUG-005  库存/价格上限
  BUG-006  打印/导出未实现路由 404
  BUG-007  URL 查询参数长度限制
  BUG-008  打印路由改密白名单
  BUG-009  NUL 字节移除
  BUG-010  登录页锁定倒计时

使用：
  python3 scripts/verify_bug_2026_07_29_all.py
"""
import os
import re
import sys
from datetime import datetime, timedelta

# 把 app/ 加入 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, 'app')
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

import app as app_module  # noqa: E402
from app import db, User  # noqa: E402
from config import config_dict  # noqa: E402

flask_app = app_module.app
results = []


def record(bug_id, ok, detail):
    results.append((bug_id, 'PASS' if ok else 'FAIL', detail))


# BUG-001 is covered by scripts/verify_empty_database_startup.py.

# 登录态 client
c = flask_app.test_client()
with c.session_transaction() as sess:
    sess['_user_id'] = '1'
    sess['_fresh'] = True


def get_csrf(client, url):
    rv = client.get(url)
    m = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', rv.data) or re.search(
        rb'value="([^"]+)"[^>]*name="csrf_token"', rv.data
    )
    return m.group(1).decode() if m else ''


# BUG-002/009
import time
xss_code = f'XSST{int(time.time())}'
xss_spec = f'S{int(time.time()) % 10000}'
csrf = get_csrf(c, '/material/add')
rv = c.post('/material/add', data={
    'csrf_token': csrf, 'code': xss_code,
    'name': "<script>alert(1)</script>x", 'spec': xss_spec, 'stock': '0', 'price': '0',
}, follow_redirects=False)
record('BUG-002/009', rv.status_code == 200,
       f'XSS 净化 POST status={rv.status_code}（期望 200）')
# 校验入库后 name 已被净化（不含尖括号、不含 NUL）
with flask_app.app_context():
    from app import Material
    mat = Material.query.filter_by(code=xss_code).first()
    if mat is None:
        record('BUG-002/009 name净化', False, f'code={xss_code} 未入库')
    elif '<' in mat.name or '>' in mat.name or '\x00' in mat.name:
        record('BUG-002/009 name净化', False, f'name 仍含危险字符: {mat.name!r}')
    else:
        record('BUG-002/009 name净化', True, f'name 净化后: {mat.name!r}')

# BUG-003
csrf = get_csrf(c, '/material/add')
rv = c.post('/material/add', data={
    'csrf_token': csrf, 'code': '', 'name': '', 'spec': '', 'stock': '', 'price': '',
}, follow_redirects=False)
record('BUG-003', rv.status_code == 400, f'空表单 POST status={rv.status_code}')

# BUG-004
val = config_dict['production'].WTF_CSRF_TIME_LIMIT
record('BUG-004', val == 1800, f'WTF_CSRF_TIME_LIMIT={val}（期望 1800）')

# BUG-005
csrf = get_csrf(c, '/material/add')
rv = c.post('/material/add', data={
    'csrf_token': csrf, 'code': 'BIGALL', 'name': 'big', 'spec': '',
    'stock': '999999999999', 'price': '0',
}, follow_redirects=False)
record('BUG-005', rv.status_code == 400, f'12 位 stock POST status={rv.status_code}（期望 400）')

# BUG-006
for url in ['/material/print_label?code=test', '/stock_query/print', '/report/print?id=1']:
    rv = c.get(url)
    record(f'BUG-006 {url[:30]}', rv.status_code == 404, f'{url} status={rv.status_code}（期望 404）')

# BUG-007
rv = c.get('/material?search=' + 'A' * 5000)
record('BUG-007', rv.status_code == 414, f'5000 字符 query status={rv.status_code}（期望 414）')

# BUG-008
with flask_app.app_context():
    admin = User.query.filter_by(username='admin').first()
    admin.must_change_password = True
    db.session.commit()
rv = c.get('/in_order/1/print')
record('BUG-008', rv.status_code == 200,
       f'must_change_password=True 时 /in_order/1/print status={rv.status_code}（期望 200）')
with flask_app.app_context():
    admin = User.query.filter_by(username='admin').first()
    admin.must_change_password = False
    db.session.commit()

# BUG-010 - 未登录 client
c2 = flask_app.test_client()
with flask_app.app_context():
    admin = User.query.filter_by(username='admin').first()
    admin.locked_until = datetime.now() + timedelta(minutes=5)
    db.session.commit()
rv = c2.get('/login')
body = rv.data.decode('utf-8', errors='ignore')
ok = 'id="lockHint" class="lock-hint" ' in body and 'data-seconds=' in body
record('BUG-010', ok, f'未登录 GET /login 含 lockHint+data-seconds = {ok}')
with flask_app.app_context():
    admin = User.query.filter_by(username='admin').first()
    admin.locked_until = None
    db.session.commit()


# 输出报告
print()
print('=' * 72)
print(' BUG-2026-07-29 综合验证报告')
print('=' * 72)
fail = 0
for bug_id, status, detail in results:
    flag = '[OK]  ' if status == 'PASS' else '[FAIL]'
    print(f'  {flag} {bug_id:32s} {detail}')
    if status != 'PASS':
        fail += 1
print('=' * 72)
print(f' 总计 {len(results)} 项，通过 {len(results) - fail}，失败 {fail}')
print('=' * 72)
sys.exit(0 if fail == 0 else 1)
