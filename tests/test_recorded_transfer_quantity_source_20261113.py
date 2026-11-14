"""Actual transfer/model bodies in the existing owned-memory source harness.

No WMS application import, SQLite file, network or child is permitted inside
the worker. Full application routes remain a separate Linux CI acceptance.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys


SETUP = r'''
from flask import g, has_request_context
from sqlalchemy import case
ns.update(case=case,g=g,has_request_context=has_request_context)
ns['current_user'].username='synthetic'
for name in ('resolve_inventory_warehouse_id','add_stock_transaction','_stock_location_from_warehouse',
             'update_location_inventory','add_location_inventory_atomic','deduct_location_inventory_atomic',
             '_acquire_order_write_lock','log_audit','is_warehouse_active','assert_warehouse_active'):
    extract('app/app.py',name)
extract('app/services/warehouse_identity.py','resolve_warehouse_text')
for name in ('_transfer_quantity_net','apply_transfer_pair','_recorded_transfer_phases','_check_recorded_transfer_completion','_reverse_recorded_transfer_stock'):
    extract('app/services/warehouse_stock_service.py',name)
for name in ('complete_transfer','revert_transfer'):
    extract('app/routes/transfer.py',name)
'''


CASES = r'''
def transfer_seed(self,location_on,quantities=None,recorded=None,same_warehouse=False):
    quantities=[1.005] if quantities is None else quantities
    recorded=list(quantities) if recorded is None else recorded
    ns['location_management_enabled']=lambda:location_on
    ns['allow_negative_stock']=lambda:False
    ns['allow_negative_location_stock']=lambda:False
    target=self.a if same_warehouse else self.b
    source_bin='LEFT' if same_warehouse else 'SAME'
    target_bin='RIGHT' if same_warehouse else 'SAME'
    transfer=ns['TransferOrder'](transfer_no='SYN-T',from_warehouse=self.a.name,to_warehouse=target.name,
        from_location=source_bin,to_location=target_bin,status='completed')
    db.session.add(transfer);db.session.flush()
    for qty in quantities:
        db.session.add(ns['TransferOrderItem'](transfer_order_id=transfer.id,material_id=self.material.id,
            quantity=qty,price=0,amount=0))
    self.txn(self.a.id,10,'material_initial',self.material.id)
    self.txn(target.id,10,'material_initial',self.material.id)
    original=[]
    for qty in recorded:
        original.extend(self.transfer_pair(transfer,qty,self.a,target,source_bin,target_bin))
    self.material.stock=20
    if location_on:
        db.session.add_all([ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,
            location=source_bin,quantity=10-math.fsum(recorded)),
            ns['LocationInventory'](material_id=self.material.id,warehouse_id=target.id,
            location=target_bin,quantity=10+math.fsum(recorded))])
    db.session.commit()
    return transfer,original

def transfer_pair(self,transfer,qty,source,target,source_bin='SAME',target_bin='SAME'):
    outgoing=self.txn(source.id,-qty,'transfer',transfer.id)
    incoming=self.txn(target.id,qty,'transfer',transfer.id)
    outgoing.transaction_type='transfer_out';incoming.transaction_type='transfer_in'
    outgoing.location=source_bin;incoming.location=target_bin
    db.session.flush()
    return outgoing,incoming

def transfer_snapshot(self):
    return (self.material.stock,
        [(row.id,row.quantity,row.warehouse_id,row.location,row.transaction_type)
         for row in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)],
        [(row.id,row.quantity) for row in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)],
        [(row.id,row.status,row.from_warehouse,row.to_warehouse,row.from_location,row.to_location,row.remark)
         for row in ns['TransferOrder'].query.order_by(ns['TransferOrder'].id)],
        [(row.id,row.material_id,row.quantity,row.price,row.amount,row.remark)
         for row in ns['TransferOrderItem'].query.order_by(ns['TransferOrderItem'].id)],
        [[tuple(getattr(row,column.name) for column in ns[name].__table__.columns)
          for row in ns[name].query.order_by(ns[name].id)]
         for name in ('Material','StockTransaction','LocationInventory','TransferOrder',
                      'TransferOrderItem','OperationLog','OperationAudit')])

def transfer_route(self,name,transfer):
    with app.test_request_context('/owned-synthetic-route',method='POST'):
        value=ns[name](transfer.id)
    value=value[0] if isinstance(value,tuple) else value
    return value.get_json() if hasattr(value,'get_json') else value

def transfer_assert_restored(self):
    self.assertEqual(self.material.stock,20)
    self.assertAlmostEqual(math.fsum(row.quantity for row in ns['StockTransaction'].query),20,places=12)
    if ns['location_management_enabled']():
        for row in ns['LocationInventory'].query:
            self.assertAlmostEqual(row.quantity,10,places=12)
    by_source={}
    for row in ns['StockTransaction'].query.filter_by(reference_type='transfer'):
        key=(row.material_id,row.warehouse_id,row.location if ns['location_management_enabled']() else '')
        by_source.setdefault(key,[]).append(row.quantity)
    for key,values in by_source.items():
        self.assertAlmostEqual(math.fsum(values),0,places=12,msg=str(key))

def test_decimal_net_preserves_raw_quantities_and_exact_cancellation(self):
    total=ns['_transfer_quantity_net']
    self.assertEqual(total([0.1,0.2,-0.3]),0)
    self.assertEqual(total([1.005,0.335]),1.34)
    self.assertEqual(total([1e12,1.005,-1e12]),1.005)

def test_private_reverse_has_no_caller_quantity_or_precision_switch(self):
    import inspect
    self.assertEqual(list(inspect.signature(ns['_reverse_recorded_transfer_stock']).parameters),['transfer'])

def transfer_case(self,mode,location_on):
    if mode.startswith('new_'):
        quantity={'new_raw':1.005,'new_down':1.004,'new_tiny':0.004,'new_ordinary':2.25}[mode]
        ns['location_management_enabled']=lambda:location_on
        ns['allow_negative_location_stock']=lambda:False
        self.material.stock=20
        self.txn(self.a.id,10,'material_initial',self.material.id)
        self.txn(self.b.id,10,'material_initial',self.material.id)
        if location_on:
            db.session.add_all([ns['LocationInventory'](material_id=self.material.id,warehouse_id=wh.id,
                location='SAME',quantity=10) for wh in (self.a,self.b)])
        db.session.commit()
        expected=ns['normalize_stock_quantity'](quantity)
        self.assertEqual(ns['apply_transfer_pair'](self.material,quantity,from_warehouse=self.a,to_warehouse=self.b,
            from_location='SAME',to_location='SAME',reference_id=19),(True,''))
        db.session.commit()
        rows=ns['StockTransaction'].query.filter_by(reference_type='transfer',reference_id=19).order_by(ns['StockTransaction'].id).all()
        self.assertEqual([row.quantity for row in rows],[-expected,expected] if expected else [])
        self.assertEqual(self.material.stock,20)
        if location_on:
            self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity,10-expected,places=12)
            self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity,10+expected,places=12)
        return
    recorded=[1.01] if mode in ('historical_normalized','cycle_same_warehouse') else ([1.01,0.34] if mode=='normalized_perline' else None)
    quantities=[1.005,0.335] if mode in ('duplicates','normalized_perline') else None
    if mode=='tiny_cycle':quantities,recorded=[0.004],[]
    transfer,rows=self.transfer_seed(location_on,quantities,recorded,
        same_warehouse=mode in ('same_warehouse','same_warehouse_physical_normalized','cycle_same_warehouse'))
    if mode in ('same_warehouse','same_warehouse_physical_normalized'):
        if mode=='same_warehouse_physical_normalized':
            ns['LocationInventory'].query.filter_by(location='LEFT').one().quantity=8.99
            ns['LocationInventory'].query.filter_by(location='RIGHT').one().quantity=11.01
            db.session.commit()
        before=self.transfer_snapshot()
        response=self.transfer_route('revert_transfer',transfer)
        self.assertEqual(response['status'],'error',response)
        self.assertIn('逐库位原数量落账证明',response['msg'])
        self.assertEqual(self.transfer_snapshot(),before)
        return
    if location_on and mode in ('raw','duplicates','cycle'):
        before=self.transfer_snapshot()
        payload=self.transfer_route('revert_transfer',transfer)
        self.assertEqual(payload['status'],'error',payload)
        self.assertIn('逐库位原数量落账证明',payload['msg'])
        self.assertEqual(self.transfer_snapshot(),before)
        return
    if location_on and (mode.startswith('post_cycle_') or mode in ('negative_allowed','rollback')):
        # Keep successful controls reachable through certified normalized legs.
        for row in rows:row.quantity=1.01 if row.quantity>0 else -1.01
        for wh,value in ((self.a,8.99),(self.b,11.01)):
            ns['LocationInventory'].query.filter_by(warehouse_id=wh.id).one().quantity=value
        if mode.startswith('post_cycle_'):
            for row in rows:db.session.delete(row)
            db.session.flush()
            self.transfer_pair(transfer,0.335,self.a,self.b)
            self.transfer_pair(transfer,0.335,self.b,self.a)
            rows=list(self.transfer_pair(transfer,1.01,self.a,self.b))
        db.session.commit()
    if mode=='tiny_cycle':
        transfer.status='pending';db.session.commit()
        for _ in range(2):
            self.assertEqual(self.transfer_route('complete_transfer',transfer)['status'],'success')
            self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'success')
        self.assertEqual(ns['StockTransaction'].query.filter_by(reference_type='transfer').count(),0)
        self.transfer_assert_restored()
        return
    if mode.startswith('post_cycle_'):
        self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'success')
        if mode=='post_cycle_ambiguous':
            transfer.from_warehouse,transfer.to_warehouse=transfer.to_warehouse,transfer.from_warehouse
            transfer.from_location,transfer.to_location=transfer.to_location,transfer.from_location
            db.session.commit()
            before=self.transfer_snapshot()
            payload=self.transfer_route('complete_transfer',transfer)
            self.assertEqual(payload['status'],'error',payload)
            self.assertIn('无法区分',payload['msg'])
            self.assertEqual(self.transfer_snapshot(),before)
        elif mode=='post_cycle_changed_bins':
            transfer.to_location='OTHER'
            if location_on:
                db.session.add(ns['LocationInventory'](material_id=self.material.id,
                    warehouse_id=self.b.id,location='OTHER',quantity=0))
            db.session.commit()
            self.assertEqual(self.transfer_route('complete_transfer',transfer)['status'],'success')
            self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'success')
            if location_on:
                self.assertEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id,location='OTHER').one().quantity,0)
        elif mode=='post_cycle_changed_warehouse':
            c=ns['Warehouse'](code='SYN-C',name='合成丙仓',status='active')
            db.session.add(c);db.session.flush();self.txn(c.id,10,'material_initial',self.material.id)
            self.material.stock=30;transfer.to_warehouse=c.name
            if location_on:
                db.session.add(ns['LocationInventory'](material_id=self.material.id,
                    warehouse_id=c.id,location='SAME',quantity=10))
            db.session.commit()
            self.assertEqual(self.transfer_route('complete_transfer',transfer)['status'],'success')
            self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'success')
            self.assertEqual(self.material.stock,30)
            self.assertEqual(ns['get_warehouse_stock_quantities'](c)[self.material.id],10)
            if location_on:
                for row in ns['LocationInventory'].query:self.assertAlmostEqual(row.quantity,10,places=12)
        else:raise AssertionError(mode)
        for warehouse in (self.a,self.b):
            self.assertAlmostEqual(ns['get_warehouse_stock_quantities'](warehouse)[self.material.id],10,places=12)
        return
    if mode in ('raw','duplicates','same_warehouse','historical_normalized','cycle','cycle_same_warehouse','normalized_perline'):
        payload=self.transfer_route('revert_transfer',transfer)
        self.assertEqual(payload['status'],'success',payload)
        self.assertEqual(transfer.status,'pending')
        self.transfer_assert_restored()
        self.assertEqual(ns['get_warehouse_stock_quantities'](self.a)[self.material.id],20 if mode in ('same_warehouse','cycle_same_warehouse') else 10)
        before=self.transfer_snapshot()
        self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'error')
        self.assertEqual(self.transfer_snapshot(),before)
        if mode in ('cycle','cycle_same_warehouse'):
            for _ in range(2):
                self.assertEqual(self.transfer_route('complete_transfer',transfer)['status'],'success')
                self.assertEqual(transfer.status,'completed')
                self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'success')
                self.transfer_assert_restored()
        return
    if mode=='ordinary':
        for item in transfer.items:item.quantity=1.01
        for row in rows:row.quantity=1.01 if row.quantity>0 else -1.01
        db.session.commit()
        before=self.transfer_snapshot()
        self.assertIsNone(ns['_reverse_recorded_transfer_stock'](transfer))
        self.assertEqual(self.transfer_snapshot(),before)
        return
    if mode.startswith('closed_'):
        # Put a fully paired old cycle before the current one, without using
        # remark, date or type as a reversal sentinel.
        for row in rows:db.session.delete(row)
        db.session.flush()
        if mode=='closed_per_line_residue':
            self.transfer_pair(transfer,1.005,self.a,self.b)
            a,b=self.transfer_pair(transfer,1.005,self.a,self.b)
            c,d=self.transfer_pair(transfer,2.01,self.b,self.a)
        else:
            a,b=self.transfer_pair(transfer,0.335,self.a,self.b)
            c,d=self.transfer_pair(transfer,0.335 if mode!='closed_residue' else 0.34,self.b,self.a)
        if mode=='closed_missing_position':a.location=''
        rows=list(self.transfer_pair(transfer,1.01 if location_on and mode=='closed_proven' else 1.005,self.a,self.b))
        if location_on and mode=='closed_proven':
            for wh,value in ((self.a,8.99),(self.b,11.01)):
                ns['LocationInventory'].query.filter_by(warehouse_id=wh.id).one().quantity=value
        if mode=='closed_other_bin':c.location='OTHER'
        db.session.commit()
        if mode=='closed_proven':
            self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'success')
            self.transfer_assert_restored()
            return
    elif mode=='unknown':rows[0].warehouse_id=None
    elif mode=='bad_type':rows[0].transaction_type='revert_transfer'
    elif mode=='missing_leg':db.session.delete(rows[-1])
    elif mode=='different_pair':rows[-1].quantity=1.004
    elif mode=='current_missing_position':rows[0].location=''
    elif mode=='current_wrong_position':rows[-1].location='OTHER'
    elif mode=='physical_normalized':
        ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=8.99
        ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity=11.01
    elif mode=='insufficient':
        self.txn(self.b.id,-11,'synthetic-used',0)
        self.material.stock=9
        if location_on:ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity=0.005
    elif mode=='negative_allowed':
        self.txn(self.b.id,-11,'synthetic-used',0)
        self.material.stock=9
        ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity=0.01
        ns['allow_negative_location_stock']=lambda:True
        db.session.commit()
        self.assertEqual(self.transfer_route('revert_transfer',transfer)['status'],'success')
        self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity,-1,places=12)
        self.assertEqual(self.material.stock,9)
        return
    elif mode=='rollback':
        db.session.commit()
        before=self.transfer_snapshot();hits=[]
        def fail_second_location(_connection,_cursor,statement,_params,_context,_many):
            if statement.lstrip().upper().startswith('UPDATE LOCATION_INVENTORY'):
                hits.append(True)
                if len(hits)==2:raise RuntimeError('owned transfer second-leg failure')
        event.listen(db.engine,'before_cursor_execute',fail_second_location)
        try:payload=self.transfer_route('revert_transfer',transfer)
        finally:event.remove(db.engine,'before_cursor_execute',fail_second_location)
        self.assertEqual(hits,[True,True])
        self.assertEqual(payload['status'],'error',payload)
        self.assertEqual(self.transfer_snapshot(),before)
        self.assertEqual(transfer.status,'completed')
        return
    else:raise AssertionError('Unknown explicit scenario '+mode)
    db.session.commit()
    before=self.transfer_snapshot()
    payload=self.transfer_route('revert_transfer',transfer)
    self.assertEqual(payload['status'],'error',(mode,payload))
    self.assertEqual(self.transfer_snapshot(),before)
    self.assertEqual(transfer.status,'completed')
def compensation_case(self,quantity,reverse):
    ns['location_management_enabled']=lambda:True
    source,target=(self.b,self.a) if reverse else (self.a,self.b)
    transfer=ns['TransferOrder'](transfer_no='SYN-T',from_warehouse=source.name,to_warehouse=target.name,
        from_location='SAME',to_location='SAME',status='completed',remark='原备注')
    other=ns['TransferOrder'](transfer_no='SYN-OTHER',from_warehouse=target.name,to_warehouse=source.name,
        from_location='OTHER',to_location='OTHER',status='completed')
    db.session.add_all([transfer,other]);db.session.flush()
    for order in (transfer,other):
        db.session.add(ns['TransferOrderItem'](transfer_order_id=order.id,material_id=self.material.id,
            quantity=quantity,price=3.56789,amount=12.34567,remark='原行备注'))
    # Historical old producer writes raw legs, while each location primitive
    # normalizes independently. Actual old apply_transfer_pair reproduction is
    # archived separately; baseline location is intentionally not guessed as bin.
    normalized=ns['normalize_stock_quantity'](quantity)
    for wh in (source,target):
        self.txn(wh.id,20,'material_initial',self.material.id)
    self.transfer_pair(transfer,quantity,source,target,'SAME','SAME')
    self.transfer_pair(other,quantity,target,source,'OTHER','OTHER')
    for wh,place,value in ((source,'SAME',10-normalized),(target,'SAME',10+normalized),
                          (source,'OTHER',10+normalized),(target,'OTHER',10-normalized)):
        db.session.add(ns['LocationInventory'](material_id=self.material.id,warehouse_id=wh.id,
            location=place,quantity=value))
    self.material.stock=40;db.session.commit()
    for wh in (source,target):
        self.assertEqual(ns['_transfer_quantity_net']([row.quantity for row in ns['LocationInventory'].query.filter_by(warehouse_id=wh.id)]),20)
        self.assertEqual(ns['_transfer_quantity_net']([row.quantity for row in ns['StockTransaction'].query.filter_by(warehouse_id=wh.id)]),20)
    before=self.transfer_snapshot()
    payload=self.transfer_route('revert_transfer',transfer)
    self.assertEqual(payload['status'],'error',payload)
    self.assertIn('逐库位原数量落账证明',payload['msg'])
    self.assertEqual(self.transfer_snapshot(),before)
    self.assertEqual(transfer.status,'completed')

'''


def main():
    harness=Path(__file__).with_name('verify_audit_real_models_20261113.py')
    tree=ast.parse(harness.read_text(encoding='utf-8-sig'))
    original=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    # The real warehouse identity function is explicitly extracted above.
    for node in ast.walk(original):
        if (isinstance(node,ast.Tuple) and all(isinstance(value,ast.Constant) for value in node.elts)
                and 'services.warehouse_stock_service' in [value.value for value in node.elts]):
            node.elts.append(ast.Constant(value='services.warehouse_identity'))
    suite=next(node for node in original.body if isinstance(node,ast.ClassDef) and node.name=='RealModelBoundaries')
    original.body[original.body.index(suite):original.body.index(suite)]=ast.parse(SETUP).body
    suite.body=[node for node in suite.body if isinstance(node,ast.FunctionDef) and node.name in ('setUp','tearDown','txn')]
    suite.body.extend(ast.parse(CASES).body)
    modes=('new_raw','new_down','new_tiny','new_ordinary','raw','duplicates','historical_normalized',
           'cycle','ordinary','closed_proven','closed_residue','unknown','bad_type','missing_leg','different_pair','insufficient',
           'normalized_perline','tiny_cycle','post_cycle_ambiguous','post_cycle_changed_bins','post_cycle_changed_warehouse')
    selected=[(mode,on) for mode in modes for on in (False,True)]
    selected.extend((mode,True) for mode in ('same_warehouse','same_warehouse_physical_normalized','cycle_same_warehouse','closed_missing_position','closed_other_bin','closed_per_line_residue',
        'current_missing_position','current_wrong_position','physical_normalized','negative_allowed','rollback'))
    assert len(selected)==53 and len(set(selected))==53
    for mode,on in selected:
        name='test_transfer_'+mode+('_on' if on else '_off')
        suite.body.extend(ast.parse('def '+name+'(self):\n    self.transfer_case('+repr(mode)+','+repr(on)+')\n').body)
    compensation=[(quantity,reverse) for quantity in (1.005,0.335) for reverse in (False,True)]
    assert len(compensation)==4 and len(set(compensation))==4
    for quantity,reverse in compensation:
        name='test_compensation_'+str(quantity).replace('.','_')+('_reverse' if reverse else '_forward')
        suite.body.extend(ast.parse('def '+name+'(self):\n    self.compensation_case('+repr(quantity)+','+repr(reverse)+')\n').body)
    counts=[node for node in ast.walk(original) if isinstance(node,ast.Compare) and isinstance(node.left,ast.Call)
            and isinstance(node.left.func,ast.Attribute) and node.left.func.attr=='countTestCases']
    assert len(counts)==1 and counts[0].comparators[0].value==9
    counts[0].comparators[0]=ast.Constant(value=59)
    imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
                 '<guarded-transfer-quantity>','exec'),namespace)
    namespace['main']()


def test_recorded_transfer_in_guarded_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
                          capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
