"""Pending reservation consumers: guarded actual models/functions, no app import."""
import ast
import os
from pathlib import Path
import subprocess
import sys

SETUP=r'''
from flask import url_for
ns['url_for']=url_for
app.add_url_rule('/synthetic/in_order/<int:id>',endpoint='in_order_detail',view_func=lambda id:'synthetic')
ns['purchase_in_order_requires_order']=lambda:False
ns['purchase_receipt_strict_order']=lambda:True
ns['purchase_over_receive_control_mode']=lambda:'forbid'
ns['purchase_order_to_in_order_enabled']=lambda:True
ns['prefer_default_warehouse']=lambda:False
ns['generate_order_no']=lambda prefix:prefix+'-SYN-'+str(ns['InOrder'].query.count()+1)
if any(isinstance(node,ast.FunctionDef) and node.name=='_purchase_reservation_error'
       for node in ast.parse((root/'app/app.py').read_text(encoding='utf-8-sig')).body):
    extract('app/app.py','_purchase_reservation_error')
for name in ('is_purchase_in_order','should_block_purchase_over_receive','validate_purchase_receive_quantity',
             'is_warehouse_active','assert_warehouse_active','resolve_active_inventory_warehouse',
             'validate_inventory_warehouse','is_future_date','_create_in_order_from_purchase_order_core'):
    extract('app/app.py',name)
extract('app/utils.py','parse_float_value')
extract('app/services/web_document_idempotency.py','stage_document_response')
for name in ('delete_in_order_item','in_order_item_delete_alias','delete_in_order','batch_delete_in_order',
             'update_in_order_item','add_in_order_item','copy_in_order','add_in_order','_product_header_project'):
    extract('app/routes/in_order.py',name)
for name in ('_aggregate_submitted_qty_by_item_id','create_in_order_from_purchase_order_selection'):
    extract('app/routes/purchase_order.py',name)
'''

