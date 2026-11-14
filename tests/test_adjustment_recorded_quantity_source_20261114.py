"""Signed adjustment reversal, actual source/models in guarded fresh memory.

No WMS import, file database, network, subprocess or application hook runs in
the worker. This is source-model evidence, not full app integration.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys

SETUP = r'''
from flask_login import LoginManager,login_user,current_user as actual_login_user
login_manager=LoginManager(app)
login_manager.user_loader(lambda ident: db.session.get(ns['User'],int(ident)))
ns.update(current_user=actual_login_user,request=actual_request)
if any(isinstance(node,ast.FunctionDef) and node.name=='_reverse_recorded_adjustment_stock'
       for node in ast.walk(ast.parse((root/'app/services/warehouse_stock_service.py').read_text(encoding='utf-8-sig')))):
    extract('app/services/warehouse_stock_service.py','_reverse_recorded_adjustment_stock')
extract('app/routes/adjustment.py','revert_adjustment')
'''

CASES = r'''
def adjustment_make(self,sign,location_on,values=None,recorded=None,positions=None):
    ns['location_management_enabled']=lambda:location_on
    ns['allow_negative_stock']=lambda:False
    ns['allow_negative_location_stock']=lambda:False
    values=[sign*1.005] if values is None else values
    recorded=values if recorded is None else recorded
    order=ns['AdjustmentOrder'](adjustment_no='SYN-ADJ-HISTORY',status='completed',warehouse=self.a.name,
        adjustment_type='surplus' if sign>0 else 'loss',source_type='manual',remark='原调整备注')
    db.session.add(order);db.session.flush()
    for index,value in enumerate(values):
        db.session.add(ns['AdjustmentOrderItem'](adjustment_order_id=order.id,material_id=self.material.id,
            quantity=value,location=positions[index] if positions else 'SAME',reason='原行原因'))
    self.txn(self.a.id,10,'material_initial',self.material.id)
    self.txn(self.b.id,10,'material_initial',self.material.id)
    rows=[]
    for value in recorded:
        row=self.txn(self.a.id,value,'adjustment',order.id)
        row.transaction_type='adjustment_in' if value>=0 else 'adjustment_out'
        row.location=self.a.name;rows.append(row)
    self.material.price=2.5
    self.material.stock=20+math.fsum(recorded)
    if location_on:
        if positions and len(set(positions))>1:
            for position in set(positions):
                quantity=sum(recorded[i] for i,p in enumerate(positions) if p==position)
                db.session.add(ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,
                    location=position,quantity=(10 if position==positions[0] else 0)+quantity))
        else:
            db.session.add(ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,
                location='SAME',quantity=10+math.fsum(recorded)))
        db.session.add(ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.b.id,location='SAME',quantity=10))
    db.session.commit()
    return order,rows

def adjustment_state(self,order):
    return ([(r.id,r.stock,r.price) for r in ns['Material'].query.order_by(ns['Material'].id)],
        [(r.id,r.quantity,r.transaction_type,r.reference_type,r.reference_id,r.warehouse_id,r.location,r.material_id)
         for r in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)],
        [(r.id,r.quantity,r.location,r.warehouse_id,r.material_id) for r in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)],
        [(c.key,getattr(order,c.key)) for c in order.__table__.columns],
        [(r.id,r.quantity,r.material_id,r.location,r.reason,r.unit_id) for r in order.items])

def adjustment_route(self,order):
    with app.test_request_context('/synthetic-only',method='POST'):
        login_user(self.user)
        result=ns['revert_adjustment'](order.id)
    result=result[0] if isinstance(result,tuple) else result
    return result.get_json() if hasattr(result,'get_json') else result

def adjustment_refusal(self,order,part):
    before=self.adjustment_state(order)
    payload=self.adjustment_route(order)
    self.assertEqual(payload['status'],'error',payload);self.assertIn(part,payload['msg'])
    self.assertEqual(self.adjustment_state(order),before)

def adjustment_success(self,order,rows,expected=20):
    before=self.adjustment_state(order);ids=[r.id for r in rows]
    original={direction:sum((Decimal(str(abs(r.quantity))) for r in rows
        if (r.quantity>=0)==(direction=='in')),Decimal(0)) for direction in ('in','out')}
    last_reverse=max((r.id for r in rows if r.transaction_type.startswith('revert_')),default=0)
    active=[r for r in rows if r.id>last_reverse]
    expected_gross={direction:original[direction]+sum((Decimal(str(abs(r.quantity))) for r in active
        if (r.quantity<0)==(direction=='in')),Decimal(0)) for direction in('in','out')}
    payload=self.adjustment_route(order);self.assertEqual(payload['status'],'success',payload)
    self.assertEqual(order.status,'pending');self.assertAlmostEqual(self.material.stock,expected,places=12)
    self.assertAlmostEqual(math.fsum(r.quantity for r in ns['StockTransaction'].query),expected,places=12)
    actual=ns['StockTransaction'].query.filter_by(reference_type='adjustment',reference_id=order.id).all()
    self.assertAlmostEqual(math.fsum(r.quantity for r in actual),0,places=12)
    for ident in ids:self.assertIsNotNone(db.session.get(ns['StockTransaction'],ident))
    # Real SQLA rows: gross in/out and their price-based reference amounts must
    # survive; never replace opposite movements with a zero net/no-op.
    for direction in('in','out'):
        total=sum((Decimal(str(abs(r.quantity))) for r in actual
            if (r.quantity>=0)==(direction=='in')),Decimal(0))
        self.assertEqual(total,expected_gross[direction])
        self.assertEqual(total*Decimal('2.5'),expected_gross[direction]*Decimal('2.5'))
    self.assertEqual(len(actual),len(rows)+len(active))
    previous_b=[r for r in before[1] if r[5]==self.b.id]
    self.assertEqual([(r.id,r.quantity,r.transaction_type,r.reference_type,r.reference_id,r.warehouse_id,r.location,r.material_id)
        for r in ns['StockTransaction'].query.filter_by(warehouse_id=self.b.id).order_by(ns['StockTransaction'].id)],previous_b)
    before_a=math.fsum(r[1] for r in before[1] if r[5]==self.a.id)
    after_a=math.fsum(r.quantity for r in ns['StockTransaction'].query.filter_by(warehouse_id=self.a.id))
    self.assertAlmostEqual(after_a,before_a-math.fsum(r.quantity for r in active),places=12)
    if ns['location_management_enabled']():
        self.assertAlmostEqual(math.fsum(r.quantity for r in ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id)),after_a,places=12)
        self.assertEqual([(r.id,r.quantity,r.location,r.warehouse_id,r.material_id) for r in ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).order_by(ns['LocationInventory'].id)],
                         [r for r in before[2] if r[3]==self.b.id])
    after=self.adjustment_state(order)
    self.assertEqual(after[4],before[4])
    self.assertEqual([(k,v) for k,v in after[3] if k!='status'],[(k,v) for k,v in before[3] if k!='status'])
    self.assertEqual(self.material.price,2.5)

def adjustment_case(self,sign,location_on,mode):
    values=([sign*1.005]*100 if mode=='cumulative_float' else [sign*1.005,sign*2.005] if mode in('same_sku_raw','aggregate','multi_bin','dml_failure') else
            [sign*1.005,sign*1.005] if mode=='same_sku_norm' else
            [sign*1.005,-sign*1.005] if mode in('mixed_raw_net_zero','mixed_norm_net_zero') else
            [sign*1.01,-sign*1.01] if mode in('ordinary_net_zero','ordinary_prefix') else
            [sign*.1,sign*.2] if mode=='float_tail' else [sign*1e-20] if mode=='float_tiny' else
            [sign*1.01] if mode=='ordinary' else None)
    recorded=([sign*1.01] if mode=='normalized' else [sign*1.01,sign*1.01] if mode=='same_sku_norm' else
              [sign*3.01] if mode=='aggregate' else [sign*1.004] if mode=='mismatch' else
              [sign*1.01,-sign*1.01] if mode=='mixed_norm_net_zero' else None)
    positions=['SAME','OTHER'] if mode=='multi_bin' else None
    order,rows=self.adjustment_make(sign,location_on,values,recorded,positions)
    if mode in('raw','normalized','ordinary','same_sku_raw','same_sku_norm','ordinary_net_zero','float_tail'):
        self.adjustment_success(order,rows)
    elif mode=='aggregate':self.adjustment_refusal(order,'逐行对应')
    elif mode=='mismatch':self.adjustment_refusal(order,'逐行对应')
    elif mode=='multi_bin':
        if location_on:self.adjustment_refusal(order,'多库位')
        else:self.adjustment_success(order,rows)
    elif mode in('mixed_raw_net_zero','mixed_norm_net_zero'):self.adjustment_refusal(order,'混合方向')
    elif mode in('phase_bad','phase_sign','unknown_fk','unknown_warehouse','header_conflict','missing_source','missing_bin','position_mismatch','missing_position_record','global_mismatch'):
        if mode=='phase_bad':rows[0].transaction_type='unproven-adjustment'
        elif mode=='phase_sign':rows[0].transaction_type='adjustment_out' if sign>0 else 'adjustment_in'
        elif mode=='unknown_fk':rows[0].warehouse_id=None
        elif mode=='unknown_warehouse':rows[0].warehouse_id=999999
        elif mode=='header_conflict':order.warehouse=self.b.name
        elif mode=='missing_source':db.session.delete(rows[0])
        elif mode=='missing_bin':order.items[0].location=''
        elif mode=='position_mismatch':ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity+=.005
        elif mode=='missing_position_record':ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().location='OTHER'
        elif mode=='global_mismatch':self.material.stock+=.005
        db.session.commit()
        part={'phase_bad':'阶段','phase_sign':'方向','unknown_fk':'原仓归属','unknown_warehouse':'原仓记录',
            'header_conflict':'头仓库','missing_source':'原流水缺失','missing_bin':'原库位缺失',
            'position_mismatch':'库位账与流水不一致','missing_position_record':'缺失或重复','global_mismatch':'总账与流水不一致'}[mode]
        self.adjustment_refusal(order,part)
    elif mode=='renamed':
        order.warehouse='SYN-OLD-NAME';db.session.commit();self.adjustment_success(order,rows)
    elif mode=='repeat':
        self.adjustment_success(order,rows);before=self.adjustment_state(order)
        self.assertEqual(self.adjustment_route(order)['status'],'error');self.assertEqual(self.adjustment_state(order),before)
    elif mode=='ordinary_prefix':
        self.txn(self.a.id,-10,'synthetic-balance',98);self.txn(self.b.id,10,'synthetic-balance',99)
        if location_on:
            ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=0
            ns['LocationInventory'].query.filter_by(warehouse_id=self.b.id).one().quantity=20
        db.session.commit()
        if sign>0:
            before=self.adjustment_state(order);self.assertEqual(self.adjustment_route(order)['status'],'error');self.assertEqual(self.adjustment_state(order),before)
        else:self.adjustment_success(order,rows)
    elif mode in('global_shortage','wh_shortage','allow_negative'):
        warehouse=self.b if mode=='global_shortage' else self.a
        extra=-30 if mode=='global_shortage' else -11 if sign>0 else -9
        self.txn(warehouse.id,extra,'synthetic-consumption',99)
        self.material.stock+=extra
        if location_on:ns['LocationInventory'].query.filter_by(warehouse_id=warehouse.id).one().quantity+=extra
        if mode=='allow_negative':
            ns['allow_negative_stock']=lambda:True;ns['allow_negative_location_stock']=lambda:True
        db.session.commit()
        if sign>0 and mode!='allow_negative':self.adjustment_refusal(order,'全局库存不足' if mode=='global_shortage' else '原仓库存不足')
        else:self.adjustment_success(order,rows,expected=20+extra)
    elif mode=='bin_shortage':
        position=ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one()
        position.quantity=.5 if sign>0 else -5
        other=ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,location='OTHER',
            quantity=10+sign*1.005-position.quantity)
        db.session.add(other);db.session.commit()
        if sign>0:self.adjustment_refusal(order,'原库位库存不足')
        else:
            self.adjustment_success(order,rows);self.assertAlmostEqual(position.quantity,-3.995,places=12)
    elif mode=='cumulative_float' and sign<0 and not location_on:self.adjustment_success(order,rows)
    elif mode in('float_tiny','cumulative_float'):self.adjustment_refusal(order,'Float可逆精度')
    elif mode=='dml_failure':
        before=self.adjustment_state(order);hit=[];prefix='UPDATE LOCATION_INVENTORY' if location_on else 'UPDATE MATERIAL'
        def fail(_connection,_cursor,statement,_parameters,_context,_executemany):
            if statement.lstrip().upper().startswith(prefix):
                hit.append(True)
                if len(hit)==2:raise RuntimeError('owned synthetic second adjustment DML failure')
        event.listen(db.engine,'before_cursor_execute',fail)
        try:payload=self.adjustment_route(order)
        finally:event.remove(db.engine,'before_cursor_execute',fail)
        self.assertEqual(len(hit),2);self.assertEqual(payload['status'],'error',payload);self.assertEqual(self.adjustment_state(order),before)
    elif mode.startswith('closed_'):
        # Seed earlier periods before the current origin, preserving actual
        # stage families. Delete/reinsert only this owned synthetic ledger.
        for row in rows:db.session.delete(row)
        db.session.flush()
        values=[(sign*2.005,'adjustment_in' if sign>0 else 'adjustment_out'),
                (-sign*(1.005 if mode=='closed_residue' else 2.005),'revert_adjustment_in' if sign>0 else 'revert_adjustment_out')]
        if mode=='closed_phase_offset':values=[(1.005,'adjustment_in'),(-.005,'revert_adjustment_in'),(-1.005,'adjustment_out'),(.005,'revert_adjustment_out')]
        values.append((sign*1.005,'adjustment_in' if sign>0 else 'adjustment_out'))
        rows=[]
        for quantity,stage in values:
            row=self.txn(self.a.id,quantity,'adjustment',order.id);row.transaction_type=stage;row.location=self.a.name;rows.append(row)
        self.material.stock=20+math.fsum(q for q,_ in values)
        if location_on:ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity=10+math.fsum(q for q,_ in values)
        db.session.commit()
        if mode!='closed_cycle':self.adjustment_refusal(order,'此前调整周期')
        elif location_on:self.adjustment_refusal(order,'闭合历史')
        else:self.adjustment_success(order,rows)
    else:raise AssertionError('Unknown explicit adjustment scenario')

def test_net(self):
    # Exact existing case22: reject cross-direction netting of unclosed prior phases.
    self.adjustment_case(1,False,'closed_phase_offset')

def test_match_values(self):
    # Exact existing case3: preserve distinct same-SKU raw legs, row identity and gross.
    self.adjustment_case(1,False,'same_sku_raw')

def test_private_adjustment_has_no_public_delta_or_precision_switch(self):
    import inspect
    self.assertIn('_reverse_recorded_adjustment_stock',ns)
    self.assertEqual(list(inspect.signature(ns['_reverse_recorded_adjustment_stock']).parameters),['adjustment'])
    self.assertNotIn('raw',inspect.signature(ns['apply_stock_delta']).parameters)
    self.assertFalse(ns['_reverse_recorded_adjustment_stock'](types.SimpleNamespace(status='completed'))[0])

def adjustment_multi_material(self,sign,location_on):
    order,rows=self.adjustment_make(sign,location_on)
    other=ns['Material'](code='SYN-ADJ-OTHER',name='第二合成物料',stock=20-sign*1.005,price=4)
    db.session.add(other);db.session.flush()
    db.session.add(ns['AdjustmentOrderItem'](adjustment_order_id=order.id,material_id=other.id,
        quantity=-sign*1.005,location='SAME',reason='相反方向另一物料'))
    for warehouse,quantity,stage,reference,ident in((self.a,10,'initial','material_initial',other.id),
        (self.b,10,'initial','material_initial',other.id),(self.a,-sign*1.005,
        'adjustment_out' if sign>0 else 'adjustment_in','adjustment',order.id)):
        db.session.add(ns['StockTransaction'](material_id=other.id,quantity=quantity,transaction_type=stage,
            reference_type=reference,reference_id=ident,warehouse_id=warehouse.id,location=warehouse.name))
    if location_on:
        for warehouse,quantity in((self.a,10-sign*1.005),(self.b,10)):
            db.session.add(ns['LocationInventory'](material_id=other.id,warehouse_id=warehouse.id,
                location='SAME',quantity=quantity))
    db.session.commit();before=self.adjustment_state(order)
    self.assertEqual(self.adjustment_route(order)['status'],'success')
    self.assertEqual(order.status,'pending')
    self.assertEqual(self.adjustment_state(order)[4],before[4])
    for material,price in((self.material,2.5),(other,4)):
        self.assertAlmostEqual(material.stock,20,places=12);self.assertEqual(material.price,price)
        for warehouse in(self.a,self.b):
            ledger=ns['StockTransaction'].query.filter_by(material_id=material.id,warehouse_id=warehouse.id).all()
            self.assertAlmostEqual(math.fsum(r.quantity for r in ledger),10,places=12)
            if location_on:
                self.assertAlmostEqual(ns['LocationInventory'].query.filter_by(material_id=material.id,
                    warehouse_id=warehouse.id).one().quantity,10,places=12)
    actual=ns['StockTransaction'].query.filter_by(reference_type='adjustment',reference_id=order.id).all()
    self.assertEqual(len(actual),4)
    for direction in(1,-1):
        self.assertEqual(sum((Decimal(str(abs(r.quantity))) for r in actual if r.quantity*direction>0),Decimal(0)),Decimal('2.010'))
'''


def main():
    root=Path(__file__).resolve().parent
    tree=ast.parse((root/'verify_audit_real_models_20261113.py').read_text(encoding='utf-8-sig'))
    original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    prior=ast.parse((root/'test_recorded_order_quantity_source_20261113.py').read_text(encoding='utf-8-sig'))
    setup=next(ast.literal_eval(n.value) for n in prior.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SETUP' for t in n.targets))
    for n in ast.walk(original):
        if isinstance(n,ast.Tuple) and all(isinstance(x,ast.Constant) for x in n.elts) and 'services.warehouse_stock_service' in [x.value for x in n.elts]:
            n.elts.extend(ast.Constant(value=x) for x in('services.document_return_guard','services.warehouse_identity'))
    suite=next(n for n in original.body if isinstance(n,ast.ClassDef) and n.name=='RealModelBoundaries')
    original.body[original.body.index(suite):original.body.index(suite)]=ast.parse(setup+SETUP).body
    suite.body=[n for n in suite.body if isinstance(n,ast.FunctionDef) and n.name in('setUp','tearDown','txn')]
    suite.body.extend(ast.parse(CASES).body)
    common=('raw','normalized','ordinary','same_sku_raw','same_sku_norm','aggregate','mismatch','multi_bin',
        'mixed_raw_net_zero','mixed_norm_net_zero','ordinary_net_zero','ordinary_prefix','phase_bad','phase_sign',
        'unknown_fk','unknown_warehouse','header_conflict','missing_source','renamed','repeat',
        'closed_cycle','closed_residue','closed_phase_offset','global_shortage','wh_shortage','allow_negative',
        'global_mismatch','float_tiny','float_tail','dml_failure','cumulative_float')
    cases=[(sign,location_on,mode) for sign in(1,-1) for location_on in(False,True) for mode in common]
    cases += [(sign,True,mode) for sign in(1,-1) for mode in('missing_bin','position_mismatch','missing_position_record','bin_shortage')]
    assert len(cases)==132 and len(set(cases))==132
    for index,(sign,location_on,mode) in enumerate(cases):
        if index in (3,22):
            assert (sign,location_on,mode)=={3:(1,False,'same_sku_raw'),22:(1,False,'closed_phase_offset')}[index]
            continue
        suite.body.extend(ast.parse(f'def test_adjustment_{index}_{mode}(self):\n    self.adjustment_case({sign!r},{location_on!r},{mode!r})').body)
    for sign in(1,-1):
        for location_on in(False,True):
            suite.body.extend(ast.parse(f'def test_adjustment_multi_material_{sign}_{location_on}(self):\n    self.adjustment_multi_material({sign!r},{location_on!r})'.replace('material_-1','material_minus1')).body)
    counts=[n for n in ast.walk(original) if isinstance(n,ast.Compare) and isinstance(n.left,ast.Call) and isinstance(n.left.func,ast.Attribute) and n.left.func.attr=='countTestCases']
    assert len(counts)==1 and counts[0].comparators[0].value==9
    counts[0].comparators[0]=ast.Constant(value=137)
    imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
        '<guarded-adjustment-history>','exec'),namespace)
    namespace['main']()


def test_adjustment_history_in_guarded_child():
    env={key:os.environ[key] for key in('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':main()
