"""Historical in/out reversal: real functions/models in guarded fresh memory."""
import ast
import os
from pathlib import Path
import subprocess
import sys


SETUP = r'''
from flask import g, has_request_context, request as actual_request
from sqlalchemy import case
import re
ns.update(g=g,has_request_context=has_request_context,re=re,case=case,LEDGER_EPS=0.01)
ns['current_user'].username='synthetic'
for name in ('resolve_inventory_warehouse_id','add_stock_transaction'):
    extract('app/app.py',name)
extract('app/services/warehouse_stock_service.py','_reverse_recorded_order_stock')
for name in ('_stock_location_from_warehouse','_material_stock_unattributed','_wh_stock_guards',
             'add_stock','deduct_stock_atomic','update_location_inventory','add_location_inventory_atomic',
             'deduct_location_inventory_atomic','_active_in_order_push_lines','_source_has_active_push',
             '_acquire_order_write_lock','_purchase_returned_quantity_by_source_item',
             '_sales_returned_quantity_by_source_item','sync_sales_order_shipment','log_audit'):
    extract('app/app.py',name)
extract('app/utils.py','is_stock_sufficient')
for name in ('three_ledger_guard_enabled','three_ledger_guard_strict','verify_material_three_ledgers',
             'guard_three_ledgers','apply_stock_delta'):
    extract('app/services/warehouse_stock_service.py',name)
for name in ('sales_outbound_revert_check','purchase_inbound_revert_check'):
    extract('app/services/document_return_guard.py',name)
extract('app/services/warehouse_identity.py','resolve_warehouse_text')
for name in ('revert_in_order','batch_revert_in_order'):
    extract('app/routes/in_order.py',name)
extract('app/routes/out_order.py','revert_out_order')
'''