HELPERS=r'''
def pending(self,quantity=1.01,counter=1.01,location_on=False):
    ns['location_management_enabled']=lambda:location_on
    ns['purchase_over_receive_control_mode']=lambda:'forbid'
    self.material.stock=20
    for warehouse in (self.a,self.b):
        self.txn(warehouse.id,10,'material_initial',self.material.id)
        if location_on:
            db.session.add(ns['LocationInventory'](material_id=self.material.id,warehouse_id=warehouse.id,location='SAME',quantity=10))
    po=ns['PurchaseOrder'](order_no='SYN-RESERVATION-PO',status='pending',total_amount=7.77)
    order=ns['InOrder'](order_no='SYN-RESERVATION-IN',warehouse=self.a.name,location='SAME',
        status='pending',business_type='采购入库',total_amount=7.77,remark='original')
    db.session.add_all([po,order])
    db.session.flush()
    source=ns['PurchaseOrderItem'](purchase_order_id=po.id,material_id=self.material.id,quantity=100,
        received_quantity=counter,price=0,amount=7.77,contract_no='SOURCE-CONTRACT')
    db.session.add(source)
    db.session.flush()
    row=ns['InOrderItem'](in_order_id=order.id,material_id=self.material.id,
        source_purchase_order_item_id=source.id,quantity=quantity,price=0,amount=7.77,
        contract_no='SOURCE-CONTRACT',remark='original')
    db.session.add(row)
    db.session.commit()
    return order,row,source

def pending_state(self):
    db.session.flush()
    return ([(r.id,r.quantity,r.received_quantity,r.amount) for r in ns['PurchaseOrderItem'].query.order_by(ns['PurchaseOrderItem'].id)],
        [(r.id,r.status,r.total_amount) for r in ns['PurchaseOrder'].query.order_by(ns['PurchaseOrder'].id)],
        [(r.id,r.status,r.total_amount,r.remark,r.warehouse) for r in ns['InOrder'].query.order_by(ns['InOrder'].id)],
        [(r.id,r.in_order_id,r.quantity,r.amount,r.remark,r.source_purchase_order_item_id) for r in ns['InOrderItem'].query.order_by(ns['InOrderItem'].id)],
        [(r.id,r.stock) for r in ns['Material'].query.order_by(ns['Material'].id)],
        [(r.id,r.quantity,r.reference_type,r.reference_id,r.warehouse_id) for r in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)],
        [(r.id,r.quantity,r.location,r.warehouse_id) for r in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)],
        [(r.id,r.status,r.pushed_quantity) for r in ns['DocumentPushLine'].query.order_by(ns['DocumentPushLine'].id)],
        ns['OperationAudit'].query.count(),ns['OperationLog'].query.count())

def pending_call(self,mode,order,row,source,payload_override=None,form_override=None):
    form=None
    payload=None
    if mode=='batch':
        payload={'ids':[order.id,str(order.id),order.id]}
    elif mode=='update':
        form={'id':row.id,'quantity':2,'price':0,'remark':'new'}
    elif mode=='addrow':
        form={'material_code':self.material.code,'quantity':1.01,'price':0,'source_purchase_order_item_id':source.id}
    elif mode in ('json_new','json_replace'):
        payload={'business_type':'采购入库','warehouse':self.a.name,'location':'SAME',
            'items':[{'code':self.material.code,'quantity':1.01,'price':0,'source_purchase_order_item_id':source.id}]}
        if mode=='json_replace':
            payload['order_id']=order.id
    elif mode=='selection':
        payload={'warehouse':self.a.name,'items':[{'purchase_order_item_id':source.id,'quantity':1.01}]}
    if payload_override is not None:
        payload=payload_override
    if form_override is not None:
        form=form_override
    with app.test_request_context('/synthetic/pending',method='POST',data=form,json=payload):
        login_user(self.user)
        with patch.dict(ns,request=actual_request,current_user=real_current_user):
            if mode=='single':
                result=ns['delete_in_order_item'](order.id,row.id)
            elif mode=='alias':
                result=ns['in_order_item_delete_alias'](order.id,row.id)
            elif mode=='whole':
                result=ns['delete_in_order'](order.id)
            elif mode=='batch':
                result=ns['batch_delete_in_order']()
            elif mode=='update':
                result=ns['update_in_order_item']()
            elif mode=='addrow':
                result=ns['add_in_order_item'](order.id)
            elif mode=='copy':
                result=ns['copy_in_order'](order.id)
            elif mode=='core':
                created,error=ns['_create_in_order_from_purchase_order_core'](source.purchase_order,
                    warehouse=self.a.name,submitted_qty_by_id={source.id:1.01})
                return (400,{'status':'error','msg':error}) if error else (200,{'status':'success','id':created.id})
            elif mode=='selection':
                result=ns['create_in_order_from_purchase_order_selection']()
            elif mode in ('json_new','json_replace'):
                result=ns['add_in_order']()
            else:
                raise AssertionError('Unknown consumer')
    status=result[1] if isinstance(result,tuple) else 200
    result=result[0] if isinstance(result,tuple) else result
    return status,result.get_json()
'''

DELETE=r'''
def test_delete_{name}(self):
    mode={mode!r}
    kind={kind!r}
    q,c={{'line':(1.005,1.01),'counter':(1.01,1.005),'both':(1.005,1.005),'normal':(1.01,1.01)}}[kind]
    order,row,source=self.pending(q,c,{location_on})
    before=self.pending_state()
    status,result=self.pending_call(mode,order,row,source)
    if kind=='normal':
        self.assertEqual(result['status'],'success',result)
        self.assertEqual(source.received_quantity,0)
        self.assertIsNone(db.session.get(ns['InOrderItem'],row.id))
        self.assertEqual(self.material.stock,20)
        if mode=='batch':
            self.assertEqual(result['deleted'],1,result)
    else:
        if mode=='batch':
            self.assertEqual(result['deleted'],0,result)
            self.assertTrue(result['skipped'],result)
        else:
            self.assertEqual(status,400,result)
        self.assertEqual(self.pending_state(),before)
'''

