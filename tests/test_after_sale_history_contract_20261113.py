"""Actual save AST with explicit fake ORM; current non-NULL model declarations checked."""
import ast
import builtins
from copy import deepcopy
from datetime import date,datetime
from decimal import Decimal,ROUND_HALF_UP,localcontext
import json
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType,SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def deny(*args,**kwargs):raise AssertionError('app, DB, network and children forbidden')
def extract(rel,names):
    tree=ast.parse((ROOT/rel).read_text(encoding='utf-8-sig'));nodes=[]
    for name in names:
        found=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
        if not found and name.startswith('_after_sale_edit_'):continue
        assert len(found)==1,name
        n=found[0];n.decorator_list=[]
        n.body=[s for s in n.body if not(isinstance(s,ast.ImportFrom) and s.module=='app')]
        nodes.append(n)
    return nodes

class AfterSaleHistoryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree=ast.parse((ROOT/'app/models/documents.py').read_text(encoding='utf-8-sig'))
        model=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='AfterSaleOutOrderItem')
        for field in('quantity','price','amount'):
            declaration=next(n for n in model.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==field for t in n.targets))
            assert any(k.arg=='nullable' and isinstance(k.value,ast.Constant) and k.value.value is False for k in declaration.value.keywords),field
        cls.env=dict(date=date,datetime=datetime,Decimal=Decimal,ROUND_HALF_UP=ROUND_HALF_UP,localcontext=localcontext,json=json,math=math,
            jsonify=lambda x:x,api_error=lambda message,status=400:({'status':'error','msg':message},status),
            log_operation=lambda *args:None,generate_order_no=lambda *args:'ASO-SYN-NEW',
            assert_warehouse_active=lambda *args,**kwargs:(True,''),location_management_enabled=lambda:False,
            get_default_warehouse=lambda:NS(id=5,name='合成仓'),validate_inventory_warehouse=lambda *args:(NS(id=5,name='合成仓'),''))
        nodes=extract('app/utils.py',('parse_float_value','parse_date_value','round_to_2_decimals','round_money_product'))
        nodes+=extract('app/app.py',('_clean_int',))
        nodes+=extract('app/routes/after_sale_out.py',('_after_sale_edit_line_id','add_after_sale_out_order'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<actual-aftersale-save-explicit-fake-ORM>','exec'),cls.env)
    def setUp(self):
        real_import=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='app' or name.startswith('app.'):deny()
            return real_import(name,*args,**kwargs)
        login=ModuleType('flask_login');login.current_user=NS(id=9)
        for guard in(patch.object(builtins,'__import__',side_effect=guarded),patch.object(sqlite3,'connect',deny),
            patch.object(sqlite3.dbapi2,'connect',deny),patch.object(socket.socket,'connect',deny),patch.object(socket,'getaddrinfo',deny),
            patch.object(subprocess,'Popen',deny),patch.dict(sys.modules,{'flask_login':login})):
            guard.start();self.addCleanup(guard.stop)
    def case(self,amount=4.02,quantity=1.15,price=3.5):
        self.active_push=False;self.next_id=100;self.commits=0
        class Query:
            def filter_by(query,**kwargs):return query
            def first(query):return None
        class Order(NS):
            query=Query()
            def __init__(order,**values):
                defaults=dict(id=None,items=[],total_amount=0);defaults.update(values);super().__init__(**defaults)
        class Item(NS):
            def __init__(line,**values):
                defaults=dict(id=None,contract_id=None,contract_no=None,project_name=None)
                defaults.update(values);super().__init__(**defaults)
        self.order=Order(id=1,order_no='ASO-SYN-HISTORY',status='pending',total_amount=amount,items=[])
        line=Item(id=10,after_sale_out_order_id=1,material_id=3,quantity=quantity,price=price,amount=amount,
            contract_id=7,contract_no='SYN-C',project_name='合成工程',remark='old line')
        self.order.items=[line];self.item_model=Item
        self.materials={3:NS(id=3,code='B-M',price=99),4:NS(id=4,code='NEW',price=5)}
        material_model=NS(query=NS(filter_by=lambda **kw:NS(first=lambda:next((m for m in self.materials.values() if m.code==kw['code']),None))))
        self.payload=dict(order_id=1,warehouse_id=5,reason='合成售后',remark='header changed only',
            items=[dict(line_id=10,code='B-M',quantity=str(quantity),price=str(price),remark='line note')])
        self.before=deepcopy(self.order.__dict__)
        def rollback():self.order.__dict__.clear();self.order.__dict__.update(deepcopy(self.before))
        def add(row):
            if row is self.order:return
            if row.id is None:row.id=self.next_id;self.next_id+=1;self.order.items.append(row)
        def commit():self.commits+=1
        push=NS(query=NS(filter_by=lambda **kwargs:NS(first=lambda:NS(id=99) if self.active_push else None)))
        self.env.update(AfterSaleOutOrder=Order,AfterSaleOutOrderItem=Item,Material=material_model,DocumentPushLine=push,
            SalesOrder=object(),OutOrder=object(),request=NS(get_json=lambda **kwargs:self.payload,form={}),
            g=NS(document_edit_guard=True),stage_document_response=lambda x:None,app=NS(logger=NS(error=deny)),
            db=NS(session=NS(get=lambda model,ident:self.order if model is Order and ident==1 else None,
                add=add,delete=lambda row:self.order.items.remove(row),flush=lambda:None,commit=commit,rollback=rollback)))
        return line
    def post(self):
        result=self.env['add_after_sale_out_order']();return result if isinstance(result,tuple) else(result,200)
    def snapshot(self):return self.order.total_amount,tuple((r.id,r.material_id,r.quantity,r.price,r.amount,r.contract_id,r.contract_no,r.project_name) for r in self.order.items)
    def test_historical_float_amount_and_contracts_survive_note_only_save(self):
        self.assertEqual(self.env['round_to_2_decimals'](1.15*3.5),4.02)
        for amount in(0,4.02,7.77):
            self.case(amount);before=self.snapshot();self.payload['items'][0].update(saved_amount=888,contract_no='FORGED')
            self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before);self.assertEqual(self.order.items[0].remark,'line note')
    def test_only_note_preserves_high_precision_and_small_quantity(self):
        for qty in(1.2345,.0001):
            self.case(7.77,qty,3.56789);before=self.snapshot();self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before)
    def test_actual_change_keeps_other_component_precision_contract_and_identity(self):
        for field,value,qty,price,amount in(('quantity','1.23',1.23,3.56789,4.39),('price','0',1.2345,0,0)):
            self.case(7.77,1.2345,3.56789);self.payload['items'][0][field]=value
            self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),(amount,((10,3,qty,price,amount,7,'SYN-C','合成工程'),)))
    def test_header_zero_and_missing_header_are_distinct(self):
        for header,expected in((0,0),(None,7.77)):
            self.case(7.77);self.order.total_amount=header;self.assertEqual(self.post()[1],200);self.assertEqual(self.order.total_amount,expected)
    def test_active_push_guard_remains_before_any_save(self):
        self.case();self.active_push=True;before=self.snapshot();self.assertEqual(self.post()[1],409);self.assertEqual(self.snapshot(),before);self.assertEqual(self.commits,0)
    def test_nonpending_status_remains_uneditable(self):
        self.case();self.order.status='completed';self.assertEqual(self.post()[1],400);self.assertEqual(self.commits,0)
    def test_after_sale_edit_line_id_rejects_foreign_duplicate_and_bad_types(self):
        for identity in(11,True,0,'1e1','9'*20):
            self.case();before=self.snapshot();self.payload['items'][0]['line_id']=identity;self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
        self.case();before=self.snapshot();self.payload['items'].append(dict(self.payload['items'][0]));self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
    def test_modern_identity_requires_real_revision_guard(self):
        self.case();before=self.snapshot();self.env['g']=NS(document_edit_guard=None);self.assertEqual(self.post()[1],409);self.assertEqual(self.snapshot(),before)
    def test_existing_id_cannot_be_repurposed_for_another_material(self):
        self.case();before=self.snapshot();self.payload['items'][0]['code']='NEW';self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
    def test_legacy_no_id_is_explicit_replacement_not_material_matching(self):
        self.case();self.payload['items'][0].pop('line_id');self.assertEqual(self.post()[1],200)
        row=self.order.items[0];self.assertNotEqual(row.id,10);self.assertEqual(row.amount,4.03)
    def test_null_id_new_row_uses_existing_price_and_amount_rules(self):
        self.case();self.payload['items'].append(dict(line_id=None,code='NEW',quantity='1.2345',price='0',remark='new'))
        self.assertEqual(self.post()[1],200);old,new=self.order.items
        self.assertEqual((old.id,old.amount,old.contract_no),(10,4.02,'SYN-C'))
        self.assertEqual((new.quantity,new.price,new.amount,new.contract_no),(1.2345,0,0,None));self.assertEqual(self.order.total_amount,4.02)
    def test_omitted_line_is_removed_without_touching_other_history(self):
        self.case();other=self.item_model(id=11,material_id=4,quantity=2,price=3,amount=6)
        self.order.items.append(other);self.assertEqual(self.post()[1],200);self.assertEqual(len(self.order.items),1);self.assertEqual(self.order.items[0].id,10);self.assertEqual(self.order.total_amount,4.02)
    def test_later_bad_row_rolls_back_earlier_metadata_and_money(self):
        self.case();before=self.snapshot();self.payload['items'][0]['quantity']='2'
        self.payload['items'].append(dict(line_id=None,code='NEW',quantity='0',price='1'))
        self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before);self.assertEqual(self.commits,0)
    def test_missing_material_rolls_back(self):
        self.case();before=self.snapshot();self.payload['items'][0]['code']='MISSING';self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
    def test_complete_and_revert_do_not_recalculate_financial_fields(self):
        tree=ast.parse((ROOT/'app/routes/after_sale_out.py').read_text(encoding='utf-8-sig'))
        for name in('complete_after_sale_out_order','revert_after_sale_out_order'):
            fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
            writes={t.attr for n in ast.walk(fn) if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Attribute)}
            self.assertFalse(writes&{'quantity','price','amount','total_amount'},(name,writes))

if __name__=='__main__':unittest.main(verbosity=2)
