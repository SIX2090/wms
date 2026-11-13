"""Completed inbound quantities: actual source/models in guarded new memory only."""
import ast
import os
from pathlib import Path
import subprocess
import sys

SETUP=r'''
from flask_login import LoginManager, current_user as real_current_user, login_user
synthetic_login=LoginManager(app)
@synthetic_login.user_loader
def synthetic_user_loader(user_id):
    return db.session.get(ns['User'],int(user_id))
for name in ('api_error','get_default_warehouse','resolve_item_contract'):
    extract('app/app.py',name)
for name in ('_parse_item_batch_no','_parse_item_expiry_date','update_completed_in_order'):
    extract('app/routes/in_order.py',name)
'''

HELPERS=r'''
def completed_call(self,order,payload):
    with app.test_request_context('/synthetic-inbound-completed',method='POST',json=payload):
        login_user(self.user)
        with patch.dict(ns,request=actual_request,current_user=real_current_user):
            self.assertTrue(real_current_user.is_authenticated)
            result=ns['update_completed_in_order'](order.id)
    status=result[1] if isinstance(result,tuple) else 200
    response=result[0] if isinstance(result,tuple) else result
    return status,response.get_json()

def attach_source(self,order,item=None,received=0):
    purchase=ns['PurchaseOrder'](order_no='SYN-PO-COMP',status='approved')
    db.session.add(purchase)
    db.session.flush()
    source=ns['PurchaseOrderItem'](purchase_order_id=purchase.id,material_id=self.material.id,
        quantity=100,received_quantity=received,price=1,amount=100,contract_no='SOURCE-CONTRACT',project_name='SOURCE-PROJECT')
    db.session.add(source)
    db.session.flush()
    if item:
        item.source_purchase_order_item_id=source.id
    if received==10:
        other=ns['InOrder'](order_no='SYN-OTHER-RESERVATION',warehouse=self.b.name,status='pending')
        db.session.add(other)
        db.session.flush()
        db.session.add(ns['InOrderItem'](in_order_id=other.id,material_id=self.material.id,
            source_purchase_order_item_id=source.id,quantity=10,price=0,amount=0))
    db.session.commit()
    return source

def completed_snapshot(self,order,source):
    return dict(order_status=order.status,order_amount=order.total_amount,stock=self.material.stock,
        flow_total=math.fsum(row.quantity for row in ns['StockTransaction'].query),
        positions=[(row.warehouse_id,row.location,row.quantity) for row in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)],
        items=[(row.id,row.quantity,row.price,row.amount,row.remark,row.contract_no,row.source_purchase_order_item_id) for row in ns['InOrderItem'].query.filter_by(in_order_id=order.id).order_by(ns['InOrderItem'].id)],
        source_received=source.received_quantity,source_order_status=source.purchase_order.status,
        downstream=[(r.id,r.status,r.pushed_quantity) for r in ns['DocumentPushLine'].query.order_by(ns['DocumentPushLine'].id)],
        returns=[(r.id,r.quantity,r.source_in_order_item_id) for r in ns['OutOrderItem'].query.order_by(ns['OutOrderItem'].id)],
        audit_count=ns['OperationAudit'].query.count(),log_count=ns['OperationLog'].query.count())

def assert_stock_and_flow(self,expected,location_on):
    self.assertAlmostEqual(self.material.stock,expected,places=12)
    self.assertAlmostEqual(math.fsum(row.quantity for row in ns['StockTransaction'].query),expected,places=12)
    if location_on:
        self.assertAlmostEqual(math.fsum(row.quantity for row in ns['LocationInventory'].query),expected,places=12)
    self.assertEqual(ns['StockTransaction'].query.filter_by(warehouse_id=self.b.id).one().quantity,10)
'''

PRODUCER=r'''
def test_producer_{name}(self):
    location_on={location_on}
    linked={linked}
    previous={previous}
    quantity={quantity}
    order,_=self.recorded_order(location_on=location_on,quantities=[],recorded=[])
    source=self.attach_source(order,received=previous)
    item={{'is_new':True,'code':self.material.code,'quantity':quantity,'price':4,'remark':'synthetic'}}
    if linked:
        item['source_purchase_order_item_id']=source.id
    before=self.completed_snapshot(order,source)
    status,result=self.completed_call(order,{{'items':[item]}})
    expected=ns['normalize_stock_quantity'](quantity)
    if expected<=0:
        self.assertEqual(status,400)
        self.assertIn('两位',result['msg'])
        self.assertEqual(self.completed_snapshot(order,source),before)
    else:
        self.assertEqual(result['status'],'success',result)
        row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
        self.assertEqual(row.quantity,expected)
        self.assertEqual(row.amount,ns['round_money_product'](expected,4))
        self.assert_stock_and_flow(20+expected,location_on)
        self.assertAlmostEqual(source.received_quantity-previous,expected if linked else 0,places=12)
        self.assertEqual(row.contract_no,'SOURCE-CONTRACT' if linked else None)
        self.assertEqual(row.project_name,'SOURCE-PROJECT' if linked else None)
        self.assertEqual(ns['OperationAudit'].query.count(),1)
'''