CASES = r'''
def recorded_order(self, kind='in', *, location_on=False, quantities=None, recorded=None):
    quantities = [1.005] if quantities is None else quantities
    sign = 1 if kind=='in' else -1
    ns['location_management_enabled'] = lambda: location_on
    ns['allow_negative_stock'] = lambda: False
    ns['allow_negative_location_stock'] = lambda: False
    cls,item_cls,key = (ns['InOrder'],ns['InOrderItem'],'in_order_id') if kind=='in' else (
        ns['OutOrder'],ns['OutOrderItem'],'out_order_id')
    order=cls(order_no='SYN-HIST-'+kind,warehouse=self.a.name,location='SAME',status='completed')
    db.session.add(order)
    db.session.flush()
    for quantity in quantities:
        db.session.add(item_cls(**{key:order.id,'material_id':self.material.id,
            'quantity':quantity,'price':0,'amount':0}))
    values=[sign*value for value in quantities] if recorded is None else recorded
    original=[]
    for value in values:
        row=self.txn(self.a.id,value,kind+'_order',order.id)
        row.transaction_type=('in' if value>=0 else 'revert_in') if kind=='in' else (
            'out' if value<=0 else 'revert_out')
        row.location=self.a.name
        original.append(row)
    self.txn(self.a.id,10,'material_initial',self.material.id)
    self.txn(self.b.id,10,'material_initial',self.material.id)
    self.material.stock=20+math.fsum(values)
    if location_on:
        db.session.add_all([
            ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,
                location='SAME',quantity=10+math.fsum(values)),
            ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.b.id,
                location='SAME',quantity=10)])
    db.session.commit()
    return order,original

def order_snapshot(self):
    return (self.material.stock,
        [(row.id,row.quantity,row.reference_type,row.reference_id,row.warehouse_id)
         for row in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)],
        [(row.id,row.quantity) for row in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)])

def order_success(self,order,original):
    original_ids=[row.id for row in original]
    self.assertEqual(ns['_reverse_recorded_order_stock'](order),(True,''))
    db.session.commit()
    self.assertAlmostEqual(self.material.stock,20,places=12)
    for row_id in original_ids:
        self.assertIsNotNone(db.session.get(ns['StockTransaction'],row_id))
    self.assertAlmostEqual(math.fsum(row.quantity for row in ns['StockTransaction'].query),20,places=12)
    if ns['location_management_enabled']():
        self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity,10,places=12)
        self.assertEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity,10)

def order_refusal(self,order,expected):
    before=self.order_snapshot()
    result=ns['_reverse_recorded_order_stock'](order)
    self.assertIsNotNone(result)
    self.assertFalse(result[0],result)
    self.assertIn(expected,result[1])
    self.assertEqual(self.order_snapshot(),before)
    db.session.rollback()

def test_raw_quantity_api_does_not_accept_client_delta_or_precision_switch(self):
    import inspect
    self.assertEqual(list(inspect.signature(ns['_reverse_recorded_order_stock']).parameters),['order'])

def test_unknown_history_keeps_normal_two_decimal_compatibility_path(self):
    order,original=self.recorded_order(quantities=[1.01])
    original[0].warehouse_id=None
    original[0].location=''
    db.session.commit()
    before=self.order_snapshot()
    self.assertIsNone(ns['_reverse_recorded_order_stock'](order))
    self.assertEqual(self.order_snapshot(),before)

def test_current_known_location_cannot_replace_missing_original_position(self):
    order,original=self.recorded_order(location_on=True)
    order.location=''
    original[0].location=''
    db.session.commit()
    self.order_refusal(order,'原库位缺失')

def test_float_point_one_and_point_two_use_normal_compatible_path(self):
    order,original=self.recorded_order(quantities=[0.1,0.2])
    before=self.order_snapshot()
    self.assertIsNone(ns['_reverse_recorded_order_stock'](order))
    self.assertEqual(self.order_snapshot(),before)

def route_result(self,kind,order,batch=False):
    route=ns['batch_revert_in_order'] if batch else ns['revert_'+kind+'_order']
    with app.test_request_context('/synthetic-only',method='POST',json={'ids':[order.id]}):
        with patch.dict(ns,request=actual_request):
            result=route() if batch else route(order.id)
    result=result[0] if isinstance(result,tuple) else result
    return result.get_json() if hasattr(result,'get_json') else result

def test_route_inbound_does_not_release_purchase_received_reservation(self):
    order,_=self.recorded_order(location_on=True)
    po=ns['PurchaseOrder'](order_no='SYN-RESERVED')
    db.session.add(po)
    db.session.flush()
    source=ns['PurchaseOrderItem'](purchase_order_id=po.id,material_id=self.material.id,
        quantity=10,received_quantity=1.005,price=0,amount=0)
    db.session.add(source)
    db.session.flush()
    order.items[0].source_purchase_order_item_id=source.id
    db.session.commit()
    payload=self.route_result('in',order)
    self.assertEqual(payload['status'],'success',payload)
    self.assertAlmostEqual(source.received_quantity,1.005,places=12)
    self.assertEqual(order.status,'pending')

def test_route_inbound_completed_purchase_return_still_blocks_raw_inverse(self):
    order,_=self.recorded_order()
    returned=ns['OutOrder'](order_no='SYN-RETURN',business_type='采购退货出库',status='completed',warehouse=self.a.name)
    db.session.add(returned)
    db.session.flush()
    db.session.add(ns['OutOrderItem'](out_order_id=returned.id,material_id=self.material.id,
        source_in_order_item_id=order.items[0].id,quantity=0.5,price=0,amount=0))
    db.session.commit()
    before=self.order_snapshot()
    payload=self.route_result('in',order)
    self.assertEqual(payload['status'],'error',payload)
    self.assertIn('已完成采购退货',payload['msg'])
    self.assertEqual(self.order_snapshot(),before)

def test_outbound_inverse_can_improve_a_still_negative_original_bin(self):
    order,_=self.recorded_order('out',location_on=True)
    self.txn(self.a.id,-15,'synthetic-consumption',99)
    self.material.stock=3.995
    ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=-6.005
    db.session.commit()
    self.assertEqual(ns['_reverse_recorded_order_stock'](order),(True,''))
    db.session.commit()
    self.assertAlmostEqual(self.material.stock,5,places=12)
    self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity,-5,places=12)

def physical_zero_scene(self,extra_active=False,location_on=True):
    quantity=1.005 if extra_active else 0
    order,original=self.recorded_order('in',location_on=location_on,quantities=[quantity],
        recorded=[quantity] if extra_active else [1.005,-1.005])
    warehouse=self.b if extra_active else self.a
    if extra_active:
        for quantity,typ in ((1.005,'in'),(-1.005,'adjust_in_item')):
            row=self.txn(warehouse.id,quantity,'in_order',order.id)
            row.transaction_type=typ
            row.location=warehouse.name
    else:
        original[1].transaction_type='adjust_in_item'
    if location_on:
        db.session.add_all([
            ns['LocationInventory'](material_id=self.material.id,warehouse_id=warehouse.id,location='HIST-POS',quantity=1.005),
            ns['LocationInventory'](material_id=self.material.id,warehouse_id=warehouse.id,location='HIST-NEG',quantity=-1.005)])
    db.session.commit()
    return order

def test_current_zero_net_cannot_hide_opposite_physical_bin_balances(self):
    self.order_refusal(self.physical_zero_scene(),'净零')

def test_other_zero_net_warehouse_cannot_be_skipped_beside_an_active_warehouse(self):
    self.order_refusal(self.physical_zero_scene(extra_active=True),'净零')

def test_closed_zero_net_warehouse_cannot_hide_opposite_physical_bins_before_an_active_cycle(self):
    order,original=self.recorded_order('in',location_on=True)
    db.session.delete(original[0])
    db.session.flush()
    for warehouse,quantity,typ in ((self.b,1.005,'in'),(self.b,-1.005,'revert_in'),(self.a,1.005,'in')):
        row=self.txn(warehouse.id,quantity,'in_order',order.id)
        row.transaction_type=typ
        row.location=warehouse.name
    db.session.add_all([
        ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.b.id,location='CLOSED-POS',quantity=1.005),
        ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.b.id,location='CLOSED-NEG',quantity=-1.005)])
    db.session.commit()
    self.order_refusal(order,'闭合历史')

def test_closed_same_warehouse_cannot_borrow_current_header_as_old_physical_proof(self):
    order,_=self.recorded_order('in',location_on=True,recorded=[1.005,-1.005,1.005])
    db.session.add_all([
        ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,location='CLOSED-POS',quantity=1.005),
        ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,location='CLOSED-NEG',quantity=-1.005)])
    db.session.commit()
    self.order_refusal(order,'闭合历史')

def test_normal_all_two_decimal_records_keep_the_original_early_path_with_locations(self):
    order,_=self.recorded_order('in',location_on=True,quantities=[1.01],recorded=[1.01,-1.01,1.01])
    before=self.order_snapshot()
    self.assertIsNone(ns['_reverse_recorded_order_stock'](order))
    self.assertEqual(self.order_snapshot(),before)

def test_each_closed_record_is_literal_zero_so_no_unknown_position_can_have_a_delta(self):
    order,original=self.recorded_order('in',location_on=True,recorded=[0,0,1.005])
    original[1].transaction_type='revert_in'
    db.session.commit()
    self.order_success(order,original)

def test_zero_net_without_location_management_does_not_allocate_a_physical_bin(self):
    order=self.physical_zero_scene(location_on=False)
    before=self.order_snapshot()
    self.assertEqual(ns['_reverse_recorded_order_stock'](order),(True,''))
    self.assertEqual(self.order_snapshot(),before)

def test_historical_normalized_inbound_wrong_header_cannot_return_to_old_warehouse(self):
    order,_=self.recorded_order('in',location_on=True,recorded=[1.01])
    order.warehouse=self.b.name
    db.session.commit()
    self.order_refusal(order,'头仓库与原流水')

def test_historical_normalized_outbound_wrong_header_cannot_return_to_old_warehouse(self):
    order,_=self.recorded_order('out',location_on=True,recorded=[-1.01])
    order.warehouse=self.b.name
    db.session.commit()
    self.order_refusal(order,'头仓库与原流水')

def test_header_code_alias_cannot_redirect_empty_location_from_original_placeholder(self):
    order,_=self.recorded_order('in',location_on=True,recorded=[1.01])
    order.warehouse=self.a.code
    order.location=''
    ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().location=self.a.name
    db.session.commit()
    self.order_success(order,ns['StockTransaction'].query.filter_by(reference_type='in_order',reference_id=order.id).all())

def test_renamed_unresolved_header_uses_recorded_id_without_returning_to_old_text_path(self):
    order,_=self.recorded_order('in',location_on=True,recorded=[1.01])
    self.a.name='RENAMED-SYN-A'
    db.session.commit()
    self.order_success(order,ns['StockTransaction'].query.filter_by(reference_type='in_order',reference_id=order.id).all())
'''

