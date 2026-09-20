"""Render key master data pages to HTML for audit evidence."""
import os
import sys
os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
os.environ['WMS_TEST_DB'] = 'sqlite:///:memory:'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'  # skip auto_migrate
os.environ['WMS_NO_DB_TOUCH'] = '1'  # skip database migrations
sys.path.insert(0, '/workspace/app')

import runpy
ag = runpy.run_path('/workspace/app/app.py')
from flask import Flask
app = next(v for v in ag.values() if isinstance(v, Flask))
db = ag['db']
User = ag['User']
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

with app.app_context():
    db.create_all()
    from werkzeug.security import generate_password_hash
    if not User.query.first():
        db.session.add(User(username='admin', role='admin', status='active', password_hash=generate_password_hash('admin')))
        db.session.commit()

OUT = '/workspace/audit_screenshots'
os.makedirs(OUT, exist_ok=True)

with app.test_client() as c:
    # Login flow - first get login page (no session)
    c2 = app.test_client()  # fresh client, no session
    rv = c2.get('/login')
    open(f'{OUT}/01_login.html', 'w', encoding='utf-8').write(rv.get_data(as_text=True)[:200000])
    print(f'01_login.html: {rv.status_code}, {len(rv.get_data(as_text=True))} bytes')

    # Submit login form
    with c2.session_transaction() as sess:
        sess['_user_id'] = str(1)
        sess['_fresh'] = True

    # Key master data pages
    for name, path in [
        ('03_home', '/'),
        ('04_material_list', '/material'),
        ('05_category_list', '/category'),
        ('06_supplier_list', '/supplier'),
        ('07_unit_list', '/unit'),
        ('08_warehouse_list', '/warehouse'),
        ('09_employee_list', '/employee'),
        ('10_department_list', '/department'),
        ('11_customer_list', '/customer'),
        ('12_contract_list', '/contract'),
        ('13_user_list', '/user'),
        ('14_system_settings', '/system_settings'),
        ('15_label_template_list', '/label_template'),
        ('16_bom_list', '/bom'),
        ('17_opening_stock_list', '/opening_stock'),
        ('18_stock_query', '/stock_query'),
        ('19_batch_print', '/label/batch_print'),
        ('20_report', '/report'),
        ('21_report_dashboard', '/report/dashboard'),
        ('22_batch_import', '/batch_import'),
        ('23_admin_console', '/admin/console'),
        ('24_form_error_category_add', '/category/add'),
    ]:
        rv = c2.get(path)
        body = rv.get_data(as_text=True)
        # Save first 200KB
        open(f'{OUT}/{name}.html', 'w', encoding='utf-8').write(body[:200000])
        print(f'{name}: {rv.status_code}, {len(body)} bytes')

print('Done!')
