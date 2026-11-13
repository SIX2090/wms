"""BUG-2026-11-13-004: actual source models and guarded synthetic memory only."""
import ast
import os
from pathlib import Path
import subprocess
import sys


SETUP = r'''
from flask import url_for
from sqlalchemy import create_engine
ns['url_for'] = url_for
for name in ('_stock_location_from_warehouse', 'resolve_inventory_warehouse_id', 'add_stock_transaction',
             '_ledger_document_date_getters', '_ledger_document_date_map', '_report_detail_url', '_report_reference_info'):
    extract('app/app.py', name)
extract('app/services/warehouse_stock_service.py', 'apply_opening_balance')
assignments = [node for node in trees['app/app.py'].body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'REPORT_REFERENCE_LINKS' for target in node.targets)]
if len(assignments) != 1:
    raise AssertionError('Unique real report source map required')
exec(compile(ast.fix_missing_locations(ast.Module(body=assignments, type_ignores=[])),
             '<source-reference-map>', 'exec'), ns)
'''

CASES = r'''
def collision(self, *, audit=True, explicit=False, same_remark=False, foreign=False, stock=5):
    base = datetime(2020, 1, 1, 10)
    self.material.created_at = base
    self.material.stock = stock
    initial = None
    if stock:
        initial = ns['StockTransaction'](material_id=self.material.id, warehouse_id=self.a.id,
            quantity=stock, transaction_type='opening',
            reference_type='material_initial' if explicit else 'opening_stock', reference_id=self.material.id,
            remark='新增物料初始库存', operator_id=self.user.id, created_at=base + timedelta(seconds=1))
        db.session.add(initial)
    if audit:
        witness = ns['OperationAudit'](operation='add_material', target_type='material', target_id=self.material.id,
            user_id=self.user.id, status='success', new_data=json.dumps({'stock':stock}),
            operation_time=base + timedelta(seconds=2))
        db.session.add(witness)
    else:
        witness = None
    db.session.commit()
    target = self.material
    if foreign:
        target = ns['Material'](code='SYN-OTHER', name='合成另一物料', stock=0, created_at=base)
        db.session.add(target)
        db.session.flush()
    line = ns['OpeningStock'](material_id=target.id, warehouse_id=self.b.id, quantity=7,
        remark='新增物料初始库存' if same_remark else '期初测试', created_at=base + timedelta(seconds=3))
    db.session.add(line)
    db.session.flush()
    self.assertEqual(line.id, self.material.id)
    target.stock += 7
    opening = ns['StockTransaction'](material_id=target.id, warehouse_id=self.b.id, quantity=7,
        transaction_type='opening', reference_type='opening_stock', reference_id=line.id,
        remark=line.remark, operator_id=self.user.id, created_at=base + timedelta(seconds=4))
    db.session.add(opening)
    db.session.commit()
    return line, initial, opening, witness, target

def refuse_without_writes(self, line):
    stock = line.material.stock
    before = [(row.id,row.quantity,row.reference_type) for row in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)]
    ok, message = ns['_reverse_opening_stock_line'](line)
    self.assertFalse(ok)
    self.assertIn('无法安全区分', message)
    self.assertEqual(line.material.stock, stock)
    self.assertEqual([(row.id,row.quantity,row.reference_type) for row in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)], before)
    self.assertIsNotNone(db.session.get(ns['OpeningStock'], line.id))
    db.session.rollback()

def delete_and_preserve_initial(self, line, initial, opening, target):
    initial_id, opening_id = initial.id, opening.id
    self.assertEqual(ns['_reverse_opening_stock_line'](line), (True,''))
    db.session.delete(line)
    db.session.commit()
    self.assertIsNone(db.session.get(ns['StockTransaction'], opening_id))
    self.assertIsNotNone(db.session.get(ns['StockTransaction'], initial_id))
    self.assertEqual(self.material.stock, 5)
    self.assertEqual(sum(row.quantity for row in ns['StockTransaction'].query.filter_by(material_id=self.material.id)), 5)
    if target.id != self.material.id:
        self.assertEqual(target.stock,0)

def test_legacy_initial_is_not_disambiguated_by_a_best_effort_audit(self):
    line, initial, opening, witness, target = self.collision()
    self.refuse_without_writes(line)

def test_same_marker_text_and_best_effort_audit_still_require_manual_review(self):
    line, initial, opening, witness, target = self.collision(same_remark=True)
    self.refuse_without_writes(line)

def test_missing_audit_cannot_make_a_remark_prove_ownership(self):
    line, *_ = self.collision(audit=False,same_remark=True)
    self.refuse_without_writes(line)

def test_wrong_audit_quantity_refuses_instead_of_selecting_a_matching_subset(self):
    line, initial, opening, witness, target = self.collision(same_remark=True)
    witness.new_data = json.dumps({'stock':6})
    db.session.commit()
    self.refuse_without_writes(line)

def test_wrong_audit_actor_refuses(self):
    line, initial, opening, witness, target = self.collision()
    other = ns['User'](username='synthetic-other',password_hash='not-a-login-hash')
    db.session.add(other)
    db.session.flush()
    witness.user_id = other.id
    db.session.commit()
    self.refuse_without_writes(line)

def test_audit_after_line_creation_does_not_prove_initial_origin(self):
    line, initial, opening, witness, target = self.collision()
    witness.operation_time = line.created_at + timedelta(seconds=1)
    db.session.commit()
    self.refuse_without_writes(line)

def test_duplicate_creation_audits_are_not_guessed(self):
    line, initial, opening, witness, target = self.collision()
    db.session.add(ns['OperationAudit'](operation='add_material',target_type='material',target_id=self.material.id,
        user_id=self.user.id,status='success',new_data=json.dumps({'stock':5}),operation_time=witness.operation_time))
    db.session.commit()
    self.refuse_without_writes(line)

def test_same_reference_id_on_another_material_is_not_deleted(self):
    line, initial, opening, witness, target = self.collision(audit=False,foreign=True)
    self.delete_and_preserve_initial(line,initial,opening,target)

def test_explicit_new_origin_is_not_a_legacy_line_transaction(self):
    line, initial, opening, witness, target = self.collision(audit=False,explicit=True)
    self.delete_and_preserve_initial(line,initial,opening,target)

def test_zero_audit_cannot_prove_ownership_of_a_legacy_marker(self):
    line, initial, opening, witness, target = self.collision(stock=0,same_remark=True)
    self.refuse_without_writes(line)

def test_missing_transaction_time_refuses(self):
    line, initial, opening, witness, target = self.collision()
    initial.created_at = None
    db.session.commit()
    self.refuse_without_writes(line)

def test_legacy_initial_does_not_borrow_an_opening_warehouse_or_business_date(self):
    line, initial, opening, witness, target = self.collision()
    initial.warehouse_id = None
    initial.location = None
    line.date = date(2022,2,2)
    db.session.commit()
    self.assertEqual(ns['_ledger_source_warehouse_map']([initial]),{})
    self.assertEqual(ns['_ledger_document_date_map']([initial]),{})
    formatter = ns['_report_reference_info']
    import inspect
    kwargs = {'material_id':self.material.id}
    if 'source_remark' in inspect.signature(formatter).parameters:
        kwargs['source_remark'] = initial.remark
    label,url = formatter('opening_stock',line.id,**kwargs)
    self.assertIn('来源待核对',label)
    self.assertEqual(url,'')

def test_foreign_material_cannot_borrow_line_warehouse_or_date_even_without_marker(self):
    line, initial, opening, witness, target = self.collision(foreign=True)
    initial.remark = '历史未明确备注'
    initial.warehouse_id = None
    initial.location = None
    db.session.commit()
    self.assertEqual(ns['_ledger_source_warehouse_map']([initial]),{})
    self.assertEqual(ns['_ledger_document_date_map']([initial]),{})

def test_new_material_writer_uses_an_unambiguous_reference_type(self):
    route = next(node for node in ast.walk(trees.setdefault('app/routes/material.py',
        ast.parse((root/'app/routes/material.py').read_text(encoding='utf-8-sig'))))
        if isinstance(node,ast.FunctionDef) and node.name=='add_material')
    calls = [node for node in ast.walk(route) if isinstance(node,ast.Call)
             and isinstance(node.func,ast.Name) and node.func.id=='apply_opening_balance']
    self.assertEqual(len(calls),1)
    types = [keyword.value.value for keyword in calls[0].keywords
             if keyword.arg=='reference_type' and isinstance(keyword.value,ast.Constant)]
    self.assertEqual(types,['material_initial'])

def test_new_material_reference_has_a_meaningful_label_without_a_false_opening_link(self):
    label,url = ns['_report_reference_info']('material_initial',self.material.id,material_id=self.material.id)
    self.assertIn('物料初始库存',label)
    self.assertIn(self.material.code,label)
    self.assertEqual(url,'')

def test_new_material_origin_survives_the_unchanged_old_cleanup_sql(self):
    line, initial, opening, witness, target = self.collision(audit=False,explicit=True)
    initial_id=initial.id
    self.delete_and_preserve_initial(line,initial,opening,target)
    cleanup=next(node for node in trees['app/app.py'].body if isinstance(node,ast.FunctionDef)
                 and node.name=='cleanup_dangling_opening_stock_transactions')
    statements=[node.args[0].value for node in ast.walk(cleanup) if isinstance(node,ast.Call)
                and isinstance(node.func,ast.Attribute) and node.func.attr=='execute' and node.args
                and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str)
                and node.args[0].value.startswith('DELETE FROM stock_transaction')]
    self.assertEqual(len(statements),1)
    self.assertIn("reference_type = 'opening_stock'",statements[0])
    db.session.execute(text(statements[0]))
    db.session.commit()
    self.assertEqual(db.session.get(ns['StockTransaction'],initial_id).quantity,5)
    self.assertEqual(self.material.stock,5)

def test_same_marker_quantity_actor_and_time_cannot_turn_audit_into_a_source_link(self):
    line, initial, opening, witness, target = self.collision(same_remark=True)
    line.quantity = 5
    target.stock = 10
    opening.quantity = 5
    opening.created_at = initial.created_at
    line.created_at = initial.created_at
    witness.operation_time = initial.created_at
    db.session.commit()
    self.refuse_without_writes(line)

def test_source_rows_are_reloaded_instead_of_trusting_the_identity_map(self):
    line, initial, opening, witness, target = self.collision(stock=0)
    old_remark=opening.remark
    db.session.execute(text('UPDATE stock_transaction SET remark=:remark WHERE id=:id'),
        {'remark':'新增物料初始库存','id':opening.id})
    self.assertEqual(opening.remark,old_remark)
    self.refuse_without_writes(line)

def test_batch_second_ambiguous_line_keeps_first_reversal_uncommitted_until_caller_rollback(self):
    line, initial, opening, witness, target = self.collision(audit=False,explicit=True)
    second = ns['Material'](code='SYN-SECOND',name='合成二',stock=12)
    db.session.add(second)
    db.session.flush()
    next_line = ns['OpeningStock'](material_id=second.id,warehouse_id=self.a.id,quantity=7)
    db.session.add(next_line)
    db.session.flush()
    self.assertEqual(next_line.id,second.id)
    db.session.add_all([
        ns['StockTransaction'](material_id=second.id,warehouse_id=self.a.id,quantity=5,
            transaction_type='opening',reference_type='opening_stock',reference_id=next_line.id,remark='新增物料初始库存'),
        ns['StockTransaction'](material_id=second.id,warehouse_id=self.a.id,quantity=7,
            transaction_type='opening',reference_type='opening_stock',reference_id=next_line.id,remark='期初二'),
    ])
    db.session.commit()
    first_id,second_id=line.id,next_line.id
    original_ids={row.id for row in ns['StockTransaction'].query.all()}
    self.assertEqual(ns['_reverse_opening_stock_line'](line),(True,''))
    self.assertEqual(self.material.stock,5)
    ok,message=ns['_reverse_opening_stock_line'](next_line)
    self.assertFalse(ok)
    self.assertIn('无法安全区分',message)
    self.assertTrue(db.session.connection().connection.driver_connection.in_transaction)
    db.session.rollback()
    self.assertEqual(db.session.get(ns['Material'],target.id).stock,12)
    self.assertEqual(db.session.get(ns['Material'],second.id).stock,12)
    self.assertEqual({row.id for row in ns['StockTransaction'].query.all()},original_ids)
    self.assertIsNotNone(db.session.get(ns['OpeningStock'],first_id))
    self.assertIsNotNone(db.session.get(ns['OpeningStock'],second_id))

def test_two_normal_lines_share_caller_transaction_without_hidden_commit(self):
    line, initial, opening, witness, target = self.collision(audit=False,explicit=True)
    second = ns['Material'](code='SYN-SECOND',name='合成二',stock=7)
    db.session.add(second)
    db.session.flush()
    next_line=ns['OpeningStock'](material_id=second.id,warehouse_id=self.a.id,quantity=7)
    db.session.add(next_line)
    db.session.flush()
    db.session.add(ns['StockTransaction'](material_id=second.id,warehouse_id=self.a.id,quantity=7,
        transaction_type='opening',reference_type='opening_stock',reference_id=next_line.id,remark='期初二'))
    db.session.commit()
    commits=[]
    session=db.session()
    def committed(_session): commits.append(True)
    event.listen(session,'after_commit',committed)
    try:
        self.assertEqual(ns['_reverse_opening_stock_line'](line),(True,''))
        self.assertEqual(ns['_reverse_opening_stock_line'](next_line),(True,''))
        self.assertEqual(commits,[])
        db.session.delete(line)
        db.session.delete(next_line)
        db.session.commit()
        self.assertEqual(commits,[True])
    finally:
        event.remove(session,'after_commit',committed)
    self.assertEqual(target.stock,5)
    self.assertEqual(second.stock,0)
    self.assertEqual(ns['StockTransaction'].query.count(),1)

def test_classification_holds_real_sqlite_write_lock_against_another_memory_connection(self):
    import uuid
    uri='file:wms_owned_reference_'+uuid.uuid4().hex+'?mode=memory&cache=shared'
    keeper=memory_connect(uri,uri=True,timeout=0.01)
    other=memory_connect(uri,uri=True,timeout=0.01)
    original_engine=db.engines[None]
    engine=create_engine('sqlite://',creator=lambda:memory_connect(uri,uri=True,timeout=0.01))
    db.session.remove()
    db.engines[None]=engine
    try:
        db.create_all()
        material=ns['Material'](code='SYN-LOCK',name='合成锁',stock=7)
        warehouse=ns['Warehouse'](code='LOCK',name='合成锁仓')
        db.session.add_all([material,warehouse])
        db.session.flush()
        line=ns['OpeningStock'](material_id=material.id,warehouse_id=warehouse.id,quantity=7)
        db.session.add(line)
        db.session.flush()
        row=ns['StockTransaction'](material_id=material.id,warehouse_id=warehouse.id,quantity=7,
            transaction_type='opening',reference_type='opening_stock',reference_id=line.id,remark='明确期初')
        db.session.add(row)
        db.session.commit()
        ids,error=ns['_opening_stock_line_transaction_ids'](line)
        self.assertEqual((ids,error),([row.id],''))
        statement="INSERT INTO stock_transaction(material_id,transaction_type,quantity,reference_type,reference_id,remark) VALUES(?,'opening',1,'opening_stock',?,'新增物料初始库存')"
        with self.assertRaises(sqlite3.OperationalError) as locked:
            other.execute(statement,(material.id,line.id))
        self.assertIn('locked',str(locked.exception).lower())
        other.rollback()
        db.session.rollback()
        other.execute(statement,(material.id,line.id))
        other.rollback()
    finally:
        db.session.remove()
        db.engines[None]=original_engine
        engine.dispose()
        other.close()
        keeper.close()
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
    if len(count)!=1 or len(methods)!=21 or count[0].comparators[0].value!=9:
        raise AssertionError('Explicit baseline/additional source method lists changed')
    count[0].comparators[0] = ast.Constant(value=30)
    imports = [node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
                 '<guarded-opening-reference-ownership>','exec'),namespace)
    namespace['main']()


def test_reference_ownership_in_explicit_guarded_child():
    env = {key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
                          capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