UPDATE=r'''
def test_update_strict_{name}(self):
    order,row,source=self.pending(1,1,{location_on})
    ns['purchase_over_receive_control_mode']=lambda:{strict_mode!r}
    status,result=self.pending_call('update',order,row,source)
    self.assertEqual(result['status'],'success',result)
    self.assertEqual(row.quantity,2)
    self.assertEqual(source.received_quantity,2,'over-receive gate must not disable reservation accounting')
    self.assertEqual(self.material.stock,20)
'''

COUNTER=r'''
def test_new_counter_{name}(self):
    order,row,source=self.pending(1.01,1.005,{location_on})
    before=self.pending_state()
    status,result=self.pending_call({mode!r},order,row,source)
    self.assertEqual(status,400,result)
    self.assertEqual(self.pending_state(),before)
'''

EXTRA=r'''
def test_extra_{name}(self):
    mode={mode!r}
    location_on={location_on}
    quantity=1.005 if mode in ('json_history_line','update_history_line','update_metadata_history','no_source_single','no_source_whole','no_source_batch') else 1.01
    counter=1.005 if mode in ('update_history_counter','update_metadata_history','core_unselected_history') else 1.01
    if mode.startswith('copy_shared'):
        quantity,counter=3,6
    order,row,source=self.pending(quantity,counter,location_on)
    before=self.pending_state()
    if mode in ('json_two_sources_success','json_two_sources_later_failure','copy_two_sources_success'):
        second=ns['PurchaseOrderItem'](purchase_order_id=source.purchase_order_id,material_id=self.material.id,
            quantity=10,received_quantity=1.01 if mode=='copy_two_sources_success' else 0,price=0,amount=4.02,
            contract_no='SECOND-CONTRACT')
        db.session.add(second)
        db.session.flush()
        source.purchase_order.total_amount=11.79
        if mode=='copy_two_sources_success':
            db.session.add(ns['InOrderItem'](in_order_id=order.id,material_id=self.material.id,
                source_purchase_order_item_id=second.id,quantity=1.01,price=0,amount=4.02,contract_no='SECOND-CONTRACT'))
            order.total_amount=11.79
        db.session.commit()
        before=self.pending_state()
        if mode=='copy_two_sources_success':
            status,result=self.pending_call('copy',order,row,source)
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(source.received_quantity,2.02)
            self.assertEqual(second.received_quantity,2.02)
            copied=ns['InOrderItem'].query.filter_by(in_order_id=result['id']).all()
            self.assertEqual({{r.contract_no for r in copied}},{{'SOURCE-CONTRACT','SECOND-CONTRACT'}})
        else:
            data={{'business_type':'采购入库','warehouse':self.a.name,'location':'SAME',
                'items':[{{'code':self.material.code,'quantity':2,'price':0,'source_purchase_order_item_id':s.id}} for s in (source,second)]}}
            if mode=='json_two_sources_later_failure':
                data['items'].append({{'code':self.material.code,'quantity':1,'source_purchase_order_item_id':999999}})
            status,result=self.pending_call('json_new',order,row,source,payload_override=data)
            if mode=='json_two_sources_success':
                self.assertEqual(result['status'],'success',result)
                self.assertEqual(source.received_quantity,3.01)
                self.assertEqual(second.received_quantity,2)
            else:
                self.assertEqual(status,400,result)
                self.assertEqual(self.pending_state(),before)
        self.assertEqual(self.material.stock,20)
    elif mode in ('metadata_zero_history','update_other_line_amount'):
        if mode=='metadata_zero_history':
            row.quantity=1.005
            row.amount=0
            order.total_amount=0
            source.received_quantity=1.005
            db.session.commit()
            status,result=self.pending_call('update',order,row,source,form_override={{'id':row.id,'remark':'only remark'}})
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(row.quantity,1.005)
            self.assertEqual(row.amount,0)
            self.assertEqual(order.total_amount,0)
            self.assertEqual(source.received_quantity,1.005)
        else:
            other=ns['InOrderItem'](in_order_id=order.id,material_id=self.material.id,quantity=1.005,price=0,amount=4.02)
            db.session.add(other)
            order.total_amount=0
            db.session.commit()
            status,result=self.pending_call('update',order,row,source,form_override={{'id':row.id,'quantity':2,'price':4}})
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(row.amount,8)
            self.assertEqual(other.quantity,1.005)
            self.assertEqual(other.amount,4.02)
            self.assertAlmostEqual(order.total_amount,12.02,places=12)
    elif mode.startswith('json_'):
        source.quantity=10
        db.session.commit()
        before=self.pending_state()
        data={{'order_id':order.id,'business_type':'采购入库','warehouse':self.a.name,'location':'SAME',
            'items':[{{'code':self.material.code,'quantity':1,'price':0,'source_purchase_order_item_id':source.id}}]}}
        if mode=='json_history_line':
            pass
        elif mode=='json_bad_source':
            data['items'].append({{'code':self.material.code,'quantity':1,'price':0,'source_purchase_order_item_id':999999}})
        elif mode=='json_bad_customer':
            data['items'].append({{'code':self.material.code,'quantity':1,'price':0,'source_purchase_order_item_id':source.id,'is_customer_supplied':True}})
        elif mode=='json_bad_batch':
            data['items'].append({{'code':self.material.code,'quantity':1,'price':0,'source_purchase_order_item_id':source.id,'batch_no':'x'*51}})
        elif mode=='json_bad_expiry':
            data['items'].append({{'code':self.material.code,'quantity':1,'price':0,'source_purchase_order_item_id':source.id,'expiry_date':'bad-date'}})
        else:
            data['items']=[{{'code':self.material.code,'quantity':6,'price':0,'source_purchase_order_item_id':source.id}} for _ in range(2)]
            if mode!='json_shared_replace_forbid':
                data.pop('order_id')
            if mode=='json_shared_allow':
                ns['purchase_over_receive_control_mode']=lambda:'allow'
        status,result=self.pending_call('json_replace',order,row,source,payload_override=data)
        if mode=='json_shared_allow':
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(source.received_quantity,13.01)
        else:
            self.assertEqual(status,400,result)
            self.assertEqual(self.pending_state(),before)
    elif mode.startswith('copy_shared'):
        source.quantity=10
        db.session.add(ns['InOrderItem'](in_order_id=order.id,material_id=self.material.id,
            source_purchase_order_item_id=source.id,quantity=3,price=0,amount=0))
        db.session.commit()
        before=self.pending_state()
        if mode=='copy_shared_allow':
            ns['purchase_over_receive_control_mode']=lambda:'allow'
        status,result=self.pending_call('copy',order,row,source)
        if mode=='copy_shared_allow':
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(source.received_quantity,12)
        else:
            self.assertEqual(status,400,result)
            self.assertEqual(self.pending_state(),before)
    elif mode.startswith('update_'):
        if mode=='update_metadata_history':
            form={{'id':row.id,'quantity':row.quantity,'price':row.price,'remark':'only remark'}}
            status,result=self.pending_call('update',order,row,source,form_override=form)
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(row.quantity,1.005)
            self.assertEqual(row.amount,7.77)
            self.assertEqual(source.received_quantity,1.005)
            self.assertEqual(self.material.stock,20)
        elif mode=='update_header_total':
            status,result=self.pending_call('update',order,row,source,
                form_override={{'id':row.id,'quantity':2,'price':4}})
            self.assertEqual(result['status'],'success',result)
            self.assertEqual(row.amount,8)
            self.assertEqual(order.total_amount,8,'saved detail amount and header must agree')
        else:
            status,result=self.pending_call('update',order,row,source)
            self.assertEqual(status,400,result)
            self.assertEqual(self.pending_state(),before)
    elif mode.startswith('batch_'):
        first_bad=mode=='batch_mixed_reverse'
        if first_bad:
            row.quantity=1.005
            source.purchase_order.status='partial'
        second_po=ns['PurchaseOrder'](order_no='SYN-SECOND-PO',status='partial',total_amount=4.02)
        second_order=ns['InOrder'](order_no='SYN-SECOND-IN',warehouse=self.b.name,location='SAME',status='pending',total_amount=4.02)
        db.session.add_all([second_po,second_order])
        db.session.flush()
        second_source=ns['PurchaseOrderItem'](purchase_order_id=second_po.id,material_id=self.material.id,quantity=100,
            received_quantity=1.01,price=0,amount=4.02)
        db.session.add(second_source)
        db.session.flush()
        second_row=ns['InOrderItem'](in_order_id=second_order.id,material_id=self.material.id,
            source_purchase_order_item_id=second_source.id,quantity=1.005 if mode=='batch_mixed_forward' else 1.01,price=0,amount=4.02)
        db.session.add(second_row)
        db.session.commit()
        failed_order=order if first_bad else second_order
        failed_source=source if first_bad else second_source
        failed_row=row if first_bad else second_row
        saved=(failed_order.id,failed_order.total_amount,failed_source.received_quantity,
            failed_source.purchase_order.status,failed_source.purchase_order.total_amount,failed_row.quantity,failed_row.amount)
        fail_item_id=second_row.id
        hit=[]
        def injected(_connection,_cursor,statement,parameters,_context,_executemany):
            if statement.lstrip().upper().startswith('DELETE FROM IN_ORDER_ITEM') and parameters==(fail_item_id,):
                hit.append(True)
                raise RuntimeError('owned synthetic second document DELETE failure')
        if mode=='batch_later_dml':
            event.listen(db.engine,'before_cursor_execute',injected)
        try:
            status,result=self.pending_call('batch',order,row,source,
                payload_override={{'ids':[order.id,str(second_order.id),order.id,second_order.id]}})
        finally:
            if mode=='batch_later_dml':
                event.remove(db.engine,'before_cursor_execute',injected)
        self.assertEqual(result['deleted'],1,result)
        self.assertEqual(len(result['skipped']),1,result)
        self.assertIsNotNone(db.session.get(ns['InOrder'],saved[0]))
        self.assertEqual((failed_order.id,failed_order.total_amount,failed_source.received_quantity,
            failed_source.purchase_order.status,failed_source.purchase_order.total_amount,failed_row.quantity,failed_row.amount),saved)
        self.assertEqual(self.material.stock,20)
        if mode=='batch_later_dml':
            self.assertEqual(hit,[True])
    elif mode=='core_unselected_history':
        second=ns['PurchaseOrderItem'](purchase_order_id=source.purchase_order_id,material_id=self.material.id,
            quantity=10,received_quantity=0,price=0,amount=0)
        db.session.add(second)
        db.session.commit()
        status,result=self.pending_call('core',order,row,second)
        self.assertEqual(result['status'],'success',result)
        self.assertEqual(source.received_quantity,1.005)
        self.assertEqual(second.received_quantity,1.01)
    elif mode.startswith('no_source_'):
        row.source_purchase_order_item_id=None
        source.received_quantity=0
        db.session.commit()
        status,result=self.pending_call(mode.removeprefix('no_source_'),order,row,source)
        self.assertEqual(result['status'],'success',result)
        self.assertEqual(source.received_quantity,0)
        self.assertIsNone(db.session.get(ns['InOrderItem'],row.id))
        self.assertEqual(self.material.stock,20)
    elif mode.startswith('ulp_'):
        source.received_quantity=math.nextafter(1.01,float('inf'))
        db.session.commit()
        status,result=self.pending_call(mode.removeprefix('ulp_'),order,row,source)
        self.assertEqual(result['status'],'success',result)
        self.assertAlmostEqual(source.received_quantity,2 if mode=='ulp_update' else 2.02,places=12)
        self.assertEqual(self.material.stock,20)
    elif mode.startswith('reverted_'):
        for quantity,typ in ((1.01,'in'),(-1.01,'revert_in')):
            txn=self.txn(self.a.id,quantity,'in_order',order.id)
            txn.transaction_type=typ
        db.session.commit()
        status,result=self.pending_call(mode.removeprefix('reverted_'),order,row,source)
        self.assertEqual(result['status'],'success',result)
        self.assertEqual(source.received_quantity,0)
        self.assertEqual(ns['StockTransaction'].query.filter_by(reference_type='in_order',reference_id=order.id).count(),0)
        self.assertEqual(self.material.stock,20)
    else:
        raise AssertionError('Unknown explicit case')
'''