NORMAL=r'''
def test_normal_{name}(self):
    location_on={location_on}
    linked={linked}
    mode={mode!r}
    quantity={quantity}
    order,_=self.recorded_order(location_on=location_on,quantities=[1.01],recorded=[1.01])
    row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
    source=self.attach_source(order,row if linked else None,received=1.01 if linked else 0)
    before=self.completed_snapshot(order,source)
    payload={{'deleted_items':[row.id]}} if mode=='delete' else {{'items':[{{'id':row.id,'quantity':quantity,'price':4}}]}}
    status,result=self.completed_call(order,payload)
    expected=0 if mode=='delete' else ns['normalize_stock_quantity'](quantity)
    if mode!='delete' and expected<=0:
        self.assertEqual(status,400)
        self.assertEqual(self.completed_snapshot(order,source),before)
    else:
        self.assertEqual(result['status'],'success',result)
        self.assert_stock_and_flow(20+expected,location_on)
        self.assertEqual(source.received_quantity,expected if linked else 0)
        if mode=='delete':
            self.assertEqual(ns['InOrderItem'].query.filter_by(in_order_id=order.id).count(),0)
        else:
            self.assertEqual(row.quantity,expected)
            self.assertEqual(row.amount,ns['round_money_product'](expected,4))
'''

HISTORY=r'''
def test_history_{name}(self):
    location_on={location_on}
    linked={linked}
    mode={mode!r}
    order,_=self.recorded_order(location_on=location_on,recorded=[{recorded}])
    row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
    source=self.attach_source(order,row if linked else None,received=1.01 if linked else 0)
    before=self.completed_snapshot(order,source)
    payload={{'deleted_items':[row.id]}} if mode=='delete' else {{'items':[{{'id':row.id,'quantity':2,'price':0}}]}}
    status,result=self.completed_call(order,payload)
    self.assertEqual(status,400)
    self.assertIn('历史',result['msg'])
    self.assertEqual(self.completed_snapshot(order,source),before)
'''

