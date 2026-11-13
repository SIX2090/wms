"""Actual fixture bodies + actual stock functions/models, guarded fresh memory."""
import ast
import os
from pathlib import Path
import subprocess
import sys


SETUP=r'''
from sqlalchemy import case
ns['case']=case
ns['allow_negative_stock']=lambda:False
for name in ('_stock_location_from_warehouse','resolve_inventory_warehouse_id','add_stock_transaction',
             'update_location_inventory','add_location_inventory_atomic','deduct_location_inventory_atomic',
             '_apply_opening_stock_balance','_opening_stock_reverse_all_lines'):
    extract('app/app.py',name)
extract('app/services/warehouse_stock_service.py','apply_opening_balance')
extract('tests/test_opening_stock_multi_doc.py','_wipe')
ns['_wipe_multi']=ns.pop('_wipe')
extract('tests/test_opening_stock_delete_all.py','_wipe')
ns['_wipe_purge']=ns.pop('_wipe')
extract('tests/test_opening_stock_delete_all.py','test_t4_orphan_lines_removed_and_reversed')
'''

CASES=r'''
def produce_two_lines(self,qty1=100,qty2=20):
    ns['location_management_enabled']=lambda:True
    second=ns['Material'](code='SYN-SECOND',name='合成另一物料',stock=0)
    doc=ns['OpeningStockDoc'](doc_no='SYN-OPEN',warehouse_id=self.a.id)
    db.session.add_all([second,doc])
    db.session.flush()
    first,_=ns['_apply_opening_stock_balance'](None,self.material,qty1,0,0,'明确原行A',
        warehouse=self.a,doc_id=doc.id)
    last,_=ns['_apply_opening_stock_balance'](None,second,qty2,0,0,'明确原行B',
        warehouse=self.b,doc_id=doc.id)
    db.session.commit()
    return doc,first,last,second

def reseed_same_ids_after_actual_fixture_cleanup(self,kind):
    self.produce_two_lines()
    ns['_wipe_'+kind](self)
    self.user=ns['User'](id=1,username='synthetic-recreated',password_hash='non-login-test-value')
    self.a=ns['Warehouse'](id=1,code='SYN-A',name='合成甲仓',status='active')
    self.b=ns['Warehouse'](id=2,code='SYN-B',name='合成乙仓',status='active')
    self.material=ns['Material'](id=1,code='SYN-M',name='合成物料',stock=0)
    db.session.add_all([self.user,self.a,self.b,self.material])
    db.session.commit()

def test_actual_multi_doc_fixture_wipes_location_rows_before_material_ids_are_reused(self):
    self.produce_two_lines()
    ns['_wipe_multi'](self)
    self.assertEqual(ns['LocationInventory'].query.count(),0)
    self.assertEqual(ns['StockTransaction'].query.count(),0)
    self.assertEqual(ns['Material'].query.count(),0)

def test_actual_purge_fixture_wipes_location_rows_before_material_ids_are_reused(self):
    self.produce_two_lines()
    ns['_wipe_purge'](self)
    self.assertEqual(ns['LocationInventory'].query.count(),0)
    self.assertEqual(ns['StockTransaction'].query.count(),0)
    self.assertEqual(ns['Material'].query.count(),0)

def test_fresh_producer_keeps_both_warehouses_in_all_three_ledgers(self):
    doc,first,last,second=self.produce_two_lines()
    self.assertEqual([(row.warehouse_id,row.quantity) for row in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)],
                     [(self.a.id,100),(self.b.id,20)])
    self.assertEqual(ns['_reverse_opening_stock_line'](last),(True,''))
    db.session.delete(last)
    db.session.commit()
    self.assertEqual(second.stock,0)
    self.assertEqual(self.material.stock,100)

def test_removed_line_after_reused_fixture_ids_does_not_inherit_previous_location_quantity(self):
    self.reseed_same_ids_after_actual_fixture_cleanup('multi')
    doc,first,last,second=self.produce_two_lines()
    self.assertEqual(ns['_reverse_opening_stock_line'](last),(True,''))
    db.session.delete(last)
    db.session.commit()
    self.assertEqual(second.stock,0)
    self.assertEqual(self.material.stock,100)
    self.assertEqual(ns['LocationInventory'].query.filter_by(material_id=second.id).one().quantity,0)

def test_doc_reversal_after_reused_fixture_ids_preserves_original_rollback_contract(self):
    self.reseed_same_ids_after_actual_fixture_cleanup('multi')
    doc,first,last,second=self.produce_two_lines(80,30)
    self.assertEqual(ns['_opening_stock_reverse_all_lines'](doc),(True,'',2))
    db.session.delete(doc)
    db.session.commit()
    self.assertEqual(self.material.stock,0)
    self.assertEqual(second.stock,0)
    self.assertEqual(ns['OpeningStock'].query.count(),0)
    self.assertEqual(ns['StockTransaction'].query.count(),0)
    self.assertTrue(all(row.quantity==0 for row in ns['LocationInventory'].query))

def purge_model_only(self,payload):
    # Component adapter only: execute the actual reversal on actual models.
    # HTTP/auth/edit guards remain for the existing isolated CI tests.
    for line in ns['OpeningStock'].query.all():
        ok,message=ns['_reverse_opening_stock_line'](line)
        if not ok:
            db.session.rollback()
            return 400,{'status':'error','msg':message}
        db.session.delete(line)
    db.session.commit()
    return 200,{'status':'success'}

def test_actual_orphan_positive_fixture_has_recorded_source_before_reversal(self):
    ns['location_management_enabled']=lambda:True
    self.m1,self.wh1=self.material,self.a
    self._stock=lambda material:db.session.get(ns['Material'],material.id).stock
    self._ok_payload=lambda:{'confirm':True}
    self._delete_all=self.purge_model_only
    ns['test_t4_orphan_lines_removed_and_reversed'](self)
    self.assertEqual(ns['StockTransaction'].query.count(),0)
    self.assertEqual(ns['LocationInventory'].query.one().quantity,0)

def test_missing_recorded_source_remains_rejected_without_weakening_product_guard(self):
    line=ns['OpeningStock'](material_id=self.material.id,warehouse_id=self.a.id,quantity=30,doc_id=None)
    self.material.stock=30
    db.session.add(line)
    db.session.commit()
    ok,message=ns['_reverse_opening_stock_line'](line)
    self.assertFalse(ok)
    self.assertIn('净额不一致',message)
    db.session.rollback()
    self.assertEqual(self.material.stock,30)
    self.assertIsNotNone(db.session.get(ns['OpeningStock'],line.id))
    self.assertEqual(ns['StockTransaction'].query.count(),0)
'''


def main():
    tree=ast.parse(Path(__file__).with_name('verify_audit_real_models_20261113.py').read_text(encoding='utf-8-sig'))
    original=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    suite=next(node for node in original.body if isinstance(node,ast.ClassDef) and node.name=='RealModelBoundaries')
    original.body[original.body.index(suite):original.body.index(suite)]=ast.parse(SETUP).body
    extra=ast.parse(CASES).body
    suite.body.extend(extra)
    methods=[node for node in extra if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')]
    counts=[node for node in ast.walk(original) if isinstance(node,ast.Compare) and isinstance(node.left,ast.Call)
        and isinstance(node.left.func,ast.Attribute) and node.left.func.attr=='countTestCases']
    if len(methods)!=7 or len(counts)!=1 or counts[0].comparators[0].value!=9:
        raise AssertionError('Explicit fixture method list changed or became empty')
    counts[0].comparators[0]=ast.Constant(value=16)
    imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    ns={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
                 '<guarded-opening-fixture-ledgers>','exec'),ns)
    ns['main']()


def test_fixture_ledgers_in_guarded_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
