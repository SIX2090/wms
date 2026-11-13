"""Historical material outside active choices: actual Node -> actual save model."""
from pathlib import Path
import runpy
import subprocess
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
CASE=('price',1.2345,0,'',3.5,4.02,200)


def capture_history_cache():
    namespace=runpy.run_path(str(ROOT/'tests/test_document_input_money_contract_20261113.py'))
    actual_run=subprocess.run
    def without_active_choices(args,*positional,**kwargs):
        # Only alter the synthetic active-choice cache, retaining the real item's
        # serialized historical material supplied by the existing edit GET route.
        args=list(args)
        assert args[1]=='-e' and args[2].count('materials:[material]')==1
        args[2]=args[2].replace('materials:[material]','materials:[]')
        return actual_run(args,*positional,**kwargs)
    with patch.object(subprocess,'run',side_effect=without_active_choices):
        return namespace['capture_input']('sales',CASE)


class SalesHistoryCacheMoneyContract(unittest.TestCase):
    def test_inactive_owned_line_missing_from_choice_cache_uses_its_serialized_default(self):
        shown=capture_history_cache()
        namespace=runpy.run_path(str(ROOT/'tests/test_sales_edit_history_contract_20261113.py'))
        cls=namespace['SalesEditHistoryContract'];cls.setUpClass();model=cls();model.setUp()
        try:
            original=model.case(price=0)
            model.material.status='inactive'
            model.payload['items']=shown['items']
            result,status=model.post()
            self.assertEqual(status,200,result)
            self.assertIs(model.order.items[0],original)
            self.assertEqual((original.quantity,original.price,float(original.amount)),(1.2345,3.5,4.32))
            self.assertEqual(shown['items'][0]['price'],'','display calculation cannot rewrite operator input')
            self.assertEqual(float(shown['shown'][0]['amount']),float(original.amount))
            self.assertEqual(float(shown['total']),float(model.order.total_amount))
        finally:model.doCleanups()


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SalesHistoryCacheMoneyContract)
    assert suite.countTestCases()==1
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
