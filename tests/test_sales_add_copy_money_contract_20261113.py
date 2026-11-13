"""Actual add-page inputs/copy/template + actual add source, explicit fake ORM.

No real app, database, server or browser execution. Node's network/child modules
are blocked; the existing source model denies app imports and external I/O.
"""
import ast
from decimal import Decimal
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MONEY = runpy.run_path(str(ROOT/'tests/test_document_copy_money_contract_20261113.py'))
CASES, rounded = MONEY['CASES'], MONEY['rounded']


def capture_add(flow, quantity, price, default_price):
    namespace = runpy.run_path(str(ROOT/'tests/test_sales_edit_history_frontend_20261113.py'))
    block = namespace['block']
    source = (ROOT/'app/templates/sales_order_add.html').read_text(encoding='utf-8-sig')
    markers = ('var unitName = function(', 'var findMaterial = function(', 'function recalcRow(',
               'function recalc(', 'function fillRow(', 'function addRow(', 'function renumber(',
               'function collect(', 'async function save(', 'function ensureBlankRows(')
    script = 'var salesSaveBusy = false;\n' + '\n'.join(block(source,m)+';' for m in markers)
    script = script.replace('{{ url_for("sales_order_add") }}', '/sales/add')
    for first, last in (("document.getElementById('copyRowBtn').addEventListener", "document.getElementById('pasteBtn').addEventListener"),
                        ("document.getElementById('templateSelect').addEventListener('change'", '    function refreshMaterials()')):
        start=source.index(first);end=source.index(last,start);script+='\n'+source[start:end]
    program = namespace['PROGRAM'].split('(async()=>{')[0]
    program = program.replace("name:'Synthetic material',price:3.5,unit:'PCS'", "name:'Synthetic material',price:p.default_price,unit:'PCS'")
    program = program.replace("assert.equal(url,'/synthetic-capture-only');", "assert.equal(url,'/sales/add');")
    program = program.replace("   if(id==='copyRowBtn')", "   if(id==='templateSelect')return {addEventListener:(event,fn)=>handlers.template=fn};\n   if(id==='copyRowBtn')")
    program = program.replace('vm.createContext(ctx);', "Object.defineProperty(body,'innerHTML',{set(){rows.length=0;}});ctx.localStorage={getItem:()=>JSON.stringify([{items:[{line_id:10,code:'B-M',quantity:p.quantity,price:p.price,tax_rate:.13}]}])};ctx.SALES_TEMPLATE_KEY='synthetic-template';vm.createContext(ctx);")
    program += r'''
(async()=>{
 const original=ctx.addRow();original.querySelector('.material-code').value='B-M';
 original.querySelector('.qty').value=String(p.quantity);original.querySelector('.price').value=p.price==null?'':String(p.price);
 original.querySelector('.tax-rate').value='.13';ctx.fillRow(original,material);
 if(p.flow==='copy')handlers.copy();
 if(p.flow==='template')handlers.template.call({value:'0'});
 await ctx.save(false);assert.equal(captured.length,1);
 const active=rows.filter(r=>r.querySelector('.material-code').value==='B-M');
 process.stdout.write(JSON.stringify({items:captured[0].items,
  rows:active.map(r=>({quantity:r.querySelector('.qty').value,price:r.querySelector('.price').value,
   amount:r.querySelector('.included').textContent,untaxed:r.querySelector('.untaxed').textContent,
   tax:r.querySelector('.tax').textContent})),total:totals.totalIncluded.textContent,
  originalQuantity:original.querySelector('.qty').value}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    node = namespace['shutil'].which('node')
    if not node:
        raise unittest.SkipTest('Node required for actual new-row interactions')
    result=subprocess.run([node,'-e',program],input=json.dumps(dict(script=script,
        money=(ROOT/'app/static/js/money.js').read_text(encoding='utf-8-sig'),flow=flow,
        case='capture',quantity=quantity,price=price,default_price=default_price)),
        encoding='utf-8',capture_output=True,timeout=15)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class SalesAddCopyMoneyContract(unittest.TestCase):
    def check(self, flow):
        namespace=runpy.run_path(str(ROOT/'tests/test_sales_edit_history_contract_20261113.py'))
        cls=namespace['SalesEditHistoryContract'];cls.setUpClass()
        functions=namespace['functions']
        for quantity,price,default_price in CASES:
            with self.subTest(flow=flow,quantity=quantity,price=price,default=default_price):
                shown=capture_add(flow,quantity,price,default_price)
                self.assertEqual(shown['originalQuantity'],str(quantity),'new amount display must not rewrite user quantity')
                if price is None:
                    expected_default = 0 if flow == 'template' else rounded(default_price)
                    self.assertTrue(all(float(sent['price']) == expected_default for sent in shown['items']),
                                    'new default price must follow HALF_UP and preserve explicit template zero')
                if flow != 'input':
                    self.assertEqual(float(shown['items'][-1]['quantity']), rounded(quantity))
                    expected_price = (0 if flow == 'template' else rounded(default_price)) if price is None else rounded(price)
                    self.assertEqual(float(shown['items'][-1]['price']), expected_price)
                model=cls();model.setUp()
                try:
                    model.case()
                    model.material.price=default_price
                    model.payload['items']=shown['items']
                    class Order(SimpleNamespace):
                        def __init__(self,**values):
                            super().__init__(id=2,items=[],**values)
                    session=model.env['db'].session
                    def add(value):
                        if isinstance(value,Order):
                            model.order=value
                        else:
                            value.id=len(model.order.items)+100;model.order.items.append(value)
                    session.add=add
                    login=ModuleType('flask_login');login.current_user=SimpleNamespace(id=9)
                    model.env.update(SalesOrder=Order,generate_sales_order_no=lambda:'SO-SYN-COPY',
                                     stage_document_response=lambda *args:None,IntegrityError=type('SyntheticIntegrityError',(Exception,),{}))
                    nodes=functions('app/routes/sales.py',('sales_order_add',))
                    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),
                                 '<actual-sales-add-with-explicit-fake-ORM>','exec'),model.env)
                    with patch.dict(sys.modules,{'flask_login':login}):
                        result=model.env['sales_order_add']()
                    status=result[1] if isinstance(result,tuple) else 200
                    self.assertEqual(status,200,result)
                    self.assertEqual(len(model.order.items),len(shown['rows']))
                    for sent,displayed,stored in zip(shown['items'],shown['rows'],model.order.items):
                        qty=rounded(float(sent['quantity']));unit_price=rounded(float(sent['price']))
                        amount=rounded(Decimal(str(qty))*Decimal(str(unit_price)))
                        self.assertEqual((stored.quantity,stored.price,float(stored.amount)),(qty,unit_price,amount))
                        self.assertEqual(float(displayed['amount']),amount)
                        self.assertEqual(float(displayed['untaxed']),float(stored.untaxed_amount))
                        self.assertEqual(float(displayed['tax']),float(stored.tax_amount))
                    self.assertEqual(float(model.order.total_amount),float(shown['total']))
                finally:
                    model.doCleanups()

    def test_new_inputs_actual_payload_and_add_source(self):
        self.check('input')

    def test_copy_actual_event_payload_and_add_source(self):
        self.check('copy')

    def test_template_actual_event_payload_and_add_source(self):
        self.check('template')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SalesAddCopyMoneyContract)
    assert suite.countTestCases()==3 and len(CASES)==8
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
