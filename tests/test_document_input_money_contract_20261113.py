"""Real PO/edit-sales calculation + save source on a denied-I/O explicit model."""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
rounded=runpy.run_path(str(ROOT/'tests/test_document_copy_money_contract_20261113.py'))['rounded']
# op, stored quantity, stored price, entered component, material default, recorded amount, expected status
CASES=(
 ('new',1.2345,3.56789,(1.2345,3.56789),3.5,4.02,200),
 ('quantity',1.2345,3.56789,1.23456,3.5,4.02,200),
 ('price',1.2345,3.56789,3.567891,3.5,4.02,200),
 ('quantity',1.2345,3.56789,1.005,3.5,4.02,200),
 ('price',1.2345,3.56789,1.005,3.5,4.02,200),
 ('price',1.2345,3.56789,0,3.5,4.02,200),
 ('metadata',1.2345,None,None,3.5,7.77,200),
 ('quantity',1.2345,None,2,3.5,7.77,400),
 ('price',1.2345,0,'',3.5,4.02,200),
 ('price',1.2345,3.5,'',3.5,4.02,200),
 ('new',1.2345,3.56789,(1.005,1.005),3.5,4.02,200),
 ('new',1.2345,3.56789,(1.005,''),1.005,4.02,200),
)


def capture_input(kind,case):
    op,quantity,price,entered,default,amount,status=case
    namespace=runpy.run_path(str(ROOT/f'tests/test_{kind}_edit_history_frontend_20261113.py'))
    cls=namespace['PurchaseEditHistoryFrontend' if kind=='purchase' else 'SalesEditHistoryFrontend']
    cls.setUpClass()
    program=namespace['PROGRAM'].split('(async()=>{')[0]
    program=program.replace("p.case==='small'?.0001:1.2345",'p.quantity')
    program=program.replace("p.case.includes('missing-price')?null:3.56789",'p.price')
    program=program.replace("name:'Synthetic material',price:3.5,unit:'PCS'","name:'Synthetic material',price:p.default_price,unit:'PCS'")
    if kind=='purchase':
        program=program.replace('amount:4.02','amount:p.amount')
        program+=r'''
(async()=>{
 const row=ctx.addNewRow(item);
 if(p.op==='new')ctx.addNewRow({material_id:3,material_code:'B-M',quantity:p.entered[0],price:p.entered[1]});
 if(p.op==='quantity'){row.querySelector('.material-qty').value=String(p.entered);row.querySelector('.material-qty').fire('input');}
 if(p.op==='price'){row.querySelector('.material-price').value=String(p.entered);row.querySelector('.material-price').fire('input');}
 await ctx.submitForm(false);assert.equal(requests.length,1);
 process.stdout.write(JSON.stringify({items:requests[0].items,total:totals.totalAmount.textContent,
  shown:rows.map(r=>({quantity:r.querySelector('.material-qty').value,price:r.querySelector('.material-price').value,
   amount:r.querySelector('.material-amount').value}))}));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    else:
        program=program.replace("amount:'4.02'","amount:p.amount")
        program+=r'''
(async()=>{
 const row=ctx.addRow(item);
 if(p.op==='new')ctx.addRow({code:'B-M',quantity:p.entered[0],price:p.entered[1],tax_rate:.13});
 if(p.op==='quantity')row.querySelector('.qty').value=String(p.entered);
 if(p.op==='price')row.querySelector('.price').value=String(p.entered);
 ctx.recalc();await ctx.save();assert.equal(captured.length,1);
 process.stdout.write(JSON.stringify({items:captured[0].items,total:totals.totalIncluded.textContent,
  shown:rows.map(r=>({quantity:r.querySelector('.qty').value,price:r.querySelector('.price').value,
   amount:r.querySelector('.included').textContent,untaxed:r.querySelector('.untaxed').textContent,
   tax:r.querySelector('.tax').textContent}))}));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result=subprocess.run([cls.node,'-e',program],input=json.dumps(dict(script=cls.script,money=cls.money,
        case='capture',op=op,quantity=quantity,price=price,entered=entered,default_price=default,amount=amount)),
        encoding='utf-8',capture_output=True,timeout=15)
    if result.returncode:raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class DocumentInputMoneyContract(unittest.TestCase):
    def check(self,kind):
        ns=runpy.run_path(str(ROOT/f'tests/test_{kind}_edit_history_contract_20261113.py'))
        cls=ns['PurchaseEditHistoryContract' if kind=='purchase' else 'SalesEditHistoryContract'];cls.setUpClass()
        for case in CASES:
            with self.subTest(kind=kind,case=case):
                shown=capture_input(kind,case)
                op,quantity,price,entered,default,amount,status=case
                if op=='new' and entered[1]=='':
                    self.assertEqual(float(shown['items'][-1]['price']),rounded(default))
                model=cls();model.setUp()
                try:
                    old=model.case(quantity=quantity,price=price,amount=amount)
                    if kind=='purchase':model.materials[3].price=default
                    else:model.material.price=default
                    before=deepcopy(model.order.__dict__)
                    model.payload['items']=shown['items']
                    result,actual_status=model.post();self.assertEqual(actual_status,status,result)
                    if status==400:
                        self.assertEqual(model.order.__dict__,before)
                        self.assertEqual(shown['items'][0]['price'],'','unknown historical price cannot be guessed')
                        continue
                    for displayed,stored in zip(shown['shown'],model.order.items):
                        self.assertEqual(float(displayed['amount']),float(stored.amount))
                        if kind=='sales':
                            self.assertEqual(float(displayed['untaxed']),float(stored.untaxed_amount))
                            self.assertEqual(float(displayed['tax']),float(stored.tax_amount))
                    self.assertEqual(float(shown['total'].lstrip('¥')),float(model.order.total_amount))
                    kept=next(row for row in model.order.items if row.id==10)
                    if op in ('metadata','new'):
                        self.assertEqual((kept.quantity,kept.price,kept.amount),(quantity,price,amount))
                    if op=='quantity':self.assertEqual(kept.price,price,'unchanged price precision must survive')
                    if op=='price':self.assertEqual(kept.quantity,quantity,'unchanged quantity precision must survive')
                    self.assertIs(kept,old)
                    if kind=='purchase':self.assertEqual(kept.purchase_request_item_id,700)
                finally:model.doCleanups()

    def test_purchase_new_and_changed_components_match_actual_save(self):self.check('purchase')
    def test_sales_new_and_changed_components_match_actual_save(self):self.check('sales')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(DocumentInputMoneyContract)
    assert suite.countTestCases()==2 and len(CASES)==12
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