def main():
    root=Path(__file__).resolve().parents[1]
    tree=ast.parse((root/'tests/verify_audit_real_models_20261113.py').read_text(encoding='utf-8-sig'))
    original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    def constants(filename):
        parsed=ast.parse((root/'tests'/filename).read_text(encoding='utf-8-sig'))
        return {n.targets[0].id:ast.literal_eval(n.value) for n in parsed.body
            if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)}
    order=constants('test_recorded_order_quantity_source_20261113.py')
    completed=constants('test_completed_inbound_quantity_source_20261113.py')
    for node in ast.walk(original):
        if (isinstance(node,ast.Tuple) and all(isinstance(v,ast.Constant) for v in node.elts)
                and 'services.warehouse_stock_service' in [v.value for v in node.elts]):
            node.elts.extend(ast.Constant(value=name) for name in ('services.document_return_guard','services.warehouse_identity'))
    suite=next(n for n in original.body if isinstance(n,ast.ClassDef) and n.name=='RealModelBoundaries')
    suite.body=[n for n in suite.body if not(isinstance(n,ast.FunctionDef) and n.name.startswith('test_'))]
    original.body[original.body.index(suite):original.body.index(suite)]=ast.parse(order['SETUP']+completed['SETUP']+SETUP).body
    suite.body.extend(ast.parse(HELPERS).body)
    cases=[]
    for location_on in (False,True):
        suffix='_on' if location_on else '_off'
        for mode in ('single','alias','whole','batch'):
            for kind in ('line','counter','both','normal'):
                cases.extend(ast.parse(DELETE.format(name=mode+'_'+kind+suffix,mode=mode,kind=kind,location_on=location_on)).body)
        for strict_mode in ('forbid','allow'):
            cases.extend(ast.parse(UPDATE.format(name=strict_mode+suffix,strict_mode=strict_mode,location_on=location_on)).body)
        for mode in ('addrow','copy','core','selection','json_new','json_replace'):
            cases.extend(ast.parse(COUNTER.format(name=mode+suffix,mode=mode,location_on=location_on)).body)
        for mode in ('json_history_line','json_bad_source','json_bad_customer','json_bad_batch','json_bad_expiry',
            'json_shared_forbid','json_shared_replace_forbid','json_shared_allow','copy_shared_forbid','copy_shared_allow',
            'update_history_line','update_history_counter','update_metadata_history','update_header_total',
            'batch_mixed_forward','batch_mixed_reverse','batch_later_dml','core_unselected_history',
            'no_source_single','no_source_whole','no_source_batch','ulp_addrow','ulp_update','ulp_copy','reverted_whole','reverted_batch',
            'json_two_sources_success','json_two_sources_later_failure','copy_two_sources_success','metadata_zero_history','update_other_line_amount'):
            specification=EXTRA.format(name=mode+suffix,mode=mode,location_on=location_on)
            if mode=='json_two_sources_later_failure' and not location_on:
                # The existing two-successful-rows/third-invalid rollback scenario
                # directly exercises add_in_order's real nested fail helper.
                assert specification.count('def test_extra_json_two_sources_later_failure_off(')==1
                specification=specification.replace('def test_extra_json_two_sources_later_failure_off(', 'def test_fail(')
            cases.extend(ast.parse(specification).body)
    assert len(cases)==110,len(cases)
    suite.body.extend(cases)
    counts=[n for n in ast.walk(original) if isinstance(n,ast.Compare) and isinstance(n.left,ast.Call)
        and isinstance(n.left.func,ast.Attribute) and n.left.func.attr=='countTestCases']
    assert len(counts)==1 and counts[0].comparators[0].value==9
    counts[0].comparators[0]=ast.Constant(value=110)
    imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
        '<guarded-purchase-reservation>','exec'),namespace)
    namespace['main']()


def test__purchase_reservation_error_in_guarded_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=150)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