EXTRA=r'''
def test_extra_{name}(self):
    location_on={location_on}
    mode={mode!r}
    if mode.startswith('metadata_'):
        amount={{'metadata_zero':0,'metadata_amount':7.77,'metadata_rounded':4.02}}[mode]
        order,_=self.recorded_order(location_on=location_on)
        row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
        row.amount=amount
        row.contract_no='HIST-CONTRACT'
        source=self.attach_source(order,row,received=1.01)
        before=self.completed_snapshot(order,source)
        status,result=self.completed_call(order,{{'items':[{{'id':row.id,'quantity':1.005,'price':0,'remark':'only remark'}}]}})
        self.assertEqual(result['status'],'success',result)
        self.assertEqual(row.quantity,1.005)
        self.assertEqual(row.amount,amount)
        self.assertEqual(row.remark,'only remark')
        self.assertEqual(row.contract_no,'HIST-CONTRACT')
        self.assertEqual(self.material.stock,before['stock'])
        self.assertEqual(ns['StockTransaction'].query.count(),3)
        self.assertEqual(source.received_quantity,1.01)
    elif mode in ('mixed_rollback','ambiguous_one','ambiguous_two'):
        values=[1.01,1.005] if mode=='mixed_rollback' else [1.005,1.005]
        flows=[1.01,1.005] if mode=='mixed_rollback' else ([1.0,1.01] if mode=='ambiguous_one' else [1.01,1.0])
        order,_=self.recorded_order(location_on=location_on,quantities=values,recorded=flows)
        rows=ns['InOrderItem'].query.filter_by(in_order_id=order.id).order_by(ns['InOrderItem'].id).all()
        source=self.attach_source(order,received=2.02)
        for row in rows:
            row.source_purchase_order_item_id=source.id
        if mode=='ambiguous_one':
            target=ns['OutOrder'](order_no='SYN-DOWNSTREAM',warehouse=self.a.name,status='pending',business_type='采购退货出库')
            db.session.add(target)
            db.session.flush()
            target_item=ns['OutOrderItem'](out_order_id=target.id,material_id=self.material.id,
                source_in_order_item_id=rows[0].id,quantity=0.5,price=0,amount=0)
            db.session.add(target_item)
            db.session.flush()
            db.session.add(ns['DocumentPushLine'](source_document_type='in_order',source_document_id=order.id,
                source_document_no=order.order_no,source_item_id=rows[0].id,target_document_type='out_order',
                target_document_id=target.id,target_document_no=target.order_no,target_item_id=target_item.id,
                pushed_quantity=0.5,status='active',request_id='synthetic-source-boundary',created_by=self.user.id))
        db.session.commit()
        before=self.completed_snapshot(order,source)
        ids=[row.id for row in rows] if mode=='mixed_rollback' else [rows[0].id]
        status,result=self.completed_call(order,{{'deleted_items':ids}})
        self.assertEqual(status,400)
        self.assertIn('历史',result['msg'])
        self.assertEqual(self.completed_snapshot(order,source),before)
        self.assertNotIn('source_item_id',ns['StockTransaction'].__table__.columns)
    elif mode.startswith('counter_'):
        order,_=self.recorded_order(location_on=location_on,quantities=[1.01],recorded=[1.01])
        row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
        tail=mode.endswith('_tail')
        source=self.attach_source(order,row,received=math.nextafter(1.01,float('inf')) if tail else 1.005)
        before=self.completed_snapshot(order,source)
        if 'producer' in mode:
            payload={{'items':[{{'is_new':True,'code':self.material.code,'quantity':1.01,'price':0,'source_purchase_order_item_id':source.id}}]}}
            expected=22.02
        elif 'delete' in mode:
            payload={{'deleted_items':[row.id]}}
            expected=20
        else:
            payload={{'items':[{{'id':row.id,'quantity':2,'price':0}}]}}
            expected=22
        status,result=self.completed_call(order,payload)
        if tail:
            self.assertEqual(result['status'],'success',result)
            self.assert_stock_and_flow(expected,location_on)
            self.assertAlmostEqual(source.received_quantity,expected-20,places=12)
        else:
            self.assertEqual(status,400)
            self.assertIn('历史采购预留',result['msg'])
            self.assertEqual(self.completed_snapshot(order,source),before)
    else:
        order,_=self.recorded_order(location_on=location_on,quantities=[1.01],recorded=[1.01])
        row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
        source=self.attach_source(order,row,received=1.01)
        before=self.completed_snapshot(order,source)
        changed={{'id':row.id,'quantity':2,'price':0}}
        if mode=='invalid_metadata':
            changed['expiry_date']='not-a-valid-date'
        hit=[]
        def inject(_connection,_cursor,statement,_parameters,_context,_executemany):
            if statement.lstrip().upper().startswith('UPDATE MATERIAL'):
                hit.append(True)
                raise RuntimeError('owned synthetic material UPDATE failure')
        if mode=='dml_failure':
            event.listen(db.engine,'before_cursor_execute',inject)
        try:
            payload={{'items':[changed]}}
            if mode=='duplicate_delete':
                payload={{'deleted_items':[row.id,row.id]}}
            elif mode=='duplicate_alias_delete':
                payload={{'deleted_items':[row.id,str(row.id),row.id]}}
            elif mode=='delete_and_modify':
                payload={{'deleted_items':[row.id],'items':[changed]}}
            elif mode=='delete_and_modify_alias':
                changed['id']=str(row.id)
                payload={{'deleted_items':[row.id],'items':[changed]}}
            elif mode=='repeat_modify':
                payload={{'items':[changed,{{'id':row.id,'quantity':3,'price':0}}]}}
            status,result=self.completed_call(order,payload)
        finally:
            if mode=='dml_failure':
                event.remove(db.engine,'before_cursor_execute',inject)
        if mode in ('duplicate_delete','duplicate_alias_delete'):
            self.assertEqual(result['status'],'success',result)
            self.assert_stock_and_flow(20,location_on)
            self.assertEqual(source.received_quantity,0)
            before_repeat=self.completed_snapshot(order,source)
            status,repeated=self.completed_call(order,payload)
            self.assertEqual(repeated['status'],'success',repeated)
            self.assertEqual(self.completed_snapshot(order,source),before_repeat)
        elif mode=='repeat_modify':
            self.assertEqual(result['status'],'success',result)
            self.assert_stock_and_flow(23,location_on)
            self.assertEqual(source.received_quantity,3)
            self.assertEqual(row.quantity,3)
        else:
            self.assertEqual(result['status'],'error',result)
            self.assertEqual(self.completed_snapshot(order,source),before)
            if mode=='dml_failure':
                self.assertEqual(hit,[True])
'''

