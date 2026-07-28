"""WMS Master Data E2E Audit - 20 modules x 10 actions = 200+ checkpoints.

Static + dynamic verification using Flask test_client (no real browser needed).
Outputs structured results to /workspace/wms_master_data_e2e_audit_<TS>.md
and /workspace/wms_master_data_e2e_audit_data.json
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
os.environ['WMS_TEST_DB'] = 'sqlite:///:memory:'
sys.path.insert(0, '/workspace/app')

import runpy
app_globals = runpy.run_path('/workspace/app/app.py')
from flask import Flask
app = next(v for v in app_globals.values() if isinstance(v, Flask))
db = app_globals['db']
User = app_globals['User']
Supplier = app_globals['Supplier']
Material = app_globals.get('Material')
MaterialCategory = app_globals.get('MaterialCategory')
Customer = app_globals.get('Customer')
OperationLog = app_globals.get('OperationLog')
SystemSetting = app_globals.get('SystemSetting')

app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

# All 20 master data modules to audit
MODULES = [
    # (#, name, list_path, list_template, related_routes...)
    (1, '物料分类', 'category', '/category', ['/category/add', '/category/<id>/edit', '/category/<id>/delete', '/category/import', '/category/export', '/category/template']),
    (2, '物料', 'material', '/material', ['/material/add', '/material/<id>/edit', '/material/<id>/delete', '/material/import', '/material/export', '/material/template', '/material/<id>']),
    (3, '单位', 'unit', '/unit', ['/unit/add', '/unit/<id>/edit', '/unit/<id>/delete', '/unit/import', '/unit/export']),
    (4, '供应商', 'supplier', '/supplier', ['/supplier/add', '/supplier/<id>/edit', '/supplier/<id>/delete', '/supplier/import', '/supplier/export', '/supplier/<id>']),
    (5, '客户', 'customer', '/customer', ['/customer/add', '/customer/<id>/edit', '/customer/<id>/delete', '/customer/import', '/customer/export', '/customer/<id>']),
    (6, '仓库', 'warehouse', '/warehouse', ['/warehouse/add', '/warehouse/<id>/edit', '/warehouse/<id>/delete', '/warehouse/import', '/warehouse/export']),
    (7, '部门', 'department', '/department', ['/department/add', '/department/<id>/edit', '/department/<id>/delete', '/department/import', '/department/export']),
    (8, '员工', 'employee', '/employee', ['/employee/add', '/employee/<id>/edit', '/employee/<id>/delete', '/employee/import', '/employee/export', '/employee/<id>']),
    (9, '合同', 'contract', '/contract', ['/contract/add', '/contract/<id>/edit', '/contract/<id>/delete', '/contract/import', '/contract/export', '/contract/<id>']),
    (10, '用户账号', 'user', '/user', ['/user/add', '/user/<id>/edit', '/user/<id>/delete', '/user/<id>/reset_password']),
    (11, '系统设置', 'system_settings', '/system_settings', ['/system_settings/save', '/system_settings/<key>']),
    (12, '标签模板', 'label_template', '/label_template', ['/label_template/add', '/label_template/<id>', '/label_template/<id>/edit', '/label_template/<id>/delete']),
    (13, 'BOM', 'bom', '/bom', ['/bom/add', '/bom/<id>', '/bom/<id>/edit', '/bom/<id>/delete']),
    (14, '期初库存', 'opening_stock', '/opening_stock', ['/opening_stock/add', '/opening_stock/<id>/edit', '/opening_stock/<id>/delete']),
    (15, '库存查询', 'stock_query', '/stock_query', []),
    (16, '批量打印标签', 'print_batch_labels', '/print_batch_labels', []),
    (17, '报表中心', 'report', '/report', ['/report/export']),
    (18, '报表看板', 'report_dashboard', '/report_dashboard', []),
    (19, '批量导入', 'batch_import', '/batch_import', ['/batch_import/upload', '/batch_import/template/<type>']),
    (20, '字典/自定义字段', 'system_settings', '/admin/console', ['/admin/console/save']),
]

# Patterns to look for in HTML
TOOLBAR_PATTERNS = {
    'add_button': [r'>\s*新增', r'添加', r'>\s*创建', r'btn.*add', r'btn.*new'],
    'import_button': [r'导入', r'import', r'btn-import'],
    'export_button': [r'导出', r'export', r'btn-export'],
    'template_download': [r'模板', r'template', r'下载模板'],
    'search': [r'搜索', r'search', r'input.*search', r'name=.?search'],
    'pagination': [r'每页', r'上一页', r'下一页', r'pager', r'pagination'],
    'batch_delete': [r'批量删除', r'batch.*delete', r'delete.*selected'],
    'row_actions': [r'<td>[^<]*<a', r'<td>[^<]*<button', r'btn.*sm'],
}

# Build the route map for resolving dynamic paths
def resolve_route(app, rule_pattern, sample_id=1):
    """Replace <int:id> with sample id, <id> with sample id."""
    rule = re.sub(r'<\w+:(\w+)>', str(sample_id), rule_pattern)
    return rule

def normalize_rule(rule):
    return re.sub(r'<\w+:(\w+)>', '1', rule)

def get_all_routes():
    return [(r.rule, ','.join(sorted(r.methods - {'OPTIONS', 'HEAD'})) or '-') for r in app.url_map.iter_rules() if not r.rule.startswith('/static')]

# Test
print('Loading routes...')
all_routes = get_all_routes()
rules_set = {normalize_rule(r) for r, _ in all_routes}
print(f'Total rules: {len(rules_set)}')

def is_route_exists(rule):
    return normalize_rule(rule) in rules_set

# Build dynamic URL with sample id
def make_url(rule, sample_id=1):
    return re.sub(r'<\w+:(\w+)>', str(sample_id), rule)

# Setup test data
def setup_data():
    with app.app_context():
        db.create_all()
        # Ensure admin
        user = User.query.filter_by(username='admin').first()
        if not user:
            from werkzeug.security import generate_password_hash
            user = User(username='admin', role='admin', status='active',
                        password_hash=generate_password_hash('admin'))
            db.session.add(user)
        # Ensure warehouse role
        wh = User.query.filter_by(username='warehouse_test').first()
        if not wh:
            wh = User(username='warehouse_test', role='warehouse', status='active',
                      password_hash=generate_password_hash('admin'))
            db.session.add(wh)
        # Ensure production role
        pr = User.query.filter_by(username='production_test').first()
        if not pr:
            pr = User(username='production_test', role='production', status='active',
                      password_hash=generate_password_hash('admin'))
            db.session.add(pr)
        # Ensure some test data
        if MaterialCategory and not MaterialCategory.query.first():
            db.session.add(MaterialCategory(name='测试分类A', code='CAT-A'))
            db.session.add(MaterialCategory(name='测试分类B', code='CAT-B'))
        if Supplier and not Supplier.query.first():
            db.session.add(Supplier(name='测试供应商', code='SUP-TEST', contact='张三', phone='13800000000'))
        if Customer and not Customer.query.first():
            db.session.add(Customer(name='测试客户', code='CUS-TEST', contact='李四', phone='13900000000'))
        db.session.commit()
        return user.id, wh.id, pr.id

admin_id, wh_id, pr_id = setup_data()
print(f'Admin ID: {admin_id}, Warehouse ID: {wh_id}, Production ID: {pr_id}')

def login_as(user_id):
    """Returns a test client logged in as the given user_id."""
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c

# Quick smoke test
with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True
    rv = c.get('/login')
    print(f'/login status: {rv.status_code}')
    rv = c.get('/')
    print(f'Home status: {rv.status_code}')

# Save globals for next step
import pickle
state = {
    'app_globals_keys': list(app_globals.keys()),
    'admin_id': admin_id,
    'wh_id': wh_id,
    'pr_id': pr_id,
    'rules_set': list(rules_set),
    'all_routes': [(r, m) for r, m in all_routes],
    'modules': [(m, n, t, p, [r for r in routes]) for m, n, t, p, routes in MODULES],
}
with open('/workspace/_audit_state.pkl', 'wb') as f:
    pickle.dump(state, f)
print('State saved')