WRONG_HEADER_ROUTE=r'''
def test_real_wrong_header_{name}(self):
    kind={kind!r}
    order,_=self.recorded_order(kind,location_on={location_on},recorded=[1.01 if kind=='in' else -1.01])
    order.warehouse=self.b.name
    db.session.commit()
    before=self.order_snapshot()
    payload=self.route_result(kind,order,batch={batch})
    if {batch}:
        self.assertEqual(payload['status'],'success',payload)
        self.assertEqual(payload['reverted'],0,payload)
    else:
        self.assertEqual(payload['status'],'error',payload)
    self.assertIn('头仓库与原流水',payload['msg'])
    self.assertEqual(self.order_snapshot(),before)
    self.assertEqual(order.status,'completed')
'''

ROUTE_CASE = r'''
def test_real_route_{name}(self):
    kind={kind!r}
    mode={mode!r}
    sign=1 if kind=='in' else -1
    quantities=[1.005,1.005] if mode in ('aggregate_raw','per_line_normalized') else [1.005]
    values=None
    if mode=='historical_normalized':
        values=[sign*1.01]
    elif mode=='aggregate_raw':
        values=[sign*2.01]
    elif mode=='per_line_normalized':
        values=[sign*1.01,sign*1.01]
    order,_=self.recorded_order(kind,location_on={location_on},quantities=quantities,recorded=values)
    payload=self.route_result(kind,order,batch={batch})
    self.assertEqual(payload['status'],'success',payload)
    if {batch}:
        self.assertEqual(payload['reverted'],1,payload)
    self.assertEqual(order.status,'pending')
    self.assertAlmostEqual(self.material.stock,20,places=12)
    self.assertAlmostEqual(math.fsum(row.quantity for row in ns['StockTransaction'].query),20,places=12)
    if {location_on}:
        self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity,10,places=12)
        self.assertEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity,10)
'''

