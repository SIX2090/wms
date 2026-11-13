"""Actual BOM schemas/route AST on explicit fake ORM; no WMS app/DB/network."""
import ast
import builtins
from copy import deepcopy
from decimal import Decimal,ROUND_HALF_UP,localcontext
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from pydantic import BaseModel,ConfigDict,Field,ValidationError

ROOT=Path(__file__).resolve().parents[1]
def deny(*args,**kwargs):raise AssertionError('WMS app/DB/network/children forbidden')
class StripImports(ast.NodeTransformer):
    def visit_Import(self,node):return None
    def visit_ImportFrom(self,node):return None
def extract(rel,names):
    tree=ast.parse((ROOT/rel).read_text(encoding='utf-8-sig'));nodes=[]
    for name in names:
        found=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name]
        if not found and name.startswith('_bom_'):continue
        assert len(found)==1,name
        n=StripImports().visit(found[0]);n.decorator_list=[];nodes.append(n)
    return nodes
class Expr:
    def __eq__(self,other):return True
    def __ne__(self,other):return True

class BomHistoryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=dict(__name__='owned_bom_ast',BaseModel=BaseModel,ConfigDict=ConfigDict,Field=Field,
            ValidationError=ValidationError,math=math,Decimal=Decimal,ROUND_HALF_UP=ROUND_HALF_UP,
            localcontext=localcontext,jsonify=lambda x:x,api_error=lambda msg,code=400:({'status':'error','msg':msg},code),
            log_operation=lambda *args:None,stage_document_response=lambda *args:None,
            generate_order_no=lambda *args:'BOM-SYN-NEW',selectinload=lambda *args:None)
        nodes=extract('app/utils.py',('round_to_2_decimals','round_money_product'))
        nodes+=extract('app/app.py',('calculate_bom_cost_value','_clean_int'))
        nodes+=extract('app/routes/bom.py',('BomSaveRequest','BomHeaderRequest','_bom_line_id','_bom_recorded_values_known',
            '_bom_lock_current','_bom_begin_batch_write','_prepare_bom_items','save_bom_table','update_bom','calculate_bom_cost'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<actual-bom-fake-ORM>','exec'),cls.env)
    def setUp(self):
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            level=args[2] if len(args)>2 else kwargs.get('level',0)
            if level==0 and(name in('app','db') or name.startswith('app.')):deny()
            return original(name,*args,**kwargs)
        for p in(patch.object(builtins,'__import__',side_effect=guarded),patch.object(sqlite3,'connect',deny),
            patch.object(socket.socket,'connect',deny),patch.object(socket,'getaddrinfo',deny),patch.object(subprocess,'Popen',deny)):
            p.start();self.addCleanup(p.stop)
    def case(self,cost=4.11,quantity=3.33,unit_cost=1.2345,total=9.99):
        self.trace=[];self.next_id=100;self.lock_fail=False;self.lock_quantity=None
        class Query:
            def filter(query,*args):return query
            def filter_by(query,**kwargs):return query
            def first(query):return None
            def get_or_404(query,identity):assert identity==1;return self.order
            def delete(query):self.order.items.clear()
        class Bom(NS):id=Expr();bom_no=Expr();items=Expr();query=Query()
        class Item(NS):
            query=Query()
            def __init__(line,**values):
                defaults=dict(id=None,usage='',remark='');defaults.update(values)
                defaults['material']=self.materials.get(defaults.get('material_id'))
                super().__init__(**defaults)
        self.materials={3:NS(id=3,code='B-M',unit_id=1,price=1.2345),4:NS(id=4,code='NEW',unit_id=1,price=5)}
        self.order=Bom(id=1,bom_no='BOM-SYN-HISTORY',product_code='P',product_name='合成产品',version='V1',status='active',remark='old',total_cost=total,items=[])
        row=Item(id=10,bom_id=1,material_id=3,quantity=quantity,unit_id=1,unit_cost=unit_cost,total_cost=cost)
        self.order.items=[row];self.before=deepcopy(self.order.__dict__);self.item_model=Item
        self.payload=dict(order_id=1,order_no='BOM-SYN-HISTORY',header=dict(product_code='P',product_name='合成产品',version='V1',status='active',remark='header note'),
            items=[dict(line_id=10,material_id=3,code='B-M',quantity=str(quantity),price=unit_cost,unit_id=1,usage='',remark='line note')])
        unit=object()
        def material(raw):
            ident=raw.get('material_id');return self.materials.get(int(ident)) if ident else next((m for m in self.materials.values() if m.code==raw.get('code')),None)
        def get(model,identity):return self.order if model is Bom and identity==1 else unit if model is unit and identity==1 else None
        def add(row):
            if isinstance(row,Item):row.id=self.next_id;self.next_id+=1;self.order.items.append(row)
        def rollback():self.order.__dict__.clear();self.order.__dict__.update(deepcopy(self.before));self.trace.append('rollback')
        def stock_unit(mat,identity):
            if identity!=mat.unit_id:raise ValueError('未配置单位换算')
            return identity
        def lock(*args):
            self.trace.append('lock')
            if self.lock_quantity is not None:self.order.items[0].quantity=self.lock_quantity
            return (None,False) if self.lock_fail else(self.order,True)
        self.env.update(BOM=Bom,BOMItem=Item,Unit=unit,_material_from_payload=material,require_stock_unit=stock_unit,
            _acquire_order_write_lock=lock,g=NS(document_edit_guard=True),
            request=NS(get_json=lambda **kwargs:self.payload,is_json=True),
            app=NS(logger=NS(error=deny)),db=NS(engine=NS(dialect=NS(name='sqlite')),
                session=NS(get=get,add=add,delete=lambda row:self.order.items.remove(row),flush=lambda:None,
                    expire=lambda *args:None,commit=lambda:self.trace.append('commit'),rollback=rollback,
                    connection=lambda:NS(exec_driver_sql=lambda sql:self.trace.append(sql)))))
        return row
    def post(self):
        result=self.env['save_bom_table']();return result if isinstance(result,tuple) else(result,200)
    def snapshot(self):return self.order.total_cost,tuple(sorted((r.id,r.material_id,r.unit_id,r.quantity,r.unit_cost,r.total_cost) for r in self.order.items))
    def test_revaluation_then_note_save_keeps_original_unit_cost_and_amount(self):
        self.case();self.assertEqual(self.env['calculate_bom_cost_value'](self.order),4.11)
        before=self.snapshot();self.payload['items'][0].update(saved_amount=999,total_cost=888)
        self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before);self.assertEqual(self.order.items[0].remark,'line note')
    def test_known_zero_and_legacy_amounts_not_recomputed_for_metadata(self):
        for amount in(0,4.02,7.77):
            self.case(amount,1.15,3.5);before=self.snapshot();self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before)
    def test_unchanged_quantity_precision_survives(self):
        for quantity in(1.2345,.0001):
            self.case(7.77,quantity,3.56789);before=self.snapshot();self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before)
    def test_explicit_price_or_quantity_change_keeps_other_known_component(self):
        for field,value,qty,price,cost in(('quantity','2',2,1.2345,2.47),('price','0',3.33,0,0)):
            self.case();self.payload['items'][0][field]=value;self.assertEqual(self.post()[1],200)
            row=self.order.items[0];self.assertEqual((row.id,row.quantity,row.unit_cost,row.total_cost),(10,qty,price,cost));self.assertEqual(self.order.total_cost,cost)
    def test_two_same_material_rows_are_owned_by_id_not_sku_or_order(self):
        self.case();other=self.item_model(id=11,bom_id=1,material_id=3,quantity=2.12345,unit_id=1,unit_cost=3.56789,total_cost=7.77)
        self.order.items.append(other);before=self.snapshot()
        self.payload['items']=[dict(line_id=11,material_id=3,code='B-M',quantity='2.12345',unit_id=1,price=3.56789,remark='second'),self.payload['items'][0]]
        self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before)
        self.assertEqual({r.id:r.remark for r in self.order.items},{10:'line note',11:'second'})
    def test_bom_line_id_rejects_foreign_duplicate_bad_and_changed_material(self):
        for value in(11,True,0,'1e1','9'*20):
            self.case();before=self.snapshot();self.payload['items'][0]['line_id']=value;self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
        self.case();before=self.snapshot();self.payload['items'].append(dict(self.payload['items'][0]));self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
        self.case();before=self.snapshot();self.payload['items'][0].update(material_id=4,code='NEW');self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
    def test_modern_edit_requires_actual_revision_guard(self):
        self.case();before=self.snapshot();self.env['g']=NS(document_edit_guard=False);self.assertEqual(self.post()[1],409);self.assertEqual(self.snapshot(),before)
    def test_known_head_zero_and_missing_head_are_distinct(self):
        for total,expected in((0,0),(None,4.11)):
            self.case(total=total);self.assertEqual(self.post()[1],200);self.assertEqual(self.order.total_cost,expected)
    def test_later_invalid_row_rolls_back_prior_metadata_and_finance(self):
        self.case();before=self.snapshot();self.payload['items'][0]['quantity']='2'
        self.payload['items'].append(dict(line_id=None,material_id=4,code='NEW',quantity='0',price='3',unit_id=1))
        self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before);self.assertNotIn('commit',self.trace)
    def test_legacy_without_ids_explicitly_replaces_using_existing_two_places(self):
        self.case();self.payload['items'][0].pop('line_id');self.assertEqual(self.post()[1],200)
        row=self.order.items[0];self.assertNotEqual(row.id,10);self.assertEqual((row.unit_cost,row.total_cost),(1.23,4.1))
    def test_unknown_null_cost_keeps_previous_legacy_computation_not_a_new_policy(self):
        self.case(unit_cost=None,cost=7.77);self.assertEqual(self.post()[1],200)
        row=self.order.items[0];self.assertEqual((row.unit_cost,row.total_cost),(1.23,4.1))
    def test_existing_header_only_route_preserves_all_finance(self):
        self.case();before=self.snapshot();self.payload={'remark':'only head'}
        result=self.env['update_bom'](1);self.assertEqual(result['status'],'success');self.assertEqual(self.snapshot(),before)
    def test_explicit_recalculation_locks_and_uses_current_material_price(self):
        self.case();self.materials[3].price=3.5;self.lock_quantity=2
        result=self.env['calculate_bom_cost'](1);self.assertEqual(result['status'],'success')
        self.assertIn('lock',self.trace);self.assertEqual((self.order.items[0].quantity,self.order.items[0].unit_cost,self.order.total_cost),(2,3.5,7))
    def test_calculate_bom_cost_value(self):
        import inspect
        for recorded in (0,4.02,7.77):
            self.case(quantity=1.15,unit_cost=3.5,cost=recorded)
            added=self.item_model(id=11,bom_id=1,material_id=4,quantity=2,unit_id=1,unit_cost=5,total_cost=10)
            self.order.items.append(added)
            fn=self.env['calculate_bom_cost_value']
            kw={'preserve_recorded_costs':True} if 'preserve_recorded_costs' in inspect.signature(fn).parameters else {}
            self.assertEqual(fn(self.order,refresh_unit_cost=False,**kw),recorded+10)
            self.assertEqual(self.order.items[0].total_cost,recorded)
            self.order.items[0].unit_id=99
            with self.assertRaisesRegex(ValueError,'单位'):fn(self.order,refresh_unit_cost=False,**kw)
    def test_recorded_preservation_does_not_change_explicit_revaluation_or_unknown_null(self):
        import inspect
        self.case(quantity=1.15,unit_cost=3.5,cost=7.77)
        fn=self.env['calculate_bom_cost_value']
        kw={'preserve_recorded_costs':True} if 'preserve_recorded_costs' in inspect.signature(fn).parameters else {}
        self.materials[3].price=2
        self.assertEqual(fn(self.order,refresh_unit_cost=True,**kw),2.3)
        self.order.items[0].unit_cost=None;self.order.items[0].total_cost=7.77
        self.assertEqual(fn(self.order,refresh_unit_cost=False,**kw),0)
        self.assertEqual((self.order.items[0].unit_cost,self.order.items[0].total_cost),(0,0))
    def test_bom_guard_registration_and_new_requisition_intent(self):
        tree=ast.parse((ROOT/'app/services/document_edit_guard.py').read_text(encoding='utf-8-sig'));values={}
        for node in tree.body:
            if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
                name=node.targets[0].id
                if name=='DOCUMENTS':values[name]=ast.literal_eval(node.value)
                elif name in('EDIT_ENDPOINTS','NEW_DOCUMENT_INTENTS'):values[name]=ast.literal_eval(node.value.args[0])
        self.assertEqual(values['DOCUMENTS'].get('bom'),('BOM','items',None,None))
        self.assertTrue({'save_bom_table','update_bom','add_bom_item','add_bom_item_alias','delete_bom_item','delete_bom_item_alias'}<=values['EDIT_ENDPOINTS'])
        self.assertIn('create_requisition_from_bom',values['NEW_DOCUMENT_INTENTS'])
        self.assertNotIn('calculate_bom_cost',values['EDIT_ENDPOINTS'])
    def test_bulk_lock_is_before_any_import_or_batch_delete_business_read(self):
        tree=ast.parse((ROOT/'app/routes/bom.py').read_text(encoding='utf-8-sig'))
        for name in('import_bom','batch_delete_bom'):
            fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
            locks=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='_bom_begin_batch_write']
            self.assertEqual(len(locks),1,name)
            writes=[n.lineno for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id in('bom','existing_item') for t in n.targets)]
            if writes:self.assertLess(locks[0].lineno,min(writes))

if __name__=='__main__':unittest.main(verbosity=2)
