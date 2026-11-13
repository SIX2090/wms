"""Historical SalesOrderItem aliases, using actual source/JS and owned synthetic objects."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import runpy
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
ALIASES = (
    (Decimal('7.77'), None, 7.77, 7.77, 7.77),
    (None, Decimal('7.77'), 7.77, 7.77, 7.77),
    (Decimal('0'), None, 0, 0, 0),
    (None, Decimal('0'), 0, 0, 0),
    (None, None, 4.03, 4.03, 4.03),
    (Decimal('0'), Decimal('4.02'), 0, 4.02, 4.02),
    (Decimal('7.77'), Decimal('0'), 7.77, 0, 7.77),
    (Decimal('4.02'), Decimal('7.77'), 4.02, 7.77, 7.77),
)


class SalesHistoryAliasContract(unittest.TestCase):
    def setUp(self):
        module = runpy.run_path(str(ROOT / 'tests/test_sales_edit_history_contract_20261113.py'))
        base = module['SalesEditHistoryContract']
        base.setUpClass()
        self.case_model = base(methodName='test_legacy_without_ids_retains_explicit_replace_semantics')
        self.case_model.setUp()
        self.addCleanup(self.case_model.doCleanups)

    def test_progress_aliases_fill_only_missing_values_and_preserve_stored_header(self):
        c = self.case_model
        for amount, primary, expected_amount, expected_primary, effective in ALIASES:
            for missing_header in (False, True):
                with self.subTest(amount=amount, primary=primary, missing_header=missing_header):
                    line = c.case(amount=amount, quantity=1.15, price=3.5)
                    line.tax_included_amount = primary
                    if missing_header:
                        c.order.total_amount = None
                    c.env['recalculate_sales_order'](c.order, recalculate_amounts=False)
                    self.assertEqual((float(line.amount), float(line.tax_included_amount)), (expected_amount, expected_primary))
                    self.assertEqual(float(c.order.total_amount), effective if missing_header else 9.99)
                    self.assertEqual((line.quantity, line.price, line.tax_amount), (1.15, 3.5, Decimal('.52')))
                    if amount is not None:
                        self.assertEqual(line.amount, amount, 'stored compatibility amount must never be rewritten')
                    if primary is not None:
                        self.assertEqual(line.tax_included_amount, primary, 'stored primary amount must never be rewritten')

    def test_metadata_edit_uses_recorded_synonym_before_quantity_product(self):
        c = self.case_model
        for amount, primary, expected_amount, expected_primary, effective in ALIASES:
            with self.subTest(amount=amount, primary=primary):
                line = c.case(amount=amount, quantity=1.15, price=3.5)
                line.tax_included_amount = primary
                self.assertEqual(c.post()[1], 200)
                line, = c.order.items
                self.assertEqual((float(line.amount), float(line.tax_included_amount)), (expected_amount, expected_primary))
                self.assertEqual(c.order.total_amount, Decimal('9.99'))
                self.assertEqual((line.quantity, line.price, line.tax_amount), (1.15, 3.5, Decimal('.52')))

    def test_mixed_financial_edit_uses_primary_then_existing_legacy_fallback(self):
        c = self.case_model
        for amount, primary, expected in ((Decimal('0'), Decimal('4.02'), 8.02),
                                         (Decimal('7.77'), Decimal('0'), 11.77)):
            with self.subTest(amount=amount, primary=primary):
                original = c.case(amount=amount, quantity=1.15, price=3.5)
                original.tax_included_amount = primary
                second = deepcopy(original)
                second.id = 11
                second.quantity = 1
                second.price = 2
                second.tax_rate = 0
                second.amount = second.tax_included_amount = second.untaxed_amount = Decimal('2')
                second.tax_amount = 0
                c.order.items.append(second)
                before = tuple(getattr(original, key) for key in ('quantity', 'price', 'amount', 'tax_included_amount', 'tax_amount'))
                c.payload['items'].append(dict(line_id=11, code='B-M', quantity='2', price='2', tax_rate='0'))
                self.assertEqual(c.post()[1], 200)
                self.assertEqual(c.order.total_amount, expected)
                self.assertEqual(tuple(getattr(original, key) for key in ('quantity', 'price', 'amount', 'tax_included_amount', 'tax_amount')), before)
                self.assertEqual((second.quantity, second.amount, second.tax_included_amount), (2, 4, 4))

    def test_missing_tax_fields_use_recorded_included_without_overwriting_known_fields(self):
        c = self.case_model
        for path in ('progress', 'edit'):
            with self.subTest(path=path):
                line = c.case(amount=Decimal('7.77'), quantity=1.15, price=3.5)
                line.tax_included_amount = line.untaxed_amount = line.tax_amount = None
                if path == 'progress':
                    c.env['recalculate_sales_order'](c.order, recalculate_amounts=False)
                else:
                    self.assertEqual(c.post()[1], 200)
                self.assertEqual((line.amount, line.tax_included_amount, line.untaxed_amount, line.tax_amount),
                                 (Decimal('7.77'), 7.77, 6.88, .89))
                self.assertEqual((line.quantity, line.price, line.untaxed_price), (1.15, 3.5, 3.0435))
                self.assertEqual(c.order.total_amount, Decimal('9.99'))

    def test_explicit_financial_recalculation_keeps_original_decimal_product_rule(self):
        c = self.case_model
        line = c.case(amount=Decimal('7.77'), quantity=1.15, price=3.5)
        c.env['recalculate_sales_order'](c.order)
        self.assertEqual((line.amount, line.tax_included_amount, c.order.total_amount), (4.03, 4.03, 4.03))


class SalesHistoryAliasFrontend(unittest.TestCase):
    def check(self, amount, primary, expected):
        module = runpy.run_path(str(ROOT / 'tests/test_sales_edit_history_frontend_20261113.py'))
        base = module['SalesEditHistoryFrontend']
        base.setUpClass()
        program = module['PROGRAM']
        if amount == '7.77':
            program = program.replace("'4.02'", "'7.77'")
        program = program.replace('const ctx={body', f"item.amount={json.dumps(amount)};item.tax_included_amount={json.dumps(primary)};\nconst ctx={{body", 1)
        marker = " if(p.case==='remark') {remark.value"
        addition = r'''
 const second={line_id:11,code:'B-M',material,quantity:1,price:2,tax_rate:0,
  amount:'2',tax_included_amount:'2',untaxed_amount:'2',tax_amount:'0'};
 ctx.existingItems.push(second);const edited=ctx.addRow(second);
 edited.querySelector('.qty').value='2';ctx.recalc();
 assert.equal(totals.totalIncluded.textContent,EXPECTED,'mixed header must use preserved primary/legacy amount');
 assert.equal(row.querySelector('.included').textContent,RECORDED,'unchanged row must keep existing read compatibility');
 await ctx.save();assert.equal(captured.length,1);assert.equal(captured[0].items.length,2);
 assert.equal(captured[0].items[0].line_id,'10');assert.equal(captured[0].items[1].quantity,'2');return;
'''.replace('EXPECTED', json.dumps(expected)).replace('RECORDED', json.dumps('4.02' if primary == '4.02' else '7.77'))
        self.assertEqual(program.count(marker), 1)
        program = program.replace(marker, addition + marker, 1)
        result = subprocess.run([base.node, '-e', program], input=json.dumps({
            'script': base.script, 'money': base.money, 'case': 'mixed'}),
            encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_positive_primary_wins_over_compatibility_zero(self):
        self.check('0', '4.02', '8.02')

    def test_existing_zero_placeholder_keeps_legacy_amount_fallback(self):
        self.check('7.77', '0', '11.77')


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in
                               (SalesHistoryAliasContract, SalesHistoryAliasFrontend))
    if suite.countTestCases() != 7:
        raise SystemExit('explicit alias source/Node list must contain seven tests')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
