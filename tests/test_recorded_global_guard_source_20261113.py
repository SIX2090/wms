"""Global primitive guard: actual models/functions, new guarded memory only."""
import ast
import os
from pathlib import Path
import subprocess
import sys


EXTRA_SETUP=r'''
from flask_login import LoginManager, current_user as real_current_user, login_user
global_source_login=LoginManager(app)
@global_source_login.user_loader
def global_source_user_loader(user_id):
    return db.session.get(ns['User'],int(user_id))
'''

HELPERS=r'''
def set_other_warehouse(self,quantity,material=None):
    material=material or self.material
    row=ns['StockTransaction'].query.filter_by(material_id=material.id,warehouse_id=self.b.id,
        reference_type='material_initial').one()
    row.quantity=quantity
    material.stock=math.fsum(row.quantity for row in ns['StockTransaction'].query.filter_by(material_id=material.id))
    if ns['location_management_enabled']():
        ns['LocationInventory'].query.filter_by(material_id=material.id,warehouse_id=self.b.id).one().quantity=quantity
    db.session.commit()

def real_logged_helper(self,order):
    with app.test_request_context('/synthetic-global',method='POST'):
        login_user(self.user)
        with patch.dict(ns,current_user=real_current_user):
            self.assertTrue(real_current_user.is_authenticated)
            return ns['_reverse_recorded_order_stock'](order)

def real_logged_route(self,order,batch=False,kind='in'):
    with app.test_request_context('/synthetic-global',method='POST',json={'ids':[order.id]}):
        login_user(self.user)
        with patch.dict(ns,request=actual_request,current_user=real_current_user):
            result=ns['batch_revert_in_order']() if batch else ns['revert_'+kind+'_order'](order.id)
    result=result[0] if isinstance(result,tuple) else result
    return result.get_json() if hasattr(result,'get_json') else result

def all_global_state(self):
    return (self.order_snapshot(),
        [(row.id,row.stock) for row in ns['Material'].query.order_by(ns['Material'].id)],
        ns['OperationLog'].query.count(),ns['OperationAudit'].query.count())

def add_second_recorded_material(self,order):
    second=ns['Material'](code='SYN-GLOBAL-SECOND',name='合成第二物料',stock=21.005)
    db.session.add(second)
    db.session.flush()
    db.session.add(ns['InOrderItem'](in_order_id=order.id,material_id=second.id,quantity=1.005,price=0,amount=0))
    for warehouse,quantity,typ,ref in ((self.a,1.005,'in','in_order'),
        (self.a,10,'opening','material_initial'),(self.b,10,'opening','material_initial')):
        db.session.add(ns['StockTransaction'](material_id=second.id,warehouse_id=warehouse.id,
            location=warehouse.name,quantity=quantity,transaction_type=typ,
            reference_type=ref,reference_id=order.id if ref=='in_order' else second.id))
    if ns['location_management_enabled']():
        db.session.add_all([
            ns['LocationInventory'](material_id=second.id,warehouse_id=self.a.id,location='SAME',quantity=11.005),
            ns['LocationInventory'](material_id=second.id,warehouse_id=self.b.id,location='SAME',quantity=10)])
    db.session.commit()
    return second
'''

