"""Execute actual route AST on explicit fake ORM; never import app or open DB."""
import ast
import builtins
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
import math
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def deny(*args,**kwargs): raise AssertionError('app, DB, network and children forbidden')
def extract(rel,names):
    tree=ast.parse((ROOT/rel).read_text(encoding='utf-8-sig'));nodes=[]
    for name in names:
        found=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
        if not found and name.startswith('_request_edit_'): continue
        assert len(found)==1,name
        n=found[0];n.decorator_list=[]
        n.body=[s for s in n.body if not(isinstance(s,ast.ImportFrom) and s.module=='app')]
        nodes.append(n)
    return nodes

class PurchaseRequestHistoryContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=dict(date=date,datetime=datetime,Decimal=Decimal,InvalidOperation=InvalidOperation,
            ROUND_HALF_UP=ROUND_HALF_UP,localcontext=localcontext,json=json,math=math,
            api_error=lambda msg,status=400:({'status':'error','msg':msg},status),jsonify=lambda x:x,
            ValidationError=type('ValidationError',(Exception,),{}),log_operation=lambda *args:None,
            generate_order_no=lambda *args:'PR-SYN-NEW',
            resolve_purchase_request_line_fields=lambda row:NS(contract_no=None,project_name=None,remark=row.get('remark','')),
            purchase_request_item_data_has_material=lambda row:isinstance(row,dict) and bool(row.get('material_id') or row.get('material_code') or row.get('material_name')))
        nodes=extract('app/utils.py',('parse_float_value','parse_date_value','round_money_product'))
        nodes+=extract('app/routes/purchase_request.py',('_request_edit_line_id','_request_edit_has_purchase','add_purchase_request'))
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),'<actual-PR-source-explicit-fake-ORM>','exec'),cls.env)
    def setUp(self):
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='app' or name.startswith('app.'): deny()
            return original(name,*args,**kwargs)
        login=ModuleType('flask_login');login.current_user=NS(id=9)
        for guard in (patch.object(builtins,'__import__',side_effect=guarded),patch.object(sqlite3,'connect',deny),
            patch.object(sqlite3.dbapi2,'connect',deny),patch.object(socket.socket,'connect',deny),
            patch.object(socket,'getaddrinfo',deny),patch.object(subprocess,'Popen',deny),patch.dict(sys.modules,{'flask_login':login})):
            guard.start();self.addCleanup(guard.stop)
    def case(self,amount=4.02,quantity=1.2345,price=3.56789):
        self.linked=False;self.nextid=100;self.commits=0
        class Query:
            def filter_by(q,**kw):return q
            def filter(q,*args):return q
            def first(q):return NS(id=900) if self.linked else None
        class Order(NS): pass
        class Item(NS):
            def __init__(item,**values):
                defaults=dict(id=None,estimated_amount=None,estimated_price=None)
                defaults.update(values);super().__init__(**defaults)
        Order.query=Query()
        self.order=Order(id=1,request_no='PR-SYN-HISTORY',status='pending',items=[],total_amount=9.99)
        line=Item(id=10,purchase_request_id=1,material_id=3,material_code='B-M',quantity=quantity,estimated_price=price,estimated_amount=amount,remark='old')
        self.order.items=[line];self.model=Item
        self.payload=dict(request_id=1,remark='header note',items=[dict(line_id=10,material_id=3,material_code='B-M',quantity=str(quantity),estimated_price='' if price is None else str(price),remark='old')])
        self.before=deepcopy(self.order.__dict__)
        material=NS(id=3,code='B-M',name='合成物料',spec='');material_model=NS(query=NS(filter_by=lambda **kw:NS(first=lambda:material if kw['code']=='B-M' else None)))
        supplier_model=object()
        def get(model,ident):
            if model is Order:return self.order if ident==1 else None
            if model is material_model:return material if str(ident)=='3' else None
            return None
        def add(row):
            if row is self.order:return
            if row.id is None:row.id=self.nextid;self.nextid+=1;self.order.items.append(row)
        def rollback():self.order.__dict__.clear();self.order.__dict__.update(deepcopy(self.before))
        def commit():self.commits+=1
        # SQL shape remains real; this explicitly fake field only emulates .in_.
        class Field:
            def in_(field,values):return tuple(values)
        self.env.update(PurchaseRequest=Order,PurchaseRequestItem=Item,Material=material_model,Supplier=supplier_model,
            PurchaseOrder=NS(query=Query()),PurchaseOrderItem=NS(query=Query(),purchase_request_item_id=Field()),
            request=NS(get_json=lambda **kw:self.payload,form={}),g=NS(document_edit_guard=True),
            stage_document_response=lambda x:None,app=NS(logger=NS(error=deny)),
            db=NS(session=NS(get=get,add=add,delete=lambda row:self.order.items.remove(row),flush=lambda:None,commit=commit,rollback=rollback)))
        return line
    def post(self):
        result=self.env['add_purchase_request']();return result if isinstance(result,tuple) else(result,200)
    def snapshot(self):return self.order.total_amount,tuple((r.id,r.material_id,r.quantity,r.estimated_price,r.estimated_amount) for r in self.order.items)
    def test_only_notes_preserve_snapshot_precision_and_identity(self):
        for amount in(0,4.02,7.77):
            for quantity in(1.2345,.0001):
                with self.subTest(amount=amount,quantity=quantity):
                    self.case(amount,quantity);before=self.snapshot();self.payload['items'][0].update(remark='line note',saved_amount=999)
                    self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before)
                    self.assertEqual(self.order.items[0].remark,'line note')
    def test_explicit_quantity_and_zero_price_change_keep_line_id_and_other_precision(self):
        for field,value,qty,price,amount in(('quantity','1.23',1.23,3.56789,4.39),('estimated_price','0',1.2345,0,0)):
            self.case();self.payload['items'][0][field]=value;self.assertEqual(self.post()[1],200)
            self.assertEqual(self.snapshot(),(amount,((10,3,qty,price,amount),)))
    def test_none_amount_backfills_only_missing_field_and_preserves_known_head(self):
        self.case(None,1.15,3.5);self.assertEqual(self.post()[1],200)
        self.assertEqual(self.snapshot(),(9.99,((10,3,1.15,3.5,4.03),)))
    def test_known_zero_and_missing_head_have_distinct_semantics(self):
        for header,expected in((0,0),(None,7.77)):
            self.case(7.77);self.order.total_amount=header;self.assertEqual(self.post()[1],200)
            self.assertEqual(self.order.total_amount,expected);self.assertEqual(self.order.items[0].estimated_amount,7.77)
    def test_none_price_metadata_preserves_recorded_estimate(self):
        self.case(7.77,price=None);before=self.snapshot();self.assertEqual(self.post()[1],200);self.assertEqual(self.snapshot(),before)
    def test_unknown_price_nonzero_estimate_quantity_change_is_atomic(self):
        self.case(7.77,price=None);before=self.snapshot();self.payload['items'][0]['quantity']='2'
        result,status=self.post();self.assertEqual(status,400);self.assertIn('预估单价',result['msg']);self.assertEqual(self.snapshot(),before);self.assertEqual(self.commits,0)
    def test_unpriced_zero_estimate_request_remains_editable_without_quote(self):
        self.case(0,price=None);self.payload['items'][0]['quantity']='2';self.assertEqual(self.post()[1],200)
        self.assertEqual(self.order.items[0].estimated_amount,0);self.assertEqual(self.order.items[0].quantity,2)
    def test_explicit_zero_price_resolves_unknown_estimate(self):
        self.case(7.77,price=None);self.payload['items'][0].update(quantity='2',estimated_price='0');self.assertEqual(self.post()[1],200)
        self.assertEqual(self.snapshot(),(0,((10,3,2,0,0),)))
    def test_request_edit_line_id(self):
        for value in(11,True,'1e1','0','9'*20):
            self.case();before=self.snapshot();self.payload['items'][0]['line_id']=value;self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
        self.case();before=self.snapshot();self.payload['items'].append(dict(self.payload['items'][0]));self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
    def test_signed_revision_required_for_modern_identity(self):
        self.case();before=self.snapshot();self.env['g']=NS(document_edit_guard=None);self.assertEqual(self.post()[1],409);self.assertEqual(self.snapshot(),before)
    def test_request_edit_has_purchase(self):
        self.case();self.linked=True;before=self.snapshot();self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
    def test_legacy_payload_explicitly_replaces_without_guessing_identity(self):
        self.case();del self.payload['items'][0]['line_id'];self.assertEqual(self.post()[1],200)
        self.assertNotEqual(self.order.items[0].id,10);self.assertEqual(self.order.items[0].estimated_amount,4.4)
    def test_omitted_row_removed_and_new_row_gets_new_identity(self):
        self.case();self.payload['items'][0]['line_id']=None;self.assertEqual(self.post()[1],200);self.assertNotEqual(self.order.items[0].id,10)
    def test_zero_quantity_and_unresolved_material_leave_state_unchanged(self):
        for field,value in(('quantity','0'),('material_id',999)):
            self.case();before=self.snapshot();self.payload['items'][0][field]=value
            if field=='material_id':self.payload['items'][0]['material_code']='MISSING'
            self.assertEqual(self.post()[1],400);self.assertEqual(self.snapshot(),before)
    def test_approved_request_remains_uneditable(self):
        self.case();self.order.status='approved';self.assertEqual(self.post()[1],400)

if __name__=='__main__':unittest.main(verbosity=2)
