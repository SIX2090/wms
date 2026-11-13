"""Actual copy JS -> captured save payload -> actual save source, explicit fake ORM.

This is a source/DOM model, not real app, database or browser verification.
Node cannot load network/child modules; route models deny app imports and I/O.
"""
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    (1.2345, None, 3.5),
    (1.2345, None, 0),
    (1.2345, 3.56789, 3.5),
    (1.005, 1.005, 3.5),
    (1.005, None, 1.005),
    (2.675, 1.335, 3.5),
    (2, None, 3.565),
    (2, 0, 3.5),
)


def rounded(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def capture_copy(kind, path, quantity, price, default_price):
    """Run the real copy handler and save function on a non-network synthetic DOM."""
    prefix = 'purchase' if kind == 'purchase' else 'sales'
    namespace = runpy.run_path(str(ROOT / f'tests/test_{prefix}_edit_history_frontend_20261113.py'))
    cls = namespace['PurchaseEditHistoryFrontend' if kind == 'purchase' else 'SalesEditHistoryFrontend']
    cls.setUpClass()
    program = namespace['PROGRAM']
    program = program.replace("p.case==='small'?.0001:1.2345", 'p.quantity')
    program = program.replace("p.case.includes('missing-price')?null:3.56789", 'p.price')
    program = program.replace("p.case==='small'?'0.0001':'1.2345'", 'String(p.quantity)')
    program = program.replace("p.case.includes('missing-price')?'':'3.56789'", "p.price==null?'':String(p.price)")
    if kind == 'purchase':
        program = program.replace("name:'Synthetic material',price:3.5,unit:'PCS'", "name:'Synthetic material',price:p.default_price,unit:'PCS'")
        before = "  assert.equal(rows[1]._purchaseSnapshot,null);return;"
        after = """  assert.equal(rows[1]._purchaseSnapshot,null);
  await ctx.submitForm(false);assert.equal(requests.length,1);
  process.stdout.write(JSON.stringify({items:requests[0].items,
   original:{quantity:row.querySelector('.material-qty').value,price:row.querySelector('.material-price').value,
    amount:row.querySelector('.material-amount').value,snapshot:row._purchaseSnapshot},
   copied:{quantity:rows[1].querySelector('.material-qty').value,price:rows[1].querySelector('.material-price').value,
    amount:rows[1].querySelector('.material-amount').value},total:totals.totalAmount.textContent}));return;"""
        case = 'copy-' + path
    else:
        program = program.replace("name:'Synthetic material',price:3.5,unit:'PCS'", "name:'Synthetic material',price:p.default_price,unit:'PCS'")
        if path == 'template':
            source = (ROOT / 'app/templates/sales_order_edit.html').read_text(encoding='utf-8-sig')
            start = source.index("document.getElementById('templateSelect').addEventListener('change'")
            end = source.index('    function refreshMaterials()', start)
            cls.script += '\n' + namespace['block'](source, 'function ensureBlankRows(') + ';\n' + source[start:end]
            program = program.replace("   if(id==='copyRowBtn')", "   if(id==='templateSelect')return {addEventListener:(event,fn)=>handlers.template=fn};\n   if(id==='copyRowBtn')")
            program = program.replace('vm.createContext(ctx);', "Object.defineProperty(body,'innerHTML',{set(){rows.length=0;}});ctx.localStorage={getItem:()=>JSON.stringify([{items:[item]}])};ctx.SALES_TEMPLATE_KEY='synthetic-template';vm.createContext(ctx);")
            program = program.replace('handlers.copy();const copy=rows.at(-1);', "handlers.template.call({value:'0'});const copy=rows.find(r=>r.querySelector('.material-code').value==='B-M');")
            program = program.replace("const values=ctx.collect().items;assert.equal(values[0].line_id,'10');assert.equal(values[1].line_id,null);", "const values=ctx.collect().items;assert.equal(values.length,1);assert.equal(values[0].line_id,null);")
        before = "  return;}\n await ctx.save();"
        after = """  await ctx.save();assert.equal(captured.length,1);
  process.stdout.write(JSON.stringify({items:captured[0].items,
   original:{quantity:row.querySelector('.qty').value,price:row.querySelector('.price').value,
    amount:row.querySelector('.included').textContent,snapshot:row._salesSnapshot},
   copied:{quantity:copy.querySelector('.qty').value,price:copy.querySelector('.price').value,
    amount:copy.querySelector('.included').textContent},total:totals.totalIncluded.textContent}));return;}
 await ctx.save();"""
        case = 'copy'
    if program.count(before) != 1:
        raise AssertionError('actual fixture copy capture must be unique')
    program = program.replace(before, after)
    result = subprocess.run([cls.node, '-e', program], input=json.dumps(dict(script=cls.script,
        money=cls.money, case=case, quantity=quantity, price=price, default_price=default_price)),
        encoding='utf-8', capture_output=True, timeout=15)
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def assert_copy(test, shown, quantity, price, default_price, replacing=False):
    qty = rounded(quantity)
    unit_price = rounded(default_price if price is None else price)
    amount = rounded(Decimal(str(qty)) * Decimal(str(unit_price)))
    test.assertEqual(shown['original']['quantity'], str(quantity))
    test.assertEqual(shown['original']['price'], '' if price is None else str(price))
    test.assertEqual(shown['original']['amount'], '4.02')
    test.assertEqual(shown['original']['snapshot']['price'], price)
    test.assertEqual(shown['items'][-1]['line_id'], None)
    test.assertNotEqual(shown['items'][-1]['price'], '', 'new copy must display and submit its actual unit price')
    test.assertEqual(float(shown['items'][-1]['quantity']), qty)
    test.assertEqual(float(shown['items'][-1]['price']), unit_price)
    test.assertEqual(float(shown['copied']['amount']), amount)
    test.assertEqual(float(shown['total'].lstrip('¥')), rounded((Decimal('0') if replacing else Decimal('4.02')) + Decimal(str(amount))))
    return qty, unit_price, amount


class DocumentCopyMoneyContract(unittest.TestCase):
    def check_route(self, kind, path):
        namespace = runpy.run_path(str(ROOT / f'tests/test_{kind}_edit_history_contract_20261113.py'))
        cls = namespace['PurchaseEditHistoryContract' if kind == 'purchase' else 'SalesEditHistoryContract']
        cls.setUpClass()
        for quantity, price, default_price in CASES:
            with self.subTest(kind=kind, path=path, quantity=quantity, price=price, default=default_price):
                shown = capture_copy(kind, path, quantity, price, default_price)
                qty, unit_price, amount = assert_copy(self, shown, quantity, price, default_price, path == 'template')
                model = cls()
                model.setUp()
                try:
                    original = model.case(quantity=quantity, price=price)
                    if kind == 'purchase':
                        model.materials[3].price = default_price
                    else:
                        model.material.price = default_price
                    model.payload['items'] = shown['items']
                    self.assertEqual(model.post()[1], 200)
                    if path == 'template':
                        new, = model.order.items
                        self.assertIsNot(new, original)
                    else:
                        old = next(row for row in model.order.items if row.id == 10)
                        new, = (row for row in model.order.items if row.id != 10)
                        self.assertIs(old, original)
                        self.assertEqual((old.quantity, old.price, float(old.amount)), (quantity, price, 4.02))
                    self.assertEqual((new.quantity, new.price, float(new.amount)), (qty, unit_price, amount))
                    self.assertEqual(float(model.order.total_amount), float(shown['total'].lstrip('¥')))
                    if kind == 'purchase':
                        self.assertEqual(old.purchase_request_item_id, 700)
                        self.assertIsNone(new.purchase_request_item_id)
                finally:
                    model.doCleanups()

    def test_purchase_copy_previous_actual_js_payload_and_save_source(self):
        self.check_route('purchase', 'previous')

    def test_purchase_copy_after_actual_js_payload_and_save_source(self):
        self.check_route('purchase', 'after')

    def test_sales_copy_actual_js_payload_and_save_source(self):
        self.check_route('sales', 'previous')

    def test_sales_template_actual_change_event_payload_and_save_source(self):
        self.check_route('sales', 'template')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DocumentCopyMoneyContract)
    assert suite.countTestCases() == 4 and len(CASES) == 8
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