PARAMETERIZED = r'''
def test_{name}(self):
    kind={kind!r}
    sign=1 if kind=='in' else -1
    location_on={location_on}
    mode={mode!r}
    if mode=='raw':
        order,original=self.recorded_order(kind,location_on=location_on)
        self.order_success(order,original)
    elif mode=='historical_normalized':
        order,_=self.recorded_order(kind,location_on=location_on,recorded=[sign*1.01])
        before=self.order_snapshot()
        self.assertIsNone(ns['_reverse_recorded_order_stock'](order))
        self.assertEqual(self.order_snapshot(),before)
    elif mode=='per_line_normalized':
        order,_=self.recorded_order(kind,location_on=location_on,quantities=[1.005,1.005],
            recorded=[sign*1.01,sign*1.01])
        before=self.order_snapshot()
        self.assertIsNone(ns['_reverse_recorded_order_stock'](order))
        self.assertEqual(self.order_snapshot(),before)
    elif mode=='aggregate_raw':
        order,original=self.recorded_order(kind,location_on=location_on,quantities=[1.005,1.005],
            recorded=[sign*2.01])
        self.order_success(order,original)
    elif mode=='mismatch':
        order,_=self.recorded_order(kind,location_on=location_on,recorded=[sign*1.02])
        self.order_refusal(order,'净额不一致')
    elif mode=='prior_signed_cycles':
        order,original=self.recorded_order(kind,location_on=location_on,
            recorded=[sign*2.005,-sign*2.005,sign*1.005])
        if location_on:
            self.order_refusal(order,'闭合历史')
        else:
            self.order_success(order,original)
    elif mode=='ordinary':
        order,_=self.recorded_order(kind,location_on=location_on,quantities=[1.01])
        before=self.order_snapshot()
        self.assertIsNone(ns['_reverse_recorded_order_stock'](order))
        self.assertEqual(self.order_snapshot(),before)
    elif mode=='rollback':
        order,_=self.recorded_order(kind,location_on=location_on)
        before=self.order_snapshot()
        self.assertEqual(ns['_reverse_recorded_order_stock'](order),(True,''))
        db.session.rollback()
        self.assertEqual(self.order_snapshot(),before)
    elif mode=='repeat':
        order,_=self.recorded_order(kind,location_on=location_on)
        self.assertEqual(ns['_reverse_recorded_order_stock'](order),(True,''))
        db.session.commit()
        self.order_refusal(order,'净额不一致')
    elif mode=='unknown':
        order,original=self.recorded_order(kind,location_on=location_on)
        original[0].warehouse_id=None
        db.session.commit()
        self.order_refusal(order,'原仓归属缺失或冲突')
    elif mode=='location_difference':
        order,_=self.recorded_order(kind,location_on=True)
        ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity += 0.005
        db.session.commit()
        self.order_refusal(order,'原仓库位账与流水不一致')
    elif mode=='source_and_bin_normalized_differently':
        order,_=self.recorded_order(kind,location_on=True,recorded=[sign*1.01])
        ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=10+sign*1.005
        db.session.commit()
        self.order_refusal(order,'原仓库位账与流水不一致')
    elif mode=='closed_cycle_residue_cannot_cancel_current_normalized_quantity':
        order,original=self.recorded_order(kind,location_on=True,
            recorded=[sign*1.005,-sign*1.01,sign*1.01])
        ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=10+sign*1.01
        db.session.add(ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,
            location='OLD-BIN',quantity=-sign*0.005))
        db.session.commit()
        self.order_refusal(order,'此前完成周期未准确回退')
    elif mode=='closed_raw_cycle_current_normalized_uses_original_path':
        order,_=self.recorded_order(kind,location_on=location_on,
            recorded=[sign*2.005,-sign*2.005,sign*1.01])
        before=self.order_snapshot()
        if location_on:
            result=ns['_reverse_recorded_order_stock'](order)
            self.assertIsNotNone(result)
            self.assertFalse(result[0],result)
            self.assertIn('闭合历史',result[1])
        else:
            self.assertIsNone(ns['_reverse_recorded_order_stock'](order))
        self.assertEqual(self.order_snapshot(),before)
    elif mode=='unproven_phase':
        order,original=self.recorded_order(kind,location_on=location_on)
        original[0].transaction_type='unproven-phase'
        db.session.commit()
        self.order_refusal(order,'流水阶段无法证明')
    elif mode=='tiny_no_effect':
        order,_=self.recorded_order(kind,quantities=[1e-20])
        self.order_refusal(order,'Float可逆精度')
    elif mode=='route_location_dml_failure':
        order,_=self.recorded_order(kind,location_on=True)
        before=self.order_snapshot()
        hit=[]
        def fail_location(_connection,_cursor,statement,_parameters,_context,_executemany):
            if statement.lstrip().upper().startswith('UPDATE LOCATION_INVENTORY'):
                hit.append(True)
                raise RuntimeError('owned synthetic order location DML failure')
        event.listen(db.engine,'before_cursor_execute',fail_location)
        try:
            payload=self.route_result(kind,order)
        finally:
            event.remove(db.engine,'before_cursor_execute',fail_location)
        self.assertEqual(hit,[True])
        self.assertEqual(payload['status'],'error',payload)
        self.assertEqual(self.order_snapshot(),before)
        self.assertEqual(order.status,'completed')
    else:
        raise AssertionError('Unknown explicit scenario')
'''