ULP=r"""
def test_ulp_{name}(self):
    location_on={location_on}
    mode={mode!r}
    linked={linked}
    amount={amount}
    direction={direction}
    old_qty=(1.005 if mode=='history' else 1.01 if mode=='change' else
             math.nextafter(1.01,float('inf') if direction>0 else 0))
    order,_=self.recorded_order(location_on=location_on,quantities=[old_qty],recorded=[1.01])
    row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
    row.price=2;row.amount=amount;row.contract_no='KEEP-CONTRACT';row.project_name='KEEP-PROJECT'
    db.session.commit()
    reserved=(math.nextafter(1.01,float('inf') if direction>0 else 0) if linked and mode in
              ('counter_metadata','change','sequential') else 1.01 if linked else 0)
    source=self.attach_source(order,row if linked else None,received=reserved)
    before=self.completed_snapshot(order,source)
    items=[{{'id':row.id,'quantity':1.01,'price':2,'remark':'only note'}}]
    if mode=='change':items[0]['quantity']=1.02
    elif mode=='sequential':items.append({{'id':str(row.id),'quantity':1.02,'price':2}})
    status,result=self.completed_call(order,{{'items':items}})
    if mode=='history':
        self.assertEqual(status,400,result);self.assertIn('历史',result['msg'])
        self.assertEqual(self.completed_snapshot(order,source),before)
    elif mode in ('change','sequential'):
        self.assertEqual(status,200,result)
        self.assertEqual((row.quantity,row.price,row.amount),(1.02,2,2.04))
        self.assert_stock_and_flow(21.02,location_on)
        self.assertEqual(source.received_quantity,1.02 if linked else 0)
    else:
        self.assertEqual(status,200,result)
        self.assertEqual((row.quantity,row.price,row.amount,row.remark),(old_qty,2,amount,'only note'))
        self.assertEqual(self.material.stock,before['stock'])
        self.assertEqual(source.received_quantity,reserved)
        self.assertEqual(ns['StockTransaction'].query.count(),3)
        self.assertEqual(self.completed_snapshot(order,source)['positions'],before['positions'])
    self.assertEqual((row.contract_no,row.project_name,row.source_purchase_order_item_id),
                     ('KEEP-CONTRACT','KEEP-PROJECT',source.id if linked else None))
"""

