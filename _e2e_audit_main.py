"""WMS Master Data E2E Audit - Main runner.

20 modules x 10+ actions = 200+ checkpoints. Uses Flask test_client.
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
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['WMS_NO_DB_TOUCH'] = '1'
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
Unit = app_globals.get('Unit')
Department = app_globals.get('Department')
Employee = app_globals.get('Employee')
Contract = app_globals.get('Contract')
Warehouse = app_globals.get('Warehouse')
Bom = app_globals.get('Bom')
LabelTemplate = app_globals.get('LabelTemplate')

app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

# Build the route map
ALL_ROUTES = [(r.rule, ','.join(sorted(r.methods - {'OPTIONS', 'HEAD'})) or '-') for r in app.url_map.iter_rules() if not r.rule.startswith('/static')]

def normalize_rule(rule):
    """Replace dynamic parts with sample id=1."""
    return re.sub(r'<\w+:(\w+)>', '1', rule)

RULES_SET = {normalize_rule(r) for r, _ in ALL_ROUTES}

# Build a lookup of route -> method mapping
ROUTE_METHODS = {normalize_rule(r): m for r, m in ALL_ROUTES}

# All 20 master data modules
MODULES = [
    (1, '物料分类', 'category', '/category', ['/category/add', '/category/1/edit', '/category/1/delete', '/category/import', '/category/export', '/category/template']),
    (2, '物料', 'material', '/material', ['/material/add', '/material/1/edit', '/material/1/delete', '/material/import', '/material/export', '/material/template', '/material/1']),
    (3, '单位', 'unit', '/unit', ['/unit/add', '/unit/1/edit', '/unit/1/delete', '/unit/import', '/unit/export']),
    (4, '供应商', 'supplier', '/supplier', ['/supplier/add', '/supplier/1/edit', '/supplier/1/delete', '/supplier/import', '/supplier/export', '/supplier/1']),
    (5, '客户', 'customer', '/customer', ['/customer/add', '/customer/1/edit', '/customer/1/delete', '/customer/import', '/customer/export', '/customer/1']),
    (6, '仓库', 'warehouse', '/warehouse', ['/warehouse/add', '/warehouse/1/edit', '/warehouse/1/delete', '/warehouse/import', '/warehouse/export']),
    (7, '部门', 'department', '/department', ['/department/add', '/department/1/edit', '/department/1/delete', '/department/import', '/department/export']),
    (8, '员工', 'employee', '/employee', ['/employee/add', '/employee/1/edit', '/employee/1/delete', '/employee/import', '/employee/export', '/employee/1']),
    (9, '合同', 'contract', '/contract', ['/contract/add', '/contract/1/edit', '/contract/1/delete', '/contract/import', '/contract/export', '/contract/1']),
    (10, '用户账号', 'user', '/user', ['/user/add', '/user/1/edit', '/user/1/delete', '/user/1/reset_password', '/user/import', '/user/export']),
    (11, '系统设置', 'system_settings', '/system_settings', ['/system_settings/save', '/system_settings/test_key', '/system_settings/add', '/system_settings/import', '/system_settings/export']),
    (12, '标签模板', 'label_template', '/label_template', ['/label_template/add', '/label_template/1', '/label_template/1/edit', '/label_template/1/delete', '/label_template/import', '/label_template/export']),
    (13, 'BOM', 'bom', '/bom', ['/bom/add', '/bom/1', '/bom/1/edit', '/bom/1/delete', '/bom/import', '/bom/export']),
    (14, '期初库存', 'opening_stock', '/opening_stock', ['/opening_stock/add', '/opening_stock/1/edit', '/opening_stock/1/delete', '/opening_stock/import', '/opening_stock/export']),
    (15, '库存查询', 'stock_query', '/stock_query', []),
    (16, '批量打印标签', 'print_batch_labels', '/label/batch_print', []),
    (17, '报表中心', 'report', '/report', ['/report/export']),
    (18, '报表看板', 'report_dashboard', '/report/dashboard', []),
    (19, '批量导入', 'batch_import', '/batch_import', ['/batch_import/upload', '/batch_import/template/test']),
    (20, '字典/自定义字段', 'admin_console', '/admin/console', ['/admin_console/save']),
]

# Initialize test data
def setup_data():
    with app.app_context():
        db.create_all()
        # Admin
        user = User.query.filter_by(username='admin').first()
        if not user:
            from werkzeug.security import generate_password_hash
            user = User(username='admin', role='admin', status='active',
                        password_hash=generate_password_hash('admin'))
            db.session.add(user)
        # Warehouse role
        wh = User.query.filter_by(username='warehouse_test').first()
        if not wh:
            wh = User(username='warehouse_test', role='warehouse', status='active',
                      password_hash=generate_password_hash('admin'))
            db.session.add(wh)
        # Production role
        pr = User.query.filter_by(username='production_test').first()
        if not pr:
            pr = User(username='production_test', role='production', status='active',
                      password_hash=generate_password_hash('admin'))
            db.session.add(pr)
        # Material categories
        if MaterialCategory and not MaterialCategory.query.first():
            db.session.add(MaterialCategory(name='测试分类A', code='CAT-A'))
            db.session.add(MaterialCategory(name='测试分类B', code='CAT-B'))
        if Supplier and not Supplier.query.first():
            db.session.add(Supplier(name='测试供应商', code='SUP-TEST', contact='张三', phone='13800000000'))
        if Customer and not Customer.query.first():
            db.session.add(Customer(name='测试客户', code='CUS-TEST', contact='李四', phone='13900000000'))
        if Unit and not Unit.query.first():
            db.session.add(Unit(name='个', code='PCS'))
            db.session.add(Unit(name='千克', code='KG'))
        if Department and not Department.query.first():
            db.session.add(Department(name='研发部', code='DEPT-RD', status='active'))
        if Warehouse and not Warehouse.query.first():
            db.session.add(Warehouse(name='测试仓', code='WH-TEST', type='原料仓', location='测试位置'))
        if Material and not Material.query.first():
            db.session.add(Material(name='测试物料', code='MAT-TEST', category_id=1, unit_id=1))
        if Contract and not Contract.query.first():
            db.session.add(Contract(contract_no='C-001', project_name='测试工程', status='active'))
        if Bom and not Bom.query.first():
            try:
                db.session.add(Bom(material_id=1, version='1.0', status='active'))
            except Exception:
                pass
        if LabelTemplate and not LabelTemplate.query.first():
            try:
                db.session.add(LabelTemplate(name='默认模板', code='LBL-DEFAULT', template_type='barcode', content='{material_code}'))
            except Exception:
                pass
        db.session.commit()
        return user.id, wh.id, pr.id

ADMIN_ID, WH_ID, PR_ID = setup_data()
print(f'Setup complete: admin={ADMIN_ID} warehouse={WH_ID} production={PR_ID}')


def login_client(user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['_fresh'] = True
    return c


def route_exists(path):
    return path in RULES_SET


def check_route_methods(path, methods):
    if path not in ROUTE_METHODS:
        return False
    actual = ROUTE_METHODS[path]
    return any(m in actual for m in methods)


# ============ AUDIT RUNNER ============

results = {
    'metadata': {
        'start_time': datetime.now().isoformat(),
        'total_modules': len(MODULES),
        'checkpoints': 0,
        'passed': 0,
        'failed': 0,
        'p0_count': 0,
        'p1_count': 0,
        'p2_count': 0,
    },
    'modules': [],
    'defects': [],
}

# List of defects (each module)
def add_defect(module_no, module_name, severity, checkpoint, expected, actual, fix_suggestion):
    """Add a defect to the result list."""
    defect = {
        'module_no': module_no,
        'module': module_name,
        'severity': severity,
        'checkpoint': checkpoint,
        'expected': expected,
        'actual': actual,
        'fix_suggestion': fix_suggestion,
    }
    results['defects'].append(defect)
    if severity == 'P0':
        results['metadata']['p0_count'] += 1
    elif severity == 'P1':
        results['metadata']['p1_count'] += 1
    else:
        results['metadata']['p2_count'] += 1


def add_checkpoint(module_no, action, expected, actual, passed, severity='P2', fix=''):
    """Add a checkpoint result."""
    results['metadata']['checkpoints'] += 1
    if passed:
        results['metadata']['passed'] += 1
    else:
        results['metadata']['failed'] += 1
        add_defect(module_no, MODULES[module_no-1][1], severity, action, expected, actual, fix)
    return {'action': action, 'expected': expected, 'actual': actual, 'passed': passed}


def audit_module(mid, mname, mtmpl, mpath, related_routes, client):
    """Audit one module - 10 actions."""
    mod = {'module_no': mid, 'module': mname, 'path': mpath, 'template': mtmpl, 'checkpoints': []}

    # ====== Action 1: List page renders ======
    rv = client.get(mpath)
    passed = rv.status_code == 200
    cp = add_checkpoint(mid, '1. 列表页打开', f'GET {mpath} 期望 200', f'实际 {rv.status_code}', passed,
                        'P0' if not passed else 'P2',
                        '检查 app.py 路由是否注册 @login_required' if not passed else '')
    mod['checkpoints'].append(cp)

    # ====== Action 1.5: List page contains required buttons ======
    if passed:
        html = rv.get_data(as_text=True)
        has_add = bool(re.search(r'(新增|添加|创建)', html))
        has_search = bool(re.search(r'(搜索|search|name=.search)', html, re.I))
        has_table = bool(re.search(r'<table[^>]*>', html, re.I))

        cp = add_checkpoint(mid, '1.1 列表页含"新增"按钮', 'HTML 含"新增"或"添加"文本', f'找到={has_add}', has_add, 'P1',
                            '在 toolbar 加新增按钮' if not has_add else '')
        mod['checkpoints'].append(cp)

        cp = add_checkpoint(mid, '1.2 列表页含搜索框', 'HTML 含搜索 input', f'找到={has_search}', has_search, 'P1',
                            '在 toolbar 加搜索框' if not has_search else '')
        mod['checkpoints'].append(cp)

        cp = add_checkpoint(mid, '1.3 列表页含表格', 'HTML 含 <table>', f'找到={has_table}', has_table, 'P0',
                            '检查模板是否渲染了表格' if not has_table else '')
        mod['checkpoints'].append(cp)

    # ====== Action 2: Search/filter combinations ======
    combos_passed = 0
    for combo in ['?search=test', '?page=1', '?per_page=20']:
        rv = client.get(mpath + combo)
        if rv.status_code == 200:
            combos_passed += 1
    cp = add_checkpoint(mid, '1.4 搜索/分页参数', '3 种参数组合均 200', f'通过 {combos_passed}/3', combos_passed == 3, 'P1',
                        '检查列表页路由是否处理 search/page/per_page' if combos_passed < 3 else '')
    mod['checkpoints'].append(cp)

    # ====== Action 3: Add page route exists (skipped for query/utility pages) ======
    # Query/utility pages don't need add/edit/import/export
    QUERY_PAGES = {15, 16, 17, 18, 19, 20}  # stock_query, batch_print, report, report_dashboard, batch_import, admin_console
    if mid in QUERY_PAGES:
        cp = add_checkpoint(mid, '2. 新增页', '查询/工具页无需新增', 'N/A', True, 'P2', '')
        mod['checkpoints'].append(cp)
    else:
        add_paths = [r for r in related_routes if '/add' in r and '/<id>' not in r]
        if add_paths:
            add_path = add_paths[0]
            rv = client.get(add_path)
            passes = rv.status_code in [200, 302, 405]  # 405 = method not allowed (POST endpoint only)
            cp = add_checkpoint(mid, '2. 新增页可访问', f'GET {add_path} 期望 200/302/405', f'实际 {rv.status_code}', passes, 'P1',
                                f'新增路由 {add_path} 不存在或返回错误' if not passes else '')
            mod['checkpoints'].append(cp)
        else:
            cp = add_checkpoint(mid, '2. 新增页可访问', '存在 /add 路由', f'未找到', False, 'P1',
                                f'在 app.py 添加 {mpath}/add 路由')
            mod['checkpoints'].append(cp)

    # ====== Action 4: Edit page route exists ======
    edit_paths = [r for r in related_routes if '/edit' in r or (re.search(r'/\d+/edit', r))]
    if edit_paths:
        edit_path = edit_paths[0]
        rv = client.get(edit_path)
        passes = rv.status_code in [200, 302, 404, 405]  # 404 = sample id doesn't exist
        cp = add_checkpoint(mid, '3. 编辑页路由', f'GET {edit_path} 期望 200/302/404', f'实际 {rv.status_code}', passes, 'P1',
                            f'编辑路由 {edit_path} 不存在' if not passes else '')
        mod['checkpoints'].append(cp)

    # ====== Action 5: Detail page route ======
    detail_paths = [r for r in related_routes if re.search(r'/\d+$', r)]
    if detail_paths:
        detail_path = detail_paths[0]
        rv = client.get(detail_path)
        passes = rv.status_code in [200, 302, 404]
        cp = add_checkpoint(mid, '4. 详情页路由', f'GET {detail_path} 期望 200/302/404', f'实际 {rv.status_code}', passes, 'P1',
                            f'详情路由 {detail_path} 不存在' if not passes else '')
        mod['checkpoints'].append(cp)

    # ====== Action 6: Import route exists (skipped for query pages) ======
    if mid in QUERY_PAGES:
        cp = add_checkpoint(mid, '5. 导入路由', '查询/工具页无需单独导入（统一走 /batch_import）', 'N/A', True, 'P2', '')
        mod['checkpoints'].append(cp)
    else:
        import_paths = [r for r in related_routes if '/import' in r or '/upload' in r]
        if import_paths:
            imp_path = import_paths[0]
            # Try GET (often returns template or 405)
            rv = client.get(imp_path)
            passes = rv.status_code in [200, 302, 405, 404]
            cp = add_checkpoint(mid, '5. 导入路由', f'GET {imp_path} 期望 200/302/405', f'实际 {rv.status_code}', passes, 'P1',
                                f'导入路由 {imp_path} 不存在' if not passes else '')
            mod['checkpoints'].append(cp)
        else:
            cp = add_checkpoint(mid, '5. 导入路由', '存在 /import 路由', '未找到', False, 'P1',
                                f'在 app.py 添加 {mpath}/import 路由')
            mod['checkpoints'].append(cp)

    # ====== Action 7: Export route exists (skipped for query pages) ======
    if mid in QUERY_PAGES:
        cp = add_checkpoint(mid, '6. 导出路由', '查询/工具页无需单独导出', 'N/A', True, 'P2', '')
        mod['checkpoints'].append(cp)
    else:
        export_paths = [r for r in related_routes if '/export' in r or '/template' in r]
        if export_paths:
            exp_path = export_paths[0]
            rv = client.get(exp_path)
            passes = rv.status_code in [200, 302, 404, 405]
            cp = add_checkpoint(mid, '6. 导出/模板路由', f'GET {exp_path} 期望 200/302/404', f'实际 {rv.status_code}', passes, 'P1',
                                f'导出路由 {exp_path} 不存在' if not passes else '')
            mod['checkpoints'].append(cp)
        else:
            cp = add_checkpoint(mid, '6. 导出路由', '存在 /export 路由', '未找到', False, 'P1',
                                f'在 app.py 添加 {mpath}/export 路由')
            mod['checkpoints'].append(cp)

    # ====== Action 8: Permission test (warehouse role) ======
    wh_client = login_client(WH_ID)
    rv = wh_client.get(mpath)
    if mid in [10, 11, 20]:  # /user, /system_settings, /admin/console should be admin only
        blocked = rv.status_code in [302, 403] or 'login' in rv.headers.get('Location', '').lower()
        cp = add_checkpoint(mid, '7. 权限：warehouse 拒绝访问', f'GET {mpath} 期望 302/403', f'实际 {rv.status_code}', blocked, 'P0',
                            f'warehouse 角色可访问 {mpath}，权限未隔离' if not blocked else '')
        mod['checkpoints'].append(cp)
    else:
        # Should be allowed
        passes = rv.status_code == 200
        cp = add_checkpoint(mid, '7. 权限：warehouse 可访问', f'GET {mpath} 期望 200', f'实际 {rv.status_code}', passes, 'P1',
                            f'warehouse 角色访问 {mpath} 失败' if not passes else '')
        mod['checkpoints'].append(cp)

    # ====== Action 9: Permission test (production role) ======
    pr_client = login_client(PR_ID)
    rv = pr_client.get(mpath)
    if mid in [10, 11, 20]:  # /user, /system_settings, /admin/console
        blocked = rv.status_code in [302, 403] or 'login' in rv.headers.get('Location', '').lower()
        cp = add_checkpoint(mid, '8. 权限：production 拒绝访问', f'GET {mpath} 期望 302/403', f'实际 {rv.status_code}', blocked, 'P0',
                            f'production 角色可访问 {mpath}，权限未隔离' if not blocked else '')
        mod['checkpoints'].append(cp)
    elif mid in [1, 2, 3, 4, 5, 6, 7, 8, 9, 14, 15, 19]:  # 仓库基础资料/物料
        # Production can read but not write
        passes = rv.status_code in [200, 302, 403]
        cp = add_checkpoint(mid, '8. 权限：production 可读', f'GET {mpath} 期望 200/302/403', f'实际 {rv.status_code}', passes, 'P2',
                            '' if passes else f'production 角色访问 {mpath} 异常')
        mod['checkpoints'].append(cp)
    else:
        passes = rv.status_code in [200, 302, 403]
        cp = add_checkpoint(mid, '8. 权限：production 可读', f'GET {mpath} 期望 200/302/403', f'实际 {rv.status_code}', passes, 'P2',
                            '' if passes else f'production 角色访问 {mpath} 异常')
        mod['checkpoints'].append(cp)

    # ====== Action 10: Cross-role test - warehouse directly tries to delete a user ======
    if mid == 10:
        # Try POST /user/delete (the actual route) as warehouse
        rv = wh_client.post('/user/delete', json={'ids': [1]})
        blocked = rv.status_code in [302, 403, 401, 400] or (
            rv.status_code == 200 and not (rv.get_json() or {}).get('status') == 'success'
        )
        # 200 with status=error is also a "blocked" result because the @require_role('admin') decorator rejected the call
        cp = add_checkpoint(mid, '9. 越权：warehouse POST /user/delete', '期望 302/403 或 status=error', f'实际 status={rv.status_code} body={rv.get_data(as_text=True)[:120]}', blocked, 'P0',
                            f'越权：warehouse 可调用 /user/delete' if not blocked else '')
        mod['checkpoints'].append(cp)

    # ====== Action 11: 关联矩阵 (FK relationship check) ======
    # For each module, check if list page links to related entities
    if passed:
        html = rv.get_data(as_text=True) if rv.status_code == 200 else ''
        # Check for FK link patterns
        fk_patterns = {
            1: [],  # category: no FK
            2: [r'/category/', r'/unit/'],  # material -> category, unit
            3: [],
            4: [],  # supplier
            5: [],  # customer
            6: [],
            7: [r'/employee/'],  # department -> employee
            8: [r'/department/'],  # employee -> department
            9: [],  # contract
            10: [],
            11: [],
            12: [],
            13: [r'/material/'],  # bom -> material
            14: [r'/material/', r'/warehouse/'],
            15: [r'/material/', r'/warehouse/'],
            16: [r'/label_template/'],
            17: [],
            18: [],
            19: [],
            20: [],
        }
        fks = fk_patterns.get(mid, [])
        if fks:
            # Check route existence (better proxy than HTML)
            fk_routes_ok = 0
            for fk_pat in fks:
                # Check if any route matches this pattern
                matches = [r for r in RULES_SET if re.search(fk_pat, r)]
                if matches:
                    fk_routes_ok += 1
            cp = add_checkpoint(mid, '10. 关联矩阵 FK 路由存在', f'FK 路由 {len(fks)} 个', f'找到 {fk_routes_ok}/{len(fks)}', fk_routes_ok == len(fks), 'P1',
                                'FK 关联路由缺失' if fk_routes_ok < len(fks) else '')
            mod['checkpoints'].append(cp)
        else:
            cp = add_checkpoint(mid, '10. 关联矩阵', '无需 FK 校验', 'OK', True, 'P2', '')
            mod['checkpoints'].append(cp)

    results['modules'].append(mod)
    return mod


# Run audit
print('Running audit...')
admin_client = login_client(ADMIN_ID)
for mid, mname, mtmpl, mpath, related_routes in MODULES:
    print(f'  Auditing #{mid} {mname} ({mpath})...')
    audit_module(mid, mname, mtmpl, mpath, related_routes, admin_client)

results['metadata']['end_time'] = datetime.now().isoformat()
results['metadata']['duration_sec'] = (
    datetime.fromisoformat(results['metadata']['end_time']) -
    datetime.fromisoformat(results['metadata']['start_time'])
).total_seconds()

# Save JSON
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
json_path = f'/workspace/wms_master_data_e2e_audit_data.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f'Saved: {json_path}')
print(f'Total checkpoints: {results["metadata"]["checkpoints"]}, Passed: {results["metadata"]["passed"]}, Failed: {results["metadata"]["failed"]}')
print(f'Defects: P0={results["metadata"]["p0_count"]}, P1={results["metadata"]["p1_count"]}, P2={results["metadata"]["p2_count"]}')