def main():
    harness=Path(__file__).with_name('verify_audit_real_models_20261113.py')
    tree=ast.parse(harness.read_text(encoding='utf-8-sig'))
    original=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    for node in ast.walk(original):
        if (isinstance(node,ast.Tuple) and all(isinstance(value,ast.Constant) for value in node.elts)
                and 'services.warehouse_stock_service' in [value.value for value in node.elts]):
            node.elts.extend(ast.Constant(value=name) for name in
                             ('services.document_return_guard','services.warehouse_identity'))
    suite=next(node for node in original.body if isinstance(node,ast.ClassDef) and node.name=='RealModelBoundaries')
    original.body[original.body.index(suite):original.body.index(suite)]=ast.parse(SETUP).body
    extra=ast.parse(CASES).body
    for kind in ('in','out'):
        for location_on in (False,True):
            for mode in ('raw','historical_normalized','per_line_normalized','aggregate_raw','mismatch',
                         'prior_signed_cycles','ordinary','rollback','repeat','unknown',
                         'closed_raw_cycle_current_normalized_uses_original_path','unproven_phase'):
                name=kind+'_'+mode+('_on' if location_on else '_off')
                extra.extend(ast.parse(PARAMETERIZED.format(name=name,kind=kind,
                    location_on=location_on,mode=mode)).body)
        for mode in ('location_difference','source_and_bin_normalized_differently',
                     'closed_cycle_residue_cannot_cancel_current_normalized_quantity',
                     'tiny_no_effect','route_location_dml_failure'):
            extra.extend(ast.parse(PARAMETERIZED.format(name=kind+'_'+mode,kind=kind,
                location_on=True,mode=mode)).body)
    for kind,batch in (('in',False),('in',True),('out',False)):
        for location_on in (False,True):
            name=kind+('_batch' if batch else '_single')+('_on' if location_on else '_off')
            extra.extend(ast.parse(WRONG_HEADER_ROUTE.format(name=name,kind=kind,batch=batch,
                location_on=location_on)).body)
            for mode in ('raw','historical_normalized','aggregate_raw','per_line_normalized'):
                name=kind+('_batch_' if batch else '_single_')+mode+('_on' if location_on else '_off')
                extra.extend(ast.parse(ROUTE_CASE.format(name=name,kind=kind,batch=batch,
                    location_on=location_on,mode=mode)).body)
    suite.body.extend(extra)
    methods=[node for node in extra if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')]
    counts=[node for node in ast.walk(original) if isinstance(node,ast.Compare) and isinstance(node.left,ast.Call)
            and isinstance(node.left.func,ast.Attribute) and node.left.func.attr=='countTestCases']
    if len(methods)!=106 or len(counts)!=1 or counts[0].comparators[0].value!=9:
        raise AssertionError('Explicit historical order list changed or became empty')
    counts[0].comparators[0]=ast.Constant(value=115)
    imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
                 '<guarded-recorded-order-quantity>','exec'),namespace)
    namespace['main']()


def test_recorded_order_in_guarded_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
                          capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
