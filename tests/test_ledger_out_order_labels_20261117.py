"""Ledger labels must follow each source document's actual business type."""
import ast
from pathlib import Path
from types import SimpleNamespace


def test_ledger_out_order_labels_follow_source_business_type():
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'app/app.py').read_text(encoding='utf-8'))
    function = next((n for n in tree.body if isinstance(n, ast.FunctionDef)
                     and n.name == '_ledger_out_order_labels'), None)
    class Column:
        def in_(self, ids):
            assert ids == {1, 2, 3, 4}
            return True
    class Query:
        def with_entities(self, *columns):
            return self
        def filter(self, condition):
            return self
        def all(self):
            return [(1, '销售出库'), (2, '其他出库'), (3, '领料单'), (4, '采购退货出库')]
    model = SimpleNamespace(id=Column(), business_type=Column(), query=Query())
    scope = {'OutOrder': model}
    transactions = [SimpleNamespace(reference_type='out_order', reference_id=i) for i in range(1, 5)]
    if function is None:
        # Exercise the old real mapping as the negative control, rather than
        # treating a missing new helper/fixture as proof of the product bug.
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'REFERENCE_TYPE_LABELS'
                                  for t in n.targets))
        mapping = ast.literal_eval(assignment.value)
        actual = {t.reference_id: mapping[t.reference_type] for t in transactions}
    else:
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<ledger-labels>', 'exec'), scope)
        actual = scope['_ledger_out_order_labels'](transactions)
        assert scope['_ledger_out_order_labels']([]) == {}
    assert actual == {
        1: '销售出库', 2: '其他出库', 3: '领料单', 4: '采购退货出库'}
