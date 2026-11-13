"""Initial-stock input and real opening entry on the guarded synthetic ORM.

Preserves all 26 opening-stock source regressions and adds 14 precise cases.
The full application is never imported; its real request tests run only in CI.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys


SETUP = r'''
def source_function(filename, name):
    key = filename, name
    if key in initial_source_functions:
        return initial_source_functions[key]
    if filename not in initial_source_trees:
        initial_source_trees[filename] = ast.parse((root / filename).read_text(encoding='utf-8-sig'))
    tree = initial_source_trees[filename]
    found = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(found) != 1:
        raise AssertionError('Unique product source function required: ' + name)
    node = found[0]
    node.decorator_list = []
    node.body = [n for n in node.body if not (isinstance(n, ast.ImportFrom) and n.module == 'app')]
    initial_source_functions[key] = node
    return node
extras = [source_function('app/utils.py', 'parse_float_value'),
          source_function('app/app.py', 'parse_bounded_number'),
          source_function('app/app.py', '_stock_location_from_warehouse'),
          source_function('app/app.py', 'resolve_inventory_warehouse_id'),
          source_function('app/app.py', 'add_stock_transaction'),
          source_function('app/app.py', 'add_location_inventory_atomic'),
          source_function('app/services/warehouse_stock_service.py', 'apply_opening_balance')]
route = source_function('app/routes/material.py', 'add_material')
first = [i for i,n in enumerate(route.body) if isinstance(n, ast.Assign)
         and any(isinstance(t, ast.Name) and t.id == 'initial_stock' for t in n.targets)]
price = [i for i,n in enumerate(route.body) if isinstance(n, ast.Assign)
         and any(isinstance(t, ast.Name) and t.id == 'initial_price' for t in n.targets)]
if not first or len(price) != 1 or price[0] <= first[0]:
    raise AssertionError('Initial-stock parsing source range missing')
probe = ast.parse('def initial_stock_from_real_route():\n    pass\n').body[0]
probe.body = route.body[first[0]:price[0]] + [ast.Return(value=ast.Name(id='initial_stock', ctx=ast.Load()))]
extras.append(probe)
self.ns.update(MAX_TRANSACTION_QUANTITY=1_000_000_000_000, MAX_REASONABLE_STOCK=99_999_999.99,
    current_user=types.SimpleNamespace(is_authenticated=False),
    api_error=lambda message: {'status':'error','msg':message})
exec(compile(ast.fix_missing_locations(ast.Module(body=extras, type_ignores=[])),
             '<source-initial-stock>', 'exec'), self.ns)
'''

CASE = r'''
def test_initial_stock_{name}(self):
    self.location_enabled = {location_on}
    self.ns['request'] = types.SimpleNamespace(form={{'stock': {raw!r}}})
    initial = self.ns['initial_stock_from_real_route']()
    self.assertEqual(initial, {expected})
    warehouse = self.session.get(Warehouse, 1)
    created = Material(code='SYN-NEW', stock=initial)
    self.session.add(created)
    self.session.flush()
    if initial > 0:
        result = self.ns['apply_opening_balance'](created, initial, warehouse=warehouse,
            location=warehouse.name, reference_id=created.id)
        self.assertTrue(result[0], result)
    self.session.commit()
    self.assertEqual(created.stock, {expected})
    txns = self.session.query(StockTransaction).filter_by(material_id=created.id).all()
    self.assertEqual(sum(row.quantity for row in txns), {expected})
    self.assertEqual(len(txns), int({expected} > 0))
    self.assertTrue(all(row.warehouse_id == 1 for row in txns))
    locations = self.session.query(LocationInventory).filter_by(material_id=created.id).all()
    if self.location_enabled and {expected} > 0:
        self.assertEqual([(row.warehouse_id, row.quantity) for row in locations], [(1, {expected})])
    else:
        self.assertEqual(locations, [])
'''

MORE = r'''
def test_initial_stock_out_of_range_remains_rejected_before_normalizing(self):
    self.ns['request'] = types.SimpleNamespace(form={'stock':'99999999.991'})
    result = self.ns['initial_stock_from_real_route']()
    self.assertEqual(result['status'], 'error')
    self.assertEqual(self.session.query(StockTransaction).count(), 0)

def test_initial_stock_without_default_preserves_unknown_ownership(self):
    self.location_enabled = True
    self.ns['request'] = types.SimpleNamespace(form={'stock':'1.005'})
    initial = self.ns['initial_stock_from_real_route']()
    self.assertEqual(initial, 1.01)
    created = Material(code='SYN-NEW', stock=initial)
    self.session.add(created)
    self.session.flush()
    result = self.ns['apply_opening_balance'](created, initial, warehouse=None, reference_id=created.id)
    self.assertTrue(result[0], result)
    self.session.commit()
    self.assertEqual(created.stock, 1.01)
    txn = self.session.query(StockTransaction).filter_by(material_id=created.id).one()
    self.assertEqual(txn.quantity, 1.01)
    self.assertIsNone(txn.warehouse_id)
    self.assertEqual(self.session.query(LocationInventory).filter_by(material_id=created.id).count(), 0)
'''


def main():
    harness = Path(__file__).with_name('verify_opening_stock_negative_hint_20261108.py')
    tree = ast.parse(harness.read_text(encoding='utf-8-sig'))
    original = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    transaction = next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name == 'StockTransaction')
    transaction.body.extend(ast.parse(
        'transaction_type: Mapped[str | None] = mapped_column(String)\n'
        'operator_id: Mapped[int | None] = mapped_column(Integer)\n'
        'remark: Mapped[str | None] = mapped_column(String)\n').body)
    suite = next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name == 'OpeningHintRegression')
    original.body[original.body.index(suite):original.body.index(suite)] = ast.parse(
        'initial_source_trees = {}\ninitial_source_functions = {}\n').body
    setup = next(n for n in suite.body if isinstance(n, ast.FunctionDef) and n.name == 'setUp')
    setup.body.extend(ast.parse(SETUP).body)
    extra = []
    for raw, expected in (('1.005',1.01),('1.004',1.0),('0.004',0.0),('0.005',0.01),
                          ('12.34',12.34),('99999999.99',99999999.99)):
        for location_on in (False,True):
            name = raw.replace('.','_') + ('_on' if location_on else '_off')
            extra.extend(ast.parse(CASE.format(name=name,raw=raw,expected=expected,location_on=location_on)).body)
    extra.extend(ast.parse(MORE).body)
    suite.body.extend(extra)
    counts = [n for n in ast.walk(original) if isinstance(n, ast.Compare) and isinstance(n.left, ast.Call)
              and isinstance(n.left.func, ast.Attribute) and n.left.func.attr == 'countTestCases']
    if len(extra) != 14 or len(counts) != 1 or counts[0].comparators[0].value != 26:
        raise AssertionError('Explicit original and additional method lists changed')
    counts[0].comparators[0] = ast.Constant(value=40)
    constants = [n for n in tree.body if isinstance(n, ast.Assign)]
    imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    namespace = {'__file__': __file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,*constants,original],type_ignores=[])),
                 '<guarded-material-initial-stock>', 'exec'),namespace)
    namespace['main']()


def test_initial_stock_in_explicit_guarded_child():
    env = {key: os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
                            capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    main()
