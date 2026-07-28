"""P1-B 验证：user/system_settings/label_template/opening_stock import/export/add 路由存在"""
import os, sys
os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
os.environ['WMS_TEST_DB'] = 'sqlite:///:memory:'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['WMS_NO_DB_TOUCH'] = '1'
sys.path.insert(0, '/workspace/app')

import runpy
from flask import Flask
g = runpy.run_path('/workspace/app/app.py')
app = next(v for v in g.values() if isinstance(v, Flask))
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True
db = g['db']
User = g['User']

with app.app_context():
    db.create_all()
    from werkzeug.security import generate_password_hash
    u = User.query.filter_by(username='admin').first()
    if not u:
        u = User(username='admin', role='admin', status='active', password_hash=generate_password_hash('admin'))
        db.session.add(u)
        db.session.commit()
    admin_id = u.id

c = app.test_client()
with c.session_transaction() as s:
    s['_user_id'] = str(admin_id); s['_fresh'] = True

print('=== P1-B stub 路由验证 ===')
get_routes = [
    ('/user/export', [200, 302]),
    ('/system_settings/add', [200, 302]),
    ('/system_settings/export', [200, 302]),
    ('/label_template/export', [200, 302]),
    ('/opening_stock/export', [200, 302]),
]
post_routes = [
    ('/user/import', [200, 302, 405]),
    ('/system_settings/import', [200, 302, 405]),
    ('/label_template/import', [200, 302, 405]),
    ('/opening_stock/import', [200, 302, 405]),
]
all_pass = True
print(f'{"method":<6} {"route":<32} {"status":<8} {"PASS/FAIL"}')
print('-' * 60)
for r, ok_codes in get_routes:
    rv = c.get(r)
    ok = rv.status_code in ok_codes
    if not ok:
        all_pass = False
    print(f'{"GET":<6} {r:<32} {rv.status_code:<8} {"✅" if ok else "❌"}')
for r, ok_codes in post_routes:
    rv = c.post(r, data={})
    ok = rv.status_code in ok_codes
    if not ok:
        all_pass = False
    print(f'{"POST":<6} {r:<32} {rv.status_code:<8} {"✅" if ok else "❌"}')
print('---')
print('Result:', 'PASS' if all_pass else 'FAIL')
