"""阶段 6.3: warehouse 角色无法访问 /admin/console"""
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
    for uname, role in [('admin','admin'), ('wh_test','warehouse'), ('pr_test','production')]:
        u = User.query.filter_by(username=uname).first()
        if not u:
            u = User(username=uname, role=role, status='active', password_hash=generate_password_hash('admin'))
            db.session.add(u)
            db.session.commit()
    wh_id = User.query.filter_by(username='wh_test').first().id
    pr_id = User.query.filter_by(username='pr_test').first().id

print('=== 6.3 权限矩阵 ===')
for uname, uid, target in [('warehouse', wh_id, '/admin/console'),
                            ('production', pr_id, '/admin/console'),
                            ('warehouse', wh_id, '/user'),
                            ('production', pr_id, '/user'),
                            ('warehouse', wh_id, '/system_settings')]:
    c = app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = str(uid); s['_fresh'] = True
    rv = c.get(target)
    blocked = rv.status_code in [302, 403]
    print(f'{uname:<12} GET {target:<22} -> {rv.status_code:<5} {"✅ blocked" if blocked else "❌ accessible"}')