HEAD=r"""
def test_head_{name}(self):
    mode={mode!r};head={head!r};amount={amount};location_on={location_on}
    quantity=math.nextafter(1.01,float('inf')) if mode=='ulp' else 1.01
    order,_=self.recorded_order(location_on=location_on,quantities=[quantity],recorded=[1.01])
    row=ns['InOrderItem'].query.filter_by(in_order_id=order.id).one()
    row.price=0;row.amount=amount;order.total_amount=head;db.session.commit()
    source=self.attach_source(order,row,received=1.01)
    before=self.completed_snapshot(order,source)
    changed={{'id':row.id,'quantity':1.01,'price':0,'remark':'note only'}}
    data={{'items':[changed]}}
    if mode=='price':changed['price']=2
    elif mode=='quantity':changed['quantity']=2
    elif mode=='add':
        data={{'items':[{{'is_new':True,'code':self.material.code,'quantity':1.01,'price':2,
                         'source_purchase_order_item_id':source.id}}]}}
    elif mode=='delete':data={{'deleted_items':[row.id]}}
    elif mode=='netback':data={{'items':[{{'id':row.id,'quantity':2,'price':0}},changed]}}
    elif mode=='invalid':
        foreign=ns['InOrder'](order_no='HEAD-FOREIGN',warehouse=self.b.name,status='pending')
        db.session.add(foreign);db.session.flush()
        foreign_row=ns['InOrderItem'](in_order_id=foreign.id,material_id=self.material.id,quantity=2,price=0,amount=0)
        db.session.add(foreign_row);db.session.commit()
        data['items'].extend([{{'id':str(foreign_row.id),'quantity':3,'price':2}},{{'id':999999,'quantity':3,'price':2}}])
        data['deleted_items']=[str(foreign_row.id),999999]
    elif mode=='late':
        changed['quantity']=2
        data['items'].append({{'is_new':True,'code':self.material.code,'quantity':1.01,'price':0,'expiry_date':'invalid'}})
    status,result=self.completed_call(order,data)
    if mode=='late':
        self.assertEqual(status,400,result);self.assertEqual(self.completed_snapshot(order,source),before)
    else:
        self.assertEqual(status,200,result)
        if mode in ('metadata','ulp','invalid'):
            self.assertEqual((order.total_amount,row.amount,row.quantity),(head,amount,quantity))
            self.assertEqual(self.material.stock,before['stock']);self.assertEqual(source.received_quantity,1.01)
            self.assertEqual(ns['StockTransaction'].query.count(),3)
            if mode=='invalid':self.assertEqual((foreign_row.quantity,foreign_row.price,foreign_row.amount),(2,0,0))
        elif mode=='missing':self.assertEqual((order.total_amount,row.amount),(amount,amount))
        elif mode=='price':self.assertEqual((order.total_amount,row.amount),(2.02,2.02))
        elif mode=='quantity':
            self.assertEqual((order.total_amount,row.amount,row.quantity),(0,0,2))
            self.assert_stock_and_flow(22,location_on);self.assertEqual(source.received_quantity,2)
        elif mode=='delete':
            self.assertEqual(order.total_amount,0);self.assertEqual(ns['InOrderItem'].query.filter_by(in_order_id=order.id).count(),0)
            self.assert_stock_and_flow(20,location_on);self.assertEqual(source.received_quantity,0)
        elif mode=='netback':
            self.assertEqual((order.total_amount,row.amount,row.quantity),(0,0,1.01))
            self.assert_stock_and_flow(21.01,location_on);self.assertEqual(source.received_quantity,1.01)
        elif mode=='add':
            self.assertEqual(order.total_amount,9.79);self.assertEqual(row.amount,7.77)
            self.assert_stock_and_flow(22.02,location_on);self.assertEqual(source.received_quantity,2.02)
            rows=ns['InOrderItem'].query.filter_by(in_order_id=order.id).order_by(ns['InOrderItem'].id).all()
            self.assertEqual(len(rows),2);self.assertEqual([r.material_id for r in rows],[self.material.id]*2)
            order.total_amount=head;db.session.commit()
            status,result=self.completed_call(order,{{'items':[{{'id':r.id,'quantity':r.quantity,'price':r.price,'remark':'two same SKU notes'}} for r in rows]}})
            self.assertEqual(status,200,result);self.assertEqual(order.total_amount,head)
            self.assertEqual([r.amount for r in rows],[7.77,2.02])
"""

