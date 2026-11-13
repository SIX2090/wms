"""Unknown recorded prices need explicit finite nonnegative numeric quotes.

Uses the existing actual-route AST/fake ORM harnesses; no app, DB or network.
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
INVALID=('abc','NaN','Infinity','-Infinity','-0.01',-1,True,False,[],{},['0'])
MISSING=(None,'',' ','\t\n')
DOMAINS={
 'request':('test_purchase_request_history_contract_20261113','PurchaseRequestHistoryContract','estimated_price'),
 'purchase':('test_purchase_edit_history_contract_20261113','PurchaseEditHistoryContract','price'),
 'sales':('test_sales_edit_history_contract_20261113','SalesEditHistoryContract','price'),
}
_CLASSES={}

@contextmanager
def actual_case(domain,*,amount=7.77,known_price=None):
    filename,class_name,price_field=DOMAINS[domain]
    if domain not in _CLASSES:
        spec=importlib.util.spec_from_file_location(filename,ROOT/'tests'/f'{filename}.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        cls=getattr(module,class_name);cls.setUpClass();_CLASSES[domain]=cls
    case=_CLASSES[domain]()
    case.setUp()
    try:
        case.case(amount=amount,price=known_price)
        yield case,price_field
    finally:case.doCleanups()

def snapshot(case):
    return case.financial_snapshot() if hasattr(case,'financial_snapshot') else case.snapshot()

class HistoryNullPriceInputContract(unittest.TestCase):
    def test_unknown_price_invalid_quotes_cannot_revalue_history(self):
        for domain in DOMAINS:
            for quote in INVALID:
                with self.subTest(domain=domain,quote=repr(quote)),actual_case(domain) as(case,field):
                    before=snapshot(case);case.payload['items'][0].update(quantity='2',**{field:quote})
                    result,status=case.post();self.assertEqual(status,400,result)
                    self.assertIn('单价',result['msg']);self.assertEqual(snapshot(case),before)
    def test_unknown_price_missing_quotes_cannot_become_implicit_zero_after_quantity_change(self):
        for domain in DOMAINS:
            for quote in MISSING:
                with self.subTest(domain=domain,quote=repr(quote)),actual_case(domain) as(case,field):
                    before=snapshot(case);case.payload['items'][0].update(quantity='2',**{field:quote})
                    self.assertEqual(case.post()[1],400);self.assertEqual(snapshot(case),before)
    def test_whitespace_missing_quote_is_metadata_only_when_other_inputs_unchanged(self):
        for domain in DOMAINS:
            for quote in MISSING:
                with self.subTest(domain=domain,quote=repr(quote)),actual_case(domain) as(case,field):
                    before=snapshot(case);case.payload['items'][0][field]=quote
                    self.assertEqual(case.post()[1],200);self.assertEqual(snapshot(case),before)
    def test_invalid_quote_without_quantity_change_is_not_a_conscious_new_price(self):
        for domain in DOMAINS:
            for quote in INVALID:
                with self.subTest(domain=domain,quote=repr(quote)),actual_case(domain) as(case,field):
                    before=snapshot(case);case.payload['items'][0][field]=quote
                    self.assertEqual(case.post()[1],400);self.assertEqual(snapshot(case),before)
    def test_explicit_finite_zero_and_positive_numeric_quotes_are_allowed(self):
        for domain in DOMAINS:
            for quote in(0,'0',' 0 ',3.5,'3.5',' 3.5 '):
                with self.subTest(domain=domain,quote=repr(quote)),actual_case(domain) as(case,field):
                    case.payload['items'][0].update(quantity='2',**{field:quote});self.assertEqual(case.post()[1],200)
                    row=case.order.items[0];self.assertEqual(row.id,10);self.assertEqual(row.price if domain!='request' else row.estimated_price,float(quote))
                    self.assertEqual(float(row.amount if domain!='request' else row.estimated_amount),2*float(quote))
    def test_request_unpriced_zero_estimate_still_allows_quantity_change_without_quote(self):
        for amount in(0,None):
            for quote in MISSING:
                with self.subTest(amount=amount,quote=repr(quote)),actual_case('request',amount=amount) as(case,field):
                    case.payload['items'][0].update(quantity='2',**{field:quote});self.assertEqual(case.post()[1],200)
                    row=case.order.items[0];self.assertEqual((row.quantity,row.estimated_price,row.estimated_amount),(2,None,0))
    def test_known_price_branch_keeps_existing_legacy_fallback_policy(self):
        for domain in DOMAINS:
            with self.subTest(domain=domain),actual_case(domain,known_price=3.5) as(case,field):
                case.payload['items'][0].update(quantity='2',**{field:'abc'});self.assertEqual(case.post()[1],200)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(HistoryNullPriceInputContract)
    if suite.countTestCases()!=7:raise SystemExit('explicit nonempty list must contain 7 methods')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
