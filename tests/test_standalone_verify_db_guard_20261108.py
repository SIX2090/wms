"""Read source and test the guard with fake globals; never import WMS or open a DB."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
BLOCKED = (
    'verify_real_db_warehouse_stock.py',
    'verify_bug_2026_08_02_005.py',
    'verify_init_business_data.py',
    'verify_full_flow_20groups.py',
)
GUARDED = (
    'verify_ledger_required_material.py', 'verify_opening_stock_multi_warehouse.py',
    'verify_ai_audit_models.py', 'verify_ai_provider_evaluation.py', 'verify_other_order_toolbar.py',
    'verify_bug_2026_07_29_all.py', 'verify_bug_2026_08_02_001.py',
    'verify_bug_2026_08_02_002.py', 'verify_bug_2026_08_02_003.py',
    'verify_bug_2026_08_02_004.py', 'verify_bug_2026_08_02_007.py',
    'verify_ai_business_quality_dashboard.py', 'verify_ai_purchase_workbench_page.py',
    'verify_ai_sales_followup_workbench.py', 'verify_ai_warehouse_workbench_page.py',
    'verify_adjustment_state_machine.py', 'verify_ai_cross_user_isolation.py',
    'verify_check_state_machine.py', 'verify_empty_database_startup.py',
    'verify_future_date_guard.py', 'verify_in_order_state_machine.py',
    'verify_out_order_state_machine.py', 'verify_transfer_state_machine.py', 'enumerate_routes.py',
)


def parsed(path):
    return ast.parse(path.read_text(encoding='utf-8-sig'))


def executable_statements(tree):
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    while body and isinstance(body[0], ast.ImportFrom) and body[0].module == '__future__':
        body.pop(0)
    return body


def isolated_guard(environment, modules=None):
    tree = parsed(SCRIPTS / 'verify_db_guard.py')
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'require_synthetic_memory_database')
    compiled = compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), '<guard>', 'exec')
    namespace = {'os': SimpleNamespace(environ=environment), 'sys': SimpleNamespace(modules=modules or {})}
    exec(compiled, namespace)
    return namespace['require_synthetic_memory_database']


@pytest.mark.parametrize('environment', [
    {}, {'DATABASE_URL': 'sqlite:///:memory:', 'WMS_DATABASE_URI': 'sqlite:///:memory:', 'FLASK_ENV': 'testing'},
])
def test_guard_selects_only_new_memory_database(environment):
    isolated_guard(environment)()
    assert environment['DATABASE_URL'] == 'sqlite:///:memory:'
    assert environment['WMS_DATABASE_URI'] == 'sqlite:///:memory:'
    assert environment['FLASK_ENV'] == 'testing'
    assert environment['WMS_SKIP_AUTO_UPDATE'] == '1'
    assert environment['WMS_SKIP_STARTUP_BACKUP'] == '1'


@pytest.mark.parametrize('environment', [
    {'DATABASE_URL': 'sqlite:///synthetic-looking.db'},
    {'DATABASE_URL': 'sqlite:///file:alias?mode=memory'},
    {'DATABASE_URL': 'postgresql://synthetic.invalid/db'},
    {'WMS_DATABASE_URI': 'sqlite:///unowned-temporary.db'},
    {'FLASK_ENV': 'production'}, {'FLASK_ENV': 'development'},
])
def test_guard_rejects_unknown_target_before_any_mutation(environment):
    original = environment.copy()
    with pytest.raises(SystemExit, match='安全阻断'):
        isolated_guard(environment)()
    assert environment == original


@pytest.mark.parametrize('loaded', ['app', 'app.models', 'config'])
def test_guard_rejects_preloaded_app_or_config(loaded):
    environment = {}
    with pytest.raises(SystemExit, match='预加载'):
        isolated_guard(environment, {loaded: object()})()
    assert not environment


@pytest.mark.parametrize('filename', BLOCKED)
def test_inherently_unsafe_script_stops_before_any_execution(filename):
    first = executable_statements(parsed(SCRIPTS / filename))[0]
    assert isinstance(first, ast.Raise)
    assert isinstance(first.exc, ast.Call) and isinstance(first.exc.func, ast.Name)
    assert first.exc.func.id == 'SystemExit'


@pytest.mark.parametrize('filename', GUARDED)
def test_guard_runs_before_all_original_executable_code(filename):
    first, second = executable_statements(parsed(SCRIPTS / filename))[:2]
    assert isinstance(first, ast.If) and isinstance(first.test, ast.Name) and first.test.id == '__package__'
    assert isinstance(second, ast.Expr) and isinstance(second.value, ast.Call)
    assert isinstance(second.value.func, ast.Name)
    assert second.value.func.id == 'require_synthetic_memory_database'


def test_batch_limit_dynamic_app_import_guarded_without_blocking_static_helpers():
    tree = parsed(SCRIPTS / 'verify_batch_limit.py')
    app_imports = [n for n in ast.walk(tree) if isinstance(n, ast.Import)
                   and any(alias.name == 'app' for alias in n.names)]
    assert len(app_imports) == 1
    guard_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Name) and n.func.id == 'require_synthetic_memory_database']
    assert len(guard_calls) == 1 and guard_calls[0].lineno < app_imports[0].lineno
    assert not any(isinstance(n, ast.Raise) for n in executable_statements(tree))


@pytest.mark.parametrize('function_name', ['main', 'check_web_login_csrf'])
def test_wms_bugs_dynamic_entries_stop_before_side_effects(function_name):
    tree = parsed(SCRIPTS / 'verify_wms_bugs.py')
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function_name)
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    assert isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call)
    assert ast.unparse(body[0].value.func) == 'require_test_runtime'
    isolated = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    checked = []
    def deny_unproved_runtime():
        checked.append(True)
        raise SystemExit('安全阻断：未证明运行能力')
    namespace = {'require_test_runtime': deny_unproved_runtime}
    exec(compile(isolated, '<synthetic-entry>', 'exec'), namespace)
    with pytest.raises(SystemExit, match='安全阻断'):
        namespace[function_name]()
    assert checked == [True]


def test_wms_bugs_preserves_static_helper_functions():
    tree = parsed(SCRIPTS / 'verify_wms_bugs.py')
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert {'function_body', 'routes_source'} <= functions.keys()
    assert all(not isinstance(n, ast.Raise) for name in ('function_body', 'routes_source')
               for n in functions[name].body)


def test_current_testing_config_is_hardcoded_memory():
    tree = parsed(ROOT / 'app/config.py')
    config = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TestingConfig')
    values = [n.value.value for n in config.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'SQLALCHEMY_DATABASE_URI' for t in n.targets)
              and isinstance(n.value, ast.Constant)]
    assert values == ['sqlite:///:memory:']


def test_route_enumeration_prints_results_but_refuses_file_output():
    tree = parsed(SCRIPTS / 'enumerate_routes.py')
    forbidden_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        if name in ('open', 'os.open', 'json.dump') or name.endswith(('.write_text', '.write_bytes')):
            forbidden_calls.append(name)
    assert forbidden_calls == []
    start = next(i for i, node in enumerate(tree.body)
                 if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                 and ast.unparse(node.value.func) == 'print'
                 and node.value.args and isinstance(node.value.args[0], ast.Call)
                 and ast.unparse(node.value.args[0].func) == 'json.dumps')
    tail = ast.fix_missing_locations(ast.Module(body=tree.body[start:], type_ignores=[]))
    output = []
    synthetic_rules = [{'path': '/synthetic', 'methods': ['GET', 'POST'], 'endpoint': 'example'}]
    namespace = {'json': json, 'rules': synthetic_rules, 'print': lambda value: output.append(value)}
    with pytest.raises(SystemExit, match='已停止写入'):
        exec(compile(tail, '<synthetic-route-output>', 'exec'), namespace)
    assert json.loads(output[0]) == synthetic_rules
    assert output[1] == '共 1 条路由'
    assert output[2] == 'GET: 1, POST: 1'


@pytest.mark.parametrize(('name', 'args'), [
    ('main', ()),
    ('collect_from_app', (True,)), ('collect_from_app', (False,)),
    ('_location_management_enabled', ()),
    ('collect_from_sqlite', ('sqlite:///unowned.db',)),
    ('collect_from_sqlite', ('sqlite:///:memory:',)),
    ('collect_from_sqlite', ('sqlite:///file:alias?mode=memory',)),
])
def test_inventory_identity_dynamic_entries_stop_before_access(name, args):
    tree = parsed(SCRIPTS / 'verify_inventory_identity.py')
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    body = list(function.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    if name in {'main', 'collect_from_sqlite'}:
        assert isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call)
        assert ast.unparse(body[0].value.func) == '_require_owned_test_profile'
    else:
        assert isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call)
        assert ast.unparse(body[0].value.func) == '_require_loaded_synthetic_app'
    module = ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[]))
    calls = []
    def reject_unproved_profile():
        calls.append('profile checked')
        raise SystemExit('安全阻断：合成隔离身份未证明')
    namespace = {'_require_owned_test_profile': reject_unproved_profile,
                 '_require_loaded_synthetic_app': reject_unproved_profile}
    exec(compile(module, '<synthetic-identity-entry>', 'exec'), namespace)
    with pytest.raises(SystemExit, match='安全阻断'):
        namespace[name](*args)
    assert calls == ['profile checked']


def test_inventory_identity_retains_calculation_and_original_sqlite_logic():
    tree = parsed(SCRIPTS / 'verify_inventory_identity.py')
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    original = functions['collect_from_sqlite']
    assert any(isinstance(node, ast.Call) and ast.unparse(node.func) == 'sqlite3.connect'
               for node in ast.walk(original))
    pure = ast.fix_missing_locations(ast.Module(
        body=[functions['build_identity_rows'], functions['find_mismatches']], type_ignores=[]))
    namespace = {'DEFAULT_TOLERANCE': 0.01}
    exec(compile(pure, '<synthetic-identity-calculation>', 'exec'), namespace)
    rows = namespace['build_identity_rows']([(1, 'SYNTHETIC', 5)], [(1, 5)], [(1, 3)])
    findings = namespace['find_mismatches'](rows)
    assert len(findings) == 1
    assert findings[0]['dimension'] == 'ledger_vs_txn' and findings[0]['delta'] == 2
