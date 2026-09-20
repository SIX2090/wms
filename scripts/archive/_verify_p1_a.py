"""P1-A 验证：12 个基础资料模板均含 /batch_import?type=X 按钮"""
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

modules = [
    ('category', '/category'),
    ('material', '/material'),
    ('unit', '/unit'),
    ('supplier', '/supplier'),
    ('customer', '/customer'),
    ('warehouse', '/warehouse'),
    ('department', '/department'),
    ('employee', '/employee'),
    ('contract', '/contract'),
    ('label_template', '/label_template'),
    ('bom', '/bom'),
    ('opening_stock', '/opening_stock'),
]
print('=== P1-A 12 模板批量导入按钮验证 ===')
print(f'{"module":<18} {"path":<22} {"status":<8} {"has_btn":<8} {"PASS/FAIL"}')
print('-' * 70)
all_pass = True
for t, p in modules:
    rv = c.get(p)
    h = rv.get_data(as_text=True)
    expected = '/batch_import?type=' + t
    has_btn = expected in h
    status_ok = rv.status_code == 200
    ok = has_btn and status_ok
    if not ok:
        all_pass = False
    print(f'{t:<18} {p:<22} {rv.status_code:<8} {str(has_btn):<8} {"✅" if ok else "❌"}')
print('---')
print('Result:', 'PASS' if all_pass else 'FAIL', f'({sum(1 for t,p in modules if "/batch_import?type="+t in c.get(p).get_data(as_text=True))}/12)')
