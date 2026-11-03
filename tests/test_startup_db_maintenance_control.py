"""Execute selected startup statements with in-memory call substitutes only.

Never import the application, connect a database, create credentials or files.
"""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'app' / 'app.py'
CALLS = (
    'backfill_empty_warehouse_documents', 'ensure_print_job_columns',
    'ensure_stock_transaction_warehouse_id_column', 'ensure_inventory_check_columns',
    'ensure_sales_return_source_columns', 'ensure_purchase_return_source_columns',
    'ensure_in_order_item_batch_columns', 'ensure_opening_stock_doc_columns',
    'ensure_opening_stock_doc_table', 'cleanup_dangling_opening_stock_transactions',
    'ensure_department_table', 'ensure_outbound_department_columns',
    'ensure_material_status_column', 'ensure_material_dedupe_unique_index',
    'ensure_excel_print_template_table', 'ensure_builtin_excel_doc_templates',
    'ensure_builtin_print_workstation', '_ensure_default_print_templates_unconditional',
    'backfill_stock_txn_warehouse_id',
)

def startup_fixture(env=None, marker=None):
    events, probes = [], []
    fake_path = SimpleNamespace(
        dirname=lambda path: 'C:/QA',
        join=lambda *parts: '/'.join(parts),
        exists=lambda path: path == marker,
    )
    ns = {'__file__': 'C:/QA/app.py',
          'os': SimpleNamespace(environ=dict(env or {}), path=fake_path),
          'app': SimpleNamespace(app_context=nullcontext,
                                 logger=SimpleNamespace(info=lambda *a: None, exception=lambda *a: None))}
    for name in CALLS:
        ns[name] = lambda name=name: events.append(name) or 1
    ns['_stock_txn_backfill_ready'] = lambda: probes.append('ready') or True
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    names = {'_env_flag', 'startup_db_touch_disabled', 'startup_db_upgrade_disabled',
             '_run_startup_db_maintenance', 'initialize_database'}
    definitions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(SOURCE), 'exec'), ns)
    steps = []
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            call = node.value
            if call.func.id in CALLS or call.func.id == '_run_startup_db_maintenance':
                steps.append(node)
        elif isinstance(node, ast.Try) and any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'backfill_stock_txn_warehouse_id'
            for n in ast.walk(node)
        ):
            steps.append(node)
    assert len(steps) == 19, 'Every existing startup maintenance site must remain covered'
    return ns, events, probes, ast.Module(body=steps, type_ignores=[])

def dispatch(fixture):
    ns, events, probes, steps = fixture
    exec(compile(steps, str(SOURCE), 'exec'), ns)
    return events, probes

@pytest.mark.parametrize('value', ['1', 'true', 'YES', ' on '])
def test_startup_db_touch_disabled(value):
    fixture = startup_fixture({'WMS_NO_DB_TOUCH': value})
    events, probes = dispatch(fixture)
    assert events == []
    assert probes == [], 'Disabled startup must not even probe maintenance readiness'

@pytest.mark.parametrize('marker', ['C:/QA/WMS_NO_DB_TOUCH.flag', 'C:/QA/instance/WMS_NO_DB_TOUCH.flag'])
def test_no_touch_marker_skips_all_import_maintenance(marker):
    assert dispatch(startup_fixture(marker=marker)) == ([], [])

@pytest.mark.parametrize('value', ['', '0', 'false', 'off'])
def test_default_or_explicit_false_preserves_every_call_and_order(value):
    assert dispatch(startup_fixture({'WMS_NO_DB_TOUCH': value})) == (list(CALLS), ['ready'])

@pytest.mark.parametrize('value', ['1', 'true', 'YES', 'on'])
def test_startup_db_upgrade_disabled(value):
    fixture = startup_fixture({'WMS_SKIP_STARTUP_DB_UPGRADE': value})
    assert fixture[0]['startup_db_upgrade_disabled']() is True
    assert dispatch(fixture) == (list(CALLS), ['ready'])

def test_no_touch_takes_precedence_over_upgrade_only_option():
    assert dispatch(startup_fixture({'WMS_NO_DB_TOUCH': '1', 'WMS_SKIP_STARTUP_DB_UPGRADE': '1'})) == ([], [])

@pytest.mark.parametrize('env', [{'WMS_NO_DB_TOUCH': '1'}, {'WMS_SKIP_STARTUP_DB_UPGRADE': '1'}])
def test_pragma_registration_still_precedes_disabled_initialization(env):
    ns, events, _, _ = startup_fixture(env)
    ns['_register_sqlite_pragma_listener'] = lambda: events.append('register-pragma')
    ns['app'].logger.warning = lambda *args: None
    ns['initialize_database']()
    assert events == ['register-pragma']

def test_runtime_maintenance_function_is_not_globally_disabled():
    ns, events, _, _ = startup_fixture({'WMS_NO_DB_TOUCH': '1'})
    ns['ensure_material_dedupe_unique_index']()
    assert events == ['ensure_material_dedupe_unique_index']

def test_dispatch_helper_preserves_return_value():
    ns, _, _, _ = startup_fixture()
    sentinel = object()
    assert ns['_run_startup_db_maintenance'](lambda: sentinel) is sentinel

def test_dispatch_helper_does_not_hide_normal_errors():
    ns, _, _, _ = startup_fixture()
    def failing():
        raise ValueError('synthetic-maintenance-error')
    with pytest.raises(ValueError, match='synthetic-maintenance-error'):
        ns['_run_startup_db_maintenance'](failing)

@pytest.mark.parametrize('filename', [
    'test_backfill_empty_warehouse_documents.py', 'test_ensure_department_table.py',
    'test_ensure_inventory_check_columns.py', 'test_ensure_opening_stock_doc_table.py',
    'test_ensure_outbound_department_columns.py', 'test_ensure_print_job_columns.py',
    'test_ensure_excel_print_template_table.py', 'test_ensure_purchase_return_source_columns.py',
    'test_ensure_sales_return_source_columns.py',
])
def test_legacy_subprocess_fixture_explicitly_selects_upgrade_only_mode(filename):
    tree=ast.parse((SOURCE.parents[1]/'tests'/filename).read_text(encoding='utf-8'))
    flags={}
    for node in ast.walk(tree):
        if not isinstance(node,ast.Assign) or len(node.targets)!=1: continue
        target=node.targets[0]
        if (isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name)
            and target.value.id=='env' and isinstance(target.slice,ast.Constant)
            and target.slice.value in ('WMS_NO_DB_TOUCH','WMS_SKIP_STARTUP_DB_UPGRADE')):
            assert isinstance(node.value,ast.Constant)
            flags[target.slice.value]=node.value.value
    assert flags=={'WMS_NO_DB_TOUCH':'0','WMS_SKIP_STARTUP_DB_UPGRADE':'1'}
