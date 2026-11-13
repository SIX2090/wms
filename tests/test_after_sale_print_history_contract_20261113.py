"""Actual print getter/row/common renderer with explicit synthetic ORM and I/O denied."""
import ast
import builtins
from datetime import date,datetime
from functools import lru_cache
from pathlib import Path
import socket
import sqlite3
import subprocess
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def nodes(path,names):
    tree=ast.parse((ROOT/path).read_text(encoding='utf-8-sig'));selected=[]
    for name in names:
        found=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
        assert len(found)==1,name
        node=found[0];node.decorator_list=[]
        node.body=[stmt for stmt in node.body if not(isinstance(stmt,ast.ImportFrom) and stmt.module in ('app','sqlalchemy.orm'))]
        selected.append(node)
    return selected


@lru_cache(maxsize=1)
def print_code():
    selected=nodes('app/app.py',('_operator_name','_material_unit_name','_material_row_common',
                                '_fmt_date','_print_status_label','_render_generic_document_print'))
    selected+=nodes('app/routes/after_sale_out.py',('print_after_sale_out',))
    return compile(ast.fix_missing_locations(ast.Module(body=selected,type_ignores=[])),
                   '<actual-print-getter-row-and-render-context>','exec')


def print_context(header_amount,line_amount):
    class Loader:
        def joinedload(self,*args):return self
    class Order:
        operator=object();items=object()
    class Item:
        material=object()
    class Material:
        unit=object()
    line=NS(material=NS(code='SYN',name='合成物料',spec='合成规格',unit=NS(name='PCS')),
            quantity=1.15,price=3.5,amount=line_amount,remark='synthetic line')
    order=NS(order_no='ASO-SYN-PRINT',date=date(2026,11,13),status='pending',
             customer='合成客户',contact='',phone='',reason='合成售后',remark='synthetic header',
             total_amount=header_amount,items=[line],operator=NS(username='synthetic'))
    Order.query=NS(options=lambda *args:NS(get_or_404=lambda ident:order))
    env=dict(date=date,datetime=datetime,AfterSaleOutOrder=Order,AfterSaleOutOrderItem=Item,
             Material=Material,selectinload=lambda *args:Loader(),joinedload=lambda *args:Loader(),
             render_template=lambda name,**values:dict(template=name,**values))
    exec(print_code(),env)
    return env['print_after_sale_out'](1)


class AfterSalePrintHistoryContract(unittest.TestCase):
    def test_known_zero_none_and_historical_header_difference_use_consistent_render_values(self):
        real_import=builtins.__import__
        def deny(*args,**kwargs):raise AssertionError('app/DB/network/children forbidden')
        def guarded(name,*args,**kwargs):
            if name=='app' or name.startswith('app.'):deny()
            return real_import(name,*args,**kwargs)
        with patch.object(builtins,'__import__',side_effect=guarded),patch.object(sqlite3,'connect',deny),\
             patch.object(socket.socket,'connect',deny),patch.object(socket,'getaddrinfo',deny),patch.object(subprocess,'Popen',deny):
            for header in (0,None,9.99):
                for line in (0,4.02):
                    with self.subTest(header=header,line=line):
                        result=print_context(header,line)
                        self.assertEqual(result['template'],'document_print.html')
                        doc=result['doc'];expected=line if header is None else header
                        self.assertEqual(doc['total_amount'],expected)
                        self.assertEqual(dict(doc['info'])['总金额'],f'{expected:.2f}')
                        self.assertEqual(doc['rows'][0]['amount'],line)
                        self.assertEqual(doc['rows'][0]['price'],3.5)
                        self.assertEqual(doc['total_quantity'],1.15)
                        self.assertEqual(doc['number'],'ASO-SYN-PRINT')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(AfterSalePrintHistoryContract)
    assert suite.countTestCases()==1
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
