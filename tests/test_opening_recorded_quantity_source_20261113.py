"""Historical opening reversal: real extracted models, fresh guarded memory only."""
import ast
import os
from pathlib import Path
import subprocess
import sys


SETUP = r'''
from sqlalchemy import case
ns['case'] = case
ns['allow_negative_stock'] = lambda: False
for name in ('resolve_inventory_warehouse_id', '_stock_location_from_warehouse',
             '_material_stock_unattributed', '_wh_stock_guards', 'update_location_inventory',
             'add_location_inventory_atomic', 'deduct_location_inventory_atomic'):
    extract('app/app.py', name)
for name in ('_recorded_quantity_matches', '_reverse_recorded_opening_stock'):
    extract('app/services/warehouse_stock_service.py', name)
ns['allow_negative_location_stock'] = lambda: False
'''

CASES = r'''
def seed_recorded(self, quantity=1.005, *, location_on=False, explicit=True, values=None):
    ns['location_management_enabled'] = lambda: location_on
    ns['allow_negative_location_stock'] = lambda: False
    line = ns['OpeningStock'](material_id=self.material.id, warehouse_id=self.a.id,
        location='SAME' if explicit else '', quantity=quantity, remark='明确期初')
    db.session.add(line)
    db.session.flush()
    original = []
    for value in values if values is not None else [quantity]:
        row = self.txn(self.a.id, value, 'opening_stock', line.id)
        row.location = 'recorded-old-warehouse-name'
        original.append(row)
    other = self.txn(self.b.id, 20, 'material_initial', self.material.id)
    self.material.stock = 20 + quantity
    if location_on:
        db.session.add_all([
            ns['LocationInventory'](material_id=self.material.id, warehouse_id=self.a.id,
                location='SAME' if explicit else 'recorded-old-warehouse-name', quantity=quantity),
            ns['LocationInventory'](material_id=self.material.id, warehouse_id=self.b.id,
                location='SAME', quantity=20)])
    db.session.commit()
    return line, original, other

def assert_recorded_success(self, quantity, *, location_on=False, explicit=True, values=None):
    line, rows, other = self.seed_recorded(quantity, location_on=location_on, explicit=explicit, values=values)
    other_id = other.id
    self.assertEqual(ns['_reverse_opening_stock_line'](line), (True,''))
    db.session.delete(line)
    db.session.commit()
    self.assertAlmostEqual(self.material.stock, 20, places=12)
    self.assertEqual([(row.id,row.quantity) for row in ns['StockTransaction'].query], [(other_id,20)])
    if location_on:
        positions = {(row.warehouse_id,row.location):row.quantity for row in ns['LocationInventory'].query}
        self.assertEqual(positions[(self.b.id,'SAME')],20)
        self.assertAlmostEqual(positions[(self.a.id,'SAME' if explicit else 'recorded-old-warehouse-name')],0,places=12)

def snapshot(self):
    return (self.material.stock,
        [(row.id,row.quantity) for row in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)],
        [(row.id,row.quantity) for row in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)])

def assert_recorded_refusal(self, line, message):
    before = self.snapshot()
    result = ns['_reverse_opening_stock_line'](line)
    self.assertFalse(result[0],result)
    self.assertIn(message,result[1])
    self.assertEqual(self.snapshot(),before)
    db.session.rollback()

def test_raw_quantity_without_locations(self):
    self.assert_recorded_success(1.005)

def test_raw_quantity_with_explicit_original_bin(self):
    self.assert_recorded_success(1.005,location_on=True)

def test_normal_two_decimals_without_locations(self):
    self.assert_recorded_success(1.01)

def test_normal_two_decimals_with_locations(self):
    self.assert_recorded_success(1.01,location_on=True)

def test_empty_bin_uses_recorded_placeholder_after_warehouse_rename(self):
    self.a.name = 'changed-current-name'
    db.session.commit()
    self.assert_recorded_success(1.005,location_on=True,explicit=False)

def test_multiple_edits_and_negative_deltas_keep_original_precision(self):
    self.assert_recorded_success(1.005,location_on=True,values=[2.005,-1.0])

def test_float_point_one_plus_point_two_is_not_a_business_difference(self):
    self.assert_recorded_success(0.1+0.2,location_on=True,values=[0.1,0.2])

def test_positive_and_negative_edits_net_zero_are_removed(self):
    self.assert_recorded_success(0,location_on=True,values=[1.005,-1.005])

def test_negative_opening_keeps_signed_inverse(self):
    self.assert_recorded_success(-1.005,location_on=True)

def test_quantity_and_recorded_net_differing_by_point_zero_zero_five_refuse(self):
    line, rows, _ = self.seed_recorded(1.005)
    rows[0].quantity = 1.01
    self.material.stock = 21.01
    db.session.commit()
    self.assert_recorded_refusal(line,'净额不一致')

def test_material_total_existing_point_zero_zero_five_difference_refuses(self):
    line, *_ = self.seed_recorded()
    self.material.stock += 0.005
    db.session.commit()
    self.assert_recorded_refusal(line,'总账与流水账不一致')

def test_location_total_existing_normalization_difference_refuses(self):
    line, *_ = self.seed_recorded(location_on=True)
    location = ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one()
    location.quantity = 1.01
    db.session.commit()
    self.assert_recorded_refusal(line,'库位账与总账或原仓流水不一致')

def test_unknown_original_warehouse_refuses_instead_of_defaulting(self):
    line, rows, _ = self.seed_recorded(location_on=True)
    line.warehouse_id = None
    rows[0].warehouse_id = None
    db.session.commit()
    self.assert_recorded_refusal(line,'原仓库归属缺失或冲突')

def test_proven_unknown_original_warehouse_without_locations_stays_unknown(self):
    line, rows, other = self.seed_recorded()
    line.warehouse_id = None
    rows[0].warehouse_id = None
    db.session.commit()
    self.assertEqual(ns['_reverse_opening_stock_line'](line),(True,''))
    db.session.commit()
    self.assertAlmostEqual(self.material.stock,20,places=12)
    self.assertEqual([(row.id,row.warehouse_id,row.quantity) for row in ns['StockTransaction'].query],
                     [(other.id,self.b.id,20)])

def test_source_warehouse_conflict_refuses(self):
    line, rows, _ = self.seed_recorded()
    rows[0].warehouse_id = self.b.id
    db.session.commit()
    self.assert_recorded_refusal(line,'原仓库归属缺失或冲突')

def test_missing_original_placeholder_refuses(self):
    line, rows, _ = self.seed_recorded(location_on=True,explicit=False)
    rows[0].location = ''
    db.session.commit()
    self.assert_recorded_refusal(line,'原库位缺失')

def test_different_bin_balance_cannot_replace_missing_original_bin(self):
    line, *_ = self.seed_recorded(location_on=True)
    location = ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one()
    location.location = 'OTHER'
    db.session.commit()
    self.assert_recorded_refusal(line,'原库位记录缺失或重复')

def test_nonzero_line_with_missing_source_cannot_change_any_balance(self):
    line, rows, _ = self.seed_recorded()
    db.session.delete(rows[0])
    self.material.stock = 20
    db.session.commit()
    self.assert_recorded_refusal(line,'净额不一致')

def test_repeated_inverse_cannot_reduce_balance_twice(self):
    line, *_ = self.seed_recorded()
    self.assertEqual(ns['_reverse_opening_stock_line'](line),(True,''))
    self.assert_recorded_refusal(line,'净额不一致')

def test_caller_rollback_restores_all_three_ledgers_and_source(self):
    line, *_ = self.seed_recorded(location_on=True)
    before = self.snapshot()
    self.assertEqual(ns['_reverse_opening_stock_line'](line),(True,''))
    db.session.rollback()
    self.assertEqual(self.snapshot(),before)

def test_source_collision_004_still_refuses(self):
    line, rows, _ = self.seed_recorded()
    self.assertEqual(line.id,line.material_id)
    rows[0].remark = '新增物料初始库存'
    db.session.commit()
    self.assert_recorded_refusal(line,'无法安全区分')

def test_cannot_hide_point_zero_zero_five_using_ledger_epsilon(self):
    self.assertFalse(ns['_recorded_quantity_matches'](1.005,1.01))
    self.assertFalse(ns['_recorded_quantity_matches'](1e12,1e12+0.005,1e16))
    self.assertTrue(ns['_recorded_quantity_matches'](0.1+0.2,0.3))
    self.assertFalse(ns['_recorded_quantity_matches'](float('inf'),float('inf')))

def test_float_unrepresentable_small_change_at_huge_balance_refuses(self):
    line, rows, other = self.seed_recorded()
    other.quantity = 1e16
    self.material.stock = 1e16 + 1.005
    db.session.commit()
    self.assert_recorded_refusal(line,'Float 可逆精度')

def test_nonzero_tiny_quantity_cannot_disappear_in_total_float_balance(self):
    line, *_ = self.seed_recorded(1e-20)
    self.assert_recorded_refusal(line,'总账 Float 可逆精度')

def test_nonzero_tiny_quantity_cannot_disappear_in_original_bin_float_balance(self):
    line, rows, other = self.seed_recorded(1e-20,location_on=True)
    self.txn(self.a.id,20,'material_initial',self.material.id)
    other.quantity=-20
    self.material.stock=1e-20
    ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=20
    ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity=-20
    db.session.commit()
    self.assert_recorded_refusal(line,'库位 Float 可逆精度')

def test_reversing_negative_opening_improves_existing_negative_bin_without_new_permission(self):
    line, rows, other = self.seed_recorded(-1.005,location_on=True)
    self.txn(self.a.id,-5,'material_initial',self.material.id)
    self.material.stock=13.995
    ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=-6.005
    db.session.commit()
    self.assertEqual(ns['_reverse_opening_stock_line'](line),(True,''))
    db.session.commit()
    self.assertAlmostEqual(self.material.stock,15,places=12)
    self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity,-5,places=12)
    self.assertEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity,20)
    self.assertAlmostEqual(math.fsum(row.quantity for row in ns['StockTransaction'].query),15,places=12)

def test_injected_location_update_failure_rolls_back_earlier_total_update(self):
    line, *_ = self.seed_recorded(location_on=True)
    before = self.snapshot()
    def fail_location(_connection,_cursor,statement,_parameters,_context,_executemany):
        if statement.lstrip().upper().startswith('UPDATE LOCATION_INVENTORY'):
            raise RuntimeError('owned synthetic location DML failure')
    event.listen(db.engine,'before_cursor_execute',fail_location)
    try:
        with self.assertRaisesRegex(RuntimeError,'owned synthetic location DML failure'):
            ns['_reverse_opening_stock_line'](line)
    finally:
        event.remove(db.engine,'before_cursor_execute',fail_location)
    db.session.rollback()
    self.assertEqual(self.snapshot(),before)
'''


def main():
    harness = Path(__file__).with_name('verify_audit_real_models_20261113.py')
    tree = ast.parse(harness.read_text(encoding='utf-8-sig'))
    original = next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    suite = next(node for node in original.body if isinstance(node,ast.ClassDef) and node.name=='RealModelBoundaries')
    original.body[original.body.index(suite):original.body.index(suite)] = ast.parse(SETUP).body
    extra = ast.parse(CASES).body
    suite.body.extend(extra)
    count = [node for node in ast.walk(original) if isinstance(node,ast.Compare) and isinstance(node.left,ast.Call)
             and isinstance(node.left.func,ast.Attribute) and node.left.func.attr=='countTestCases']
    methods = [node for node in extra if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')]
    if len(count)!=1 or len(methods)!=27 or count[0].comparators[0].value!=9:
        raise AssertionError('Explicit baseline/additional source method lists changed')
    count[0].comparators[0] = ast.Constant(value=36)
    imports = [node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
                 '<guarded-recorded-opening-quantity>','exec'),namespace)
    namespace['main']()


def test_recorded_quantity_in_explicit_guarded_child():
    env = {key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
                          capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