CASE=r'''
def test_global_{name}(self):
    location_on={location_on}
    mode={mode!r}
    if mode=='out_improves':
        order,_=self.recorded_order('out',location_on=location_on)
        self.set_other_warehouse(-30)
        other_before=ns['StockTransaction'].query.filter_by(warehouse_id=self.b.id).one().quantity
        self.assertEqual(self.real_logged_helper(order),(True,''))
        db.session.commit()
        self.assertAlmostEqual(self.material.stock,-20,places=12)
        self.assertEqual(ns['StockTransaction'].query.filter_by(warehouse_id=self.b.id).one().quantity,other_before)
    elif mode in ('normalized_route','ordinary_route','normalized_batch'):
        order,_=self.recorded_order('in',location_on=location_on,quantities=[1.01] if mode=='ordinary_route' else [1.005],
            recorded=[1.01])
        self.set_other_warehouse(-10.51)
        before=self.all_global_state()
        payload=self.real_logged_route(order,batch=mode=='normalized_batch')
        if mode=='normalized_batch':
            self.assertEqual(payload['status'],'success',payload)
            self.assertEqual(payload['reverted'],0,payload)
        else:
            self.assertEqual(payload['status'],'error',payload)
        self.assertEqual(self.all_global_state(),before)
        self.assertEqual(order.status,'completed')
    elif mode=='tail':
        order,_=self.recorded_order('in',location_on=location_on)
        self.set_other_warehouse(-10)
        self.material.stock=math.nextafter(1.005,float('-inf'))
        db.session.commit()
        self.assertEqual(self.real_logged_helper(order),(True,''))
        db.session.commit()
        self.assertLessEqual(abs(self.material.stock),8*math.ulp(1.005))
        self.assertEqual(ns['StockTransaction'].query.filter_by(warehouse_id=self.b.id).one().quantity,-10)
    elif mode in ('multi_global','multi_dml'):
        order,_=self.recorded_order('in',location_on=location_on)
        second=self.add_second_recorded_material(order)
        if mode=='multi_global':
            self.set_other_warehouse(-10.505,second)
        before=self.all_global_state()
        hit=[]
        def fail_later_material(_connection,_cursor,statement,parameters,_context,_executemany):
            if statement.lstrip().upper().startswith('UPDATE MATERIAL'):
                hit.append(parameters)
                if len(hit)==2:
                    raise RuntimeError('owned synthetic later material UPDATE failure')
        if mode=='multi_dml':
            event.listen(db.engine,'before_cursor_execute',fail_later_material)
        try:
            payload=self.real_logged_route(order,batch=False)
        finally:
            if mode=='multi_dml':
                event.remove(db.engine,'before_cursor_execute',fail_later_material)
        self.assertEqual(payload['status'],'error',payload)
        self.assertEqual(self.all_global_state(),before)
        self.assertEqual(order.status,'completed')
        if mode=='multi_dml':
            self.assertEqual(len(hit),2)
    else:
        order,_=self.recorded_order('in',location_on=location_on)
        self.set_other_warehouse(-10.505)
        before=self.all_global_state()
        if mode=='allow_negative':
            ns['allow_negative_stock']=lambda:True
            self.assertEqual(self.real_logged_helper(order),(True,''))
            db.session.commit()
            self.assertAlmostEqual(self.material.stock,-0.505,places=12)
            self.assertEqual(ns['StockTransaction'].query.filter_by(warehouse_id=self.b.id).one().quantity,-10.505)
        elif mode=='raw_helper_refuse':
            result=self.real_logged_helper(order)
            self.assertIsNotNone(result)
            self.assertFalse(result[0],result)
            self.assertIn('全局',result[1])
            self.assertEqual(self.all_global_state(),before)
            db.session.rollback()
        elif mode in ('raw_single','raw_batch'):
            payload=self.real_logged_route(order,batch=mode=='raw_batch')
            if mode=='raw_batch':
                self.assertEqual(payload['status'],'success',payload)
                self.assertEqual(payload['reverted'],0,payload)
            else:
                self.assertEqual(payload['status'],'error',payload)
            self.assertIn('全局',payload['msg'])
            self.assertEqual(self.all_global_state(),before)
            self.assertEqual(order.status,'completed')
        else:
            raise AssertionError('Unknown global scenario')
'''


def main():
    base=Path(__file__).with_name('test_recorded_order_quantity_source_20261113.py')
    tree=ast.parse(base.read_text(encoding='utf-8-sig'))
    original=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='main')
    extra=HELPERS
    cases=0
    for location_on in (False,True):
        for mode in ('raw_helper_refuse','raw_single','raw_batch','normalized_route','ordinary_route',
                     'allow_negative','out_improves','tail','multi_global','multi_dml','normalized_batch'):
            # Batch normalized fallback is an original primitive control too.
            rendered=CASE.format(name=mode+('_on' if location_on else '_off'),mode=mode,
                                 location_on=location_on)
            extra+=rendered
            cases+=1
    assert cases==22
    replacements={106:0,115:0}
    for node in ast.walk(original):
        if isinstance(node,ast.Constant) and type(node.value) is int and node.value in replacements:
            old=node.value
            replacements[old]+=1
            node.value=old+cases
    assert replacements=={106:1,115:1},replacements
    imports=[node for node in tree.body if isinstance(node,(ast.Import,ast.ImportFrom))]
    assignments=[node for node in tree.body if isinstance(node,ast.Assign)]
    namespace={'__file__':__file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports,*assignments],type_ignores=[])),
                 '<global-proof-definitions>','exec'),namespace)
    namespace['SETUP']+=EXTRA_SETUP
    namespace['CASES']+=extra
    exec(compile(ast.fix_missing_locations(ast.Module(body=[original],type_ignores=[])),
                 '<guarded-global-primitive-proof>','exec'),namespace)
    namespace['main']()


def test_global_guard_in_explicit_memory_child():
    env={key:os.environ[key] for key in ('SYSTEMROOT','WINDIR') if key in os.environ}
    result=subprocess.run([sys.executable,'-I','-S','-B','-X','utf8',__file__],env=env,
        capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert result.returncode==0,result.stdout+result.stderr


if __name__=='__main__':
    main()
