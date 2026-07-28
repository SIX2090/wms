"""P0-1 单独验证：/label/batch_print?ids= 必须返回 200 + 占位提示"""
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

rv = c.get('/label/batch_print?ids=')
print('=== P0-1 验证 ===')
print('status:', rv.status_code)
html = rv.get_data(as_text=True)
print('has_placeholder:', '未选择物料' in html)
print('has_link_to_material:', '/material' in html)
print('has_table:', '<table' in html.lower())
print('has_search_input:', 'name="ids"' in html)
print('has_close_button:', 'window.close()' in html)
print('---')
print('Result:', 'PASS' if (rv.status_code == 200 and '未选择物料' in html and '<table' in html.lower()) else 'FAIL')
