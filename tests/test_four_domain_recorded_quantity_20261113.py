"""Four real document types: source models/routes in guarded fresh memory.

This verifies actual model/function bodies, not full WMS app integration.
The reused worker blocks WMS imports, file databases, network and children
before dependencies load; its only SQLite creator is literal fresh :memory:.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys


EXTRA_SETUP = r'''
from flask_login import LoginManager, login_user, current_user as actual_login_user
login_manager=LoginManager(app)
login_manager.user_loader(lambda ident: db.session.get(ns['User'],int(ident)))
ns.update(current_user=actual_login_user,request=actual_request)
for filename,names in [('requisition.py',('revert_requisition',)),
                       ('after_sale_out.py',('revert_after_sale_out_order',)),
                       ('subcontract.py',('revert_subcontract_issue','revert_subcontract_receive'))]:
    for name in names:extract('app/routes/'+filename,name)
'''

CASES = r'''
def domain_definition(self,domain):
    return {
      'requisition':('ProductionRequisition','req_no','ProductionRequisitionItem','requisition_id','requisition','requisition',-1,'revert_requisition','revert_requisition'),
      'aftersale':('AfterSaleOutOrder','order_no','AfterSaleOutOrderItem','after_sale_out_order_id','after_sale_out_order','after_sale_out',-1,'revert_after_sale_out','revert_after_sale_out_order'),
      'issue':('SubcontractIssue','issue_no','SubcontractIssueItem','issue_id','subcontract_issue','subcontract_issue',-1,'revert_subcontract_issue','revert_subcontract_issue'),
      'receive':('SubcontractReceive','receive_no','SubcontractReceiveItem','receive_id','subcontract_receive','subcontract_receive',1,'revert_subcontract_receive','revert_subcontract_receive'),
    }[domain]

def domain_make(self,domain,location_on,quantities=None,recorded=None):
    model,number,item_model,fk,ref,origin,sign,inverse,route=self.domain_definition(domain)
    ns['location_management_enabled']=lambda:location_on
    ns['allow_negative_stock']=lambda:False
    ns['allow_negative_location_stock']=lambda:False
    quantities=[1.005] if quantities is None else quantities
    values={number:'SYN-FOUR-HISTORY','status':'completed','warehouse':self.a.name,'location':'SAME'}
    if domain=='aftersale':values.update(total_amount=123.45,customer='合成客户',reason='原售后原因')
    order=ns[model](**values);db.session.add(order);db.session.flush()
    for quantity in quantities:
        fields={fk:order.id,'material_id':self.material.id,'quantity':quantity}
        if domain=='aftersale':fields.update(price=3.5,amount=7.77,contract_no='LINE-CONTRACT',project_name='行工程')
        db.session.add(ns[item_model](**fields))
    self.txn(self.a.id,10,'material_initial',self.material.id)
    self.txn(self.b.id,10,'material_initial',self.material.id)
    values=[sign*q for q in quantities] if recorded is None else recorded
    rows=[]
    for quantity in values:
        row=self.txn(self.a.id,quantity,ref,order.id)
        row.transaction_type=origin if quantity*sign>=0 else inverse
        row.location=self.a.name;rows.append(row)
    self.material.stock=20+math.fsum(values)
    if location_on:
        db.session.add_all([
            ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,location='SAME',quantity=10+math.fsum(values)),
            ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.b.id,location='SAME',quantity=10)])
    db.session.commit()
    return order,rows

def domain_snapshot(self):
    return ([(r.id,r.stock) for r in ns['Material'].query.order_by(ns['Material'].id)],
            [(r.id,r.quantity,r.transaction_type,r.reference_type,r.reference_id,r.warehouse_id,r.location)
             for r in ns['StockTransaction'].query.order_by(ns['StockTransaction'].id)],
            [(r.id,r.quantity,r.warehouse_id,r.location) for r in ns['LocationInventory'].query.order_by(ns['LocationInventory'].id)])

def domain_route(self,domain,order):
    route=self.domain_definition(domain)[-1]
    with app.test_request_context('/synthetic-only',method='POST'):
        login_user(self.user)
        result=ns[route](order.id)
    result=result[0] if isinstance(result,tuple) else result
    return result.get_json() if hasattr(result,'get_json') else result

def domain_success(self,domain,order,original,expected=20):
    ref=self.domain_definition(domain)[4]
    original_ids=[row.id for row in original]
    financial=(order.total_amount,order.customer,order.reason,
               [(r.id,r.quantity,r.price,r.amount,r.contract_no,r.project_name) for r in order.items]) if domain=='aftersale' else None
    payload=self.domain_route(domain,order)
    self.assertEqual(payload['status'],'success',payload)
    self.assertEqual(order.status,'pending')
    self.assertAlmostEqual(self.material.stock,expected,places=12)
    self.assertAlmostEqual(math.fsum(r.quantity for r in ns['StockTransaction'].query),expected,places=12)
    self.assertAlmostEqual(math.fsum(r.quantity for r in ns['StockTransaction'].query.filter_by(reference_type=ref,reference_id=order.id)),0,places=12)
    for ident in original_ids:self.assertIsNotNone(db.session.get(ns['StockTransaction'],ident))
    if ns['location_management_enabled']():
        for row in ns['LocationInventory'].query.all():self.assertAlmostEqual(row.quantity,10,places=12)
    if domain=='aftersale':
        self.assertEqual((order.total_amount,order.customer,order.reason,
                          [(r.id,r.quantity,r.price,r.amount,r.contract_no,r.project_name) for r in order.items]),financial)
    return payload

def domain_refusal(self,domain,order,message):
    before=self.domain_snapshot()
    payload=self.domain_route(domain,order)
    self.assertEqual(payload['status'],'error',payload)
    self.assertIn(message,payload['msg'])
    self.assertEqual(order.status,'completed')
    self.assertEqual(self.domain_snapshot(),before)

def domain_case(self,domain,location_on,mode):
    sign=self.domain_definition(domain)[6]
    if mode in ('raw','normalized','ordinary','same_sku_raw','per_line_normalized','tail'):
        quantities=([1.005,2.005] if mode=='same_sku_raw' else [1.005,1.005] if mode=='per_line_normalized'
                    else [.1,.2] if mode=='tail' else [1.01] if mode=='ordinary' else [1.005])
        recorded=([sign*1.01] if mode=='normalized' else [sign*2.02] if mode=='per_line_normalized'
                  else [sign*(.1+.2)] if mode=='tail' else None)
        order,rows=self.domain_make(domain,location_on,quantities,recorded)
        self.domain_success(domain,order,rows)
    elif mode in ('wrong_phase','unknown_fk','header_conflict','mismatch','missing_bin','bin_mismatch'):
        order,rows=self.domain_make(domain,location_on)
        if mode=='wrong_phase':rows[0].transaction_type='in'
        elif mode=='unknown_fk':rows[0].warehouse_id=None
        elif mode=='header_conflict':order.warehouse=self.b.name
        elif mode=='mismatch':rows[0].quantity=sign*1.004
        elif mode=='missing_bin':order.location='';rows[0].location=''
        elif mode=='bin_mismatch':ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().quantity+=.001
        db.session.commit()
        message={'wrong_phase':'流水阶段无法证明','unknown_fk':'原仓归属','header_conflict':'头仓库',
                 'mismatch':'净额不一致','missing_bin':'原库位缺失','bin_mismatch':'库位账与流水不一致'}[mode]
        self.domain_refusal(domain,order,message)
    elif mode=='repeat':
        order,rows=self.domain_make(domain,location_on)
        self.domain_success(domain,order,rows)
        before=self.domain_snapshot();payload=self.domain_route(domain,order)
        self.assertEqual(payload['status'],'error',payload)
        self.assertEqual(self.domain_snapshot(),before)
    elif mode in ('closed_cycle','residue_cycle'):
        recorded=[sign*2.005,-sign*(2.005 if mode=='closed_cycle' else 1.005),sign*1.005]
        order,rows=self.domain_make(domain,location_on,recorded=recorded)
        if mode=='residue_cycle':self.domain_refusal(domain,order,'此前完成周期')
        elif location_on:self.domain_refusal(domain,order,'闭合历史')
        else:self.domain_success(domain,order,rows)
    elif mode=='rollback_dml':
        order,rows=self.domain_make(domain,location_on)
        before=self.domain_snapshot();hit=[]
        target='UPDATE LOCATION_INVENTORY' if location_on else 'UPDATE MATERIAL'
        def fail(_connection,_cursor,statement,_parameters,_context,_executemany):
            if statement.lstrip().upper().startswith(target):hit.append(True);raise RuntimeError('owned synthetic four-domain DML failure')
        event.listen(db.engine,'before_cursor_execute',fail)
        try:payload=self.domain_route(domain,order)
        finally:event.remove(db.engine,'before_cursor_execute',fail)
        self.assertEqual(hit,[True]);self.assertEqual(payload['status'],'error',payload)
        self.assertEqual(order.status,'completed');self.assertEqual(self.domain_snapshot(),before)
    elif mode=='float_tiny':
        order,rows=self.domain_make(domain,False,quantities=[1e-20])
        self.domain_refusal(domain,order,'Float可逆精度')
    elif mode=='global_negative':
        order,rows=self.domain_make(domain,False)
        self.txn(self.b.id,-25,'synthetic-consumption',99)
        self.material.stock-=25;db.session.commit()
        if sign>0:self.domain_refusal(domain,order,'全局库存不足')
        else:self.domain_success(domain,order,rows,expected=-5)
    elif mode=='later_invalid':
        order,rows=self.domain_make(domain,False)
        model,number,item_model,fk,*_=self.domain_definition(domain)
        material=ns['Material'](code='SYN-LATER',name='合成后项',stock=0)
        db.session.add(material);db.session.flush()
        fields={fk:order.id,'material_id':material.id,'quantity':2.005}
        if domain=='aftersale':fields.update(price=0,amount=0)
        db.session.add(ns[item_model](**fields));db.session.commit()
        self.domain_refusal(domain,order,'净额不一致')
    elif mode in ('legacy_bin_fallback','renamed_header'):
        order,rows=self.domain_make(domain,location_on)
        if mode=='legacy_bin_fallback':
            order.location=''
            ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one().location=self.a.name
        else:order.warehouse='SYN-OLD-UNRESOLVED-NAME'
        db.session.commit();self.domain_success(domain,order,rows)
    elif mode=='negative_bin':
        order,rows=self.domain_make(domain,True)
        position=ns['LocationInventory'].query.filter_by(warehouse_id=self.a.id).one()
        position.quantity=.5 if sign>0 else -5
        other=ns['LocationInventory'](material_id=self.material.id,warehouse_id=self.a.id,location='OTHER',
                                      quantity=10+sign*1.005-position.quantity)
        db.session.add(other);db.session.commit()
        if sign>0:self.domain_refusal(domain,order,'原库位库存不足')
        else:
            payload=self.domain_route(domain,order)
            self.assertEqual(payload['status'],'success',payload)
            self.assertAlmostEqual(position.quantity,-3.995,places=12)
            self.assertAlmostEqual(other.quantity,13.995,places=12)
            self.assertAlmostEqual(self.material.stock,20,places=12)
            self.assertAlmostEqual(math.fsum(r.quantity for r in ns['StockTransaction'].query),20,places=12)
    elif mode=='multiple_materials':
        order,rows=self.domain_make(domain,location_on)
        model,number,item_model,fk,ref,origin,sign,inverse,route=self.domain_definition(domain)
        material=ns['Material'](code='SYN-SECOND',name='合成第二物料',stock=20+sign*2.005)
        db.session.add(material);db.session.flush()
        fields={fk:order.id,'material_id':material.id,'quantity':2.005}
        if domain=='aftersale':fields.update(price=3.5,amount=4.02)
        db.session.add(ns[item_model](**fields))
        for warehouse,q,reference,ident,stage in ((self.a,10,'material_initial',material.id,'in'),
                (self.b,10,'material_initial',material.id,'in'),(self.a,sign*2.005,ref,order.id,origin)):
            db.session.add(ns['StockTransaction'](material_id=material.id,warehouse_id=warehouse.id,
                quantity=q,reference_type=reference,reference_id=ident,transaction_type=stage,location=warehouse.name))
        if location_on:
            db.session.add_all([ns['LocationInventory'](material_id=material.id,warehouse_id=self.a.id,location='SAME',quantity=10+sign*2.005),
                               ns['LocationInventory'](material_id=material.id,warehouse_id=self.b.id,location='SAME',quantity=10)])
        db.session.commit()
        payload=self.domain_route(domain,order);self.assertEqual(payload['status'],'success',payload)
        for row in (self.material,material):
            self.assertAlmostEqual(row.stock,20,places=12)
            self.assertAlmostEqual(math.fsum(t.quantity for t in ns['StockTransaction'].query.filter_by(material_id=row.id)),20,places=12)
        if location_on:
            for row in ns['LocationInventory'].query:self.assertAlmostEqual(row.quantity,10,places=12)
    elif mode=='upstream':
        order,rows=self.domain_make(domain,location_on)
        if domain in ('issue','receive'):
            source=ns['SubcontractOrder'](order_no='SYN-UPSTREAM',status='processing',warehouse=self.a.name,total_amount=77.77,remark='合同来源')
            key='subcontract_order_id'
        elif domain=='requisition':
            source=ns['BOM'](bom_no='SYN-BOM',product_code='P',product_name='合成产品',status='active',total_cost=4.02,remark='原BOM')
            key='bom_id'
        else:
            source=ns['OutOrder'](order_no='SYN-UPSTREAM',status='completed',warehouse=self.a.name,total_amount=88.88,remark='原来源')
            key='source_out_order_id'
        db.session.add(source);db.session.flush();setattr(order,key,source.id);db.session.commit()
        before={column.key:getattr(source,column.key) for column in source.__table__.columns}
        self.domain_success(domain,order,rows)
        self.assertEqual({column.key:getattr(source,column.key) for column in source.__table__.columns},before)
        self.assertEqual(getattr(order,key),source.id)
        self.assertEqual(ns['DocumentPushLine'].query.count(),0)
    else:raise AssertionError('Unknown explicit scenario')

def test_private_helper_keeps_single_order_capability_and_rejects_unregistered_type(self):
    import inspect
    self.assertEqual(list(inspect.signature(ns['_reverse_recorded_order_stock']).parameters),['order'])
    self.assertNotIn('raw',inspect.signature(ns['apply_stock_delta']).parameters)
    result=ns['_reverse_recorded_order_stock'](types.SimpleNamespace(status='completed'))
    self.assertFalse(result[0]);self.assertIn('不支持',result[1])
'''


def main():
    root=Path(__file__).resolve().parent
    harness=root/'verify_audit_real_models_20261113.py'
    tree=ast.parse(harness.read_text(encoding='utf-8-sig'))
    original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    existing=ast.parse((root/'test_recorded_order_quantity_source_20261113.py').read_text(encoding='utf-8-sig'))
    setup=next(ast.literal_eval(n.value) for n in existing.body if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id=='SETUP' for t in n.targets))
    for node in ast.walk(original):
        if (isinstance(node,ast.Tuple) and all(isinstance(value,ast.Constant) for value in node.elts)
                and 'services.warehouse_stock_service' in [value.value for value in node.elts]):
            node.elts.extend(ast.Constant(value=name) for name in ('services.document_return_guard','services.warehouse_identity'))
    suite=next(n for n in original.body if isinstance(n,ast.ClassDef) and n.name=='RealModelBoundaries')
    original.body[original.body.index(suite):original.body.index(suite)]=ast.parse(setup+EXTRA_SETUP).body
    # This is an additional suite, not a replacement for the existing 115-case
    # ordinary in/out regression, which is run separately unchanged.
    suite.body=[n for n in suite.body if isinstance(n,ast.FunctionDef) and n.name in ('setUp','tearDown','txn')]
    suite.body.extend(ast.parse(CASES).body)
    cases=[]
    common=('raw','normalized','ordinary','same_sku_raw','per_line_normalized','wrong_phase','unknown_fk',
            'header_conflict','mismatch','repeat','rollback_dml','closed_cycle','residue_cycle','multiple_materials','upstream')
    for domain in ('requisition','aftersale','issue','receive'):
        for location_on in (False,True):
            for mode in common:cases.append((domain,location_on,mode))
        cases.extend((domain,location_on,mode) for location_on,mode in (
            (True,'missing_bin'),(True,'bin_mismatch'),(False,'float_tiny'),
            (False,'global_negative'),(False,'later_invalid'),(False,'tail'),
            (True,'legacy_bin_fallback'),(False,'renamed_header'),(True,'negative_bin')))
    assert len(cases)==156 and len(set(cases))==156
    for domain,location_on,mode in cases:
        name='test_'+domain+'_'+mode+('_on' if location_on else '_off')
        suite.body.extend(ast.parse(f'def {name}(self):\n    self.domain_case({domain!r},{location_on!r},{mode!r})\n').body)
    counts=[n for n in ast.walk(original) if isinstance(n,ast.Compare) and isinstance(n.left,ast.Call)
            and isinstance(n.left.func,ast.Attribute) and n.left.func.attr=='countTestCases']
    assert len(counts)==1 and counts[0].comparators[0].value==9
    counts[0].comparators[0]=ast.Constant(value=len(cases)+1)
    imports=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,original],type_ignores=[])),
                 '<guarded-four-domain-recorded-quantity>','exec'),namespace)
    namespace['main']()


def test_four_domain_in_guarded_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
                          capture_output=True,text=True,encoding='utf-8',timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':main()