def main():
    root=Path(__file__).resolve().parents[1]
    tree=ast.parse((root/'tests/verify_audit_real_models_20261113.py').read_text(encoding='utf-8-sig'))
    original=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    order_tree=ast.parse((root/'tests/test_recorded_order_quantity_source_20261113.py').read_text(encoding='utf-8-sig'))
    constants={node.targets[0].id:ast.literal_eval(node.value) for node in order_tree.body
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)}
    for node in ast.walk(original):
        if (isinstance(node,ast.Tuple) and all(isinstance(value,ast.Constant) for value in node.elts)
                and 'services.warehouse_stock_service' in [value.value for value in node.elts]):
            node.elts.extend(ast.Constant(value=name) for name in ('services.document_return_guard','services.warehouse_identity'))
    suite=next(node for node in original.body if isinstance(node,ast.ClassDef) and node.name=='RealModelBoundaries')
    suite.body=[node for node in suite.body if not(isinstance(node,ast.FunctionDef) and node.name.startswith('test_'))]
    original.body[original.body.index(suite):original.body.index(suite)]=ast.parse(constants['SETUP']+SETUP).body
    suite.body.extend(node for node in ast.parse(constants['CASES']).body if isinstance(node,ast.FunctionDef) and node.name in {'recorded_order','order_snapshot'})
    suite.body.extend(ast.parse(HELPERS).body)
    cases=[]
    for location_on in (False,True):
        suffix='_on' if location_on else '_off'
        for linked,previous in ((False,0),(True,0),(True,10)):
            for quantity in (1.005,1.004,0.004):
                name=str(linked)+'_'+str(previous)+'_'+str(quantity).replace('.','p')+suffix
                cases.extend(ast.parse(PRODUCER.format(name=name,location_on=location_on,linked=linked,previous=previous,quantity=quantity)).body)
        for linked in (False,True):
            for quantity in (1.005,1.004,0.004):
                name='modify_'+str(linked)+'_'+str(quantity).replace('.','p')+suffix
                cases.extend(ast.parse(NORMAL.format(name=name,location_on=location_on,linked=linked,mode='modify',quantity=quantity)).body)
            cases.extend(ast.parse(NORMAL.format(name='delete_'+str(linked)+suffix,location_on=location_on,linked=linked,mode='delete',quantity=0)).body)
            for recorded in (1.005,1.01):
                for mode in ('delete','modify'):
                    name=mode+'_'+str(linked)+'_'+str(recorded).replace('.','p')+suffix
                    cases.extend(ast.parse(HISTORY.format(name=name,location_on=location_on,linked=linked,mode=mode,recorded=recorded)).body)
        for mode in ('metadata_zero','metadata_amount','metadata_rounded','mixed_rollback','ambiguous_one','ambiguous_two','invalid_metadata','dml_failure','duplicate_delete','duplicate_alias_delete','delete_and_modify','delete_and_modify_alias','repeat_modify','counter_producer_bad','counter_modify_bad','counter_delete_bad','counter_producer_tail','counter_modify_tail','counter_delete_tail'):
            cases.extend(ast.parse(EXTRA.format(name=mode+suffix,location_on=location_on,mode=mode)).body)
    ulp_cases = [('metadata', False, 0, -1), ('metadata', False, 0, 1), ('metadata', False, 4.02, -1), ('metadata', False, 4.02, 1), ('metadata', False, 7.77, -1), ('metadata', False, 7.77, 1), ('metadata', True, 0, -1), ('metadata', True, 0, 1), ('metadata', True, 4.02, -1), ('metadata', True, 4.02, 1), ('metadata', True, 7.77, -1), ('metadata', True, 7.77, 1), ('counter_metadata', True, 7.77, -1), ('counter_metadata', True, 7.77, 1), ('change', False, 0, 1), ('change', False, 4.02, 1), ('change', False, 7.77, 1), ('change', True, 0, 1), ('change', True, 4.02, 1), ('change', True, 7.77, 1), ('sequential', False, 7.77, 1), ('sequential', True, 7.77, 1), ('history', False, 7.77, 1), ('history', True, 7.77, 1)]
    assert len(ulp_cases)==24
    for location_on in (False,True):
        for index,(mode,linked,amount,direction) in enumerate(ulp_cases):
            cases.extend(ast.parse(ULP.format(name=str(index)+str(location_on),location_on=location_on,
                mode=mode,linked=linked,amount=amount,direction=direction)).body)
    head_cases = [('metadata', 0, 0), ('metadata', 0, 4.02), ('metadata', 0, 7.77), ('metadata', 9.99, 0), ('metadata', 9.99, 4.02), ('metadata', 9.99, 7.77), ('ulp', 0, 4.02), ('ulp', 0, 7.77), ('ulp', 9.99, 4.02), ('ulp', 9.99, 7.77), ('missing', None, 4.02), ('missing', None, 7.77), ('price', 0, 4.02), ('price', 9.99, 4.02), ('quantity', 0, 7.77), ('quantity', 9.99, 7.77), ('add', 0, 7.77), ('add', 9.99, 7.77), ('delete', 0, 7.77), ('delete', 9.99, 7.77), ('netback', 0, 7.77), ('netback', 9.99, 7.77), ('invalid', 0, 7.77), ('invalid', 9.99, 7.77), ('late', 0, 7.77), ('late', 9.99, 7.77)]
    assert len(head_cases)==26
    for location_on in (False,True):
        for index,(mode,head,amount) in enumerate(head_cases):
            cases.extend(ast.parse(HEAD.format(name=str(index)+str(location_on),location_on=location_on,
                mode=mode,head=head,amount=amount)).body)
    assert len(cases)==188,len(cases)
    suite.body.extend(cases)
    counts=[node for node in ast.walk(original) if isinstance(node,ast.Compare) and isinstance(node.left,ast.Call)
            and isinstance(node.left.func,ast.Attribute) and node.left.func.attr=='countTestCases']
    assert len(counts)==1 and counts[0].comparators[0].value==9
    counts[0].comparators[0]=ast.Constant(value=188)
    imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
        '<guarded-completed-inbound-quantity>','exec'),namespace)
    namespace['main']()


def test_completed_quantity_in_guarded_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
