"""Extend the existing guarded, memory-only source-function reconciliation suite.

The imported text is parsed rather than imported/executed as a module. Its
original memory-only SQLite, no-app, network and subprocess guards remain.
This is extracted product-function evidence, not full WMS app integration.
"""
import ast
import os
from pathlib import Path
import subprocess
import sys


CASES = r'''
def test_split_material_lines_do_not_repeat_whole_document_transactions(self):
    order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
    outbound = order.outbound_orders[0]
    outbound.items[0].quantity = 3
    session.add(OutOrderItem(order=outbound, material_id=material.id, quantity=2, amount=2))
    session.add_all([
        StockTransaction(reference_type='out_order', reference_id=outbound.id, material_id=material.id, transaction_type='out', quantity=-3),
        StockTransaction(reference_type='out_order', reference_id=outbound.id, material_id=material.id, transaction_type='out', quantity=-2),
        StockTransaction(reference_type='out_order', reference_id=outbound.id, material_id=material.id, transaction_type='in', quantity=99),
        StockTransaction(reference_type='in_order', reference_id=outbound.id, material_id=material.id, transaction_type='out', quantity=-99),
    ])
    session.flush()
    try:
        row = self.report(warehouse_id=a.id)['rows'][0]
        self.assertEqual(row['completed_qty'], 5)
        self.assertEqual(row['inventory_qty'], 5)
        self.assertEqual(self.print_data(warehouse_id=a.id)['rows'][0]['inventory_qty'], 5)
        self.assertEqual(session.query(StockTransaction).count(), 4)
    finally:
        session.rollback()

def test_two_documents_of_same_material_keep_distinct_transaction_totals(self):
    order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
    first = order.outbound_orders[0]
    first.items[0].quantity = 2
    second = OutOrder(order=order, status='completed', warehouse=a.name)
    session.add(second)
    session.flush()
    session.add(OutOrderItem(order=second, material_id=material.id, quantity=3, amount=3))
    session.add_all([
        StockTransaction(reference_type='out_order', reference_id=first.id, material_id=material.id, transaction_type='out', quantity=-2),
        StockTransaction(reference_type='out_order', reference_id=second.id, material_id=material.id, transaction_type='out', quantity=-3),
    ])
    session.flush()
    try:
        self.assertEqual(self.report(warehouse_id=a.id)['rows'][0]['inventory_qty'], 5)
    finally:
        session.rollback()

def test_distinct_materials_in_same_document_are_not_collapsed(self):
    order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
    outbound = order.outbound_orders[0]
    another = Material(code='SYN-ANOTHER', name='Synthetic second material')
    session.add(another)
    session.flush()
    outbound.items[0].quantity = 2
    session.add(OutOrderItem(order=outbound, material_id=another.id, quantity=3, amount=3))
    session.add_all([
        StockTransaction(reference_type='out_order', reference_id=outbound.id, material_id=material.id, transaction_type='out', quantity=-2),
        StockTransaction(reference_type='out_order', reference_id=outbound.id, material_id=another.id, transaction_type='out', quantity=-3),
    ])
    session.flush()
    try:
        self.assertEqual(self.report(warehouse_id=a.id)['rows'][0]['inventory_qty'], 5)
    finally:
        session.rollback()

def test_pending_document_transactions_are_excluded(self):
    order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
    first = order.outbound_orders[0]
    second = OutOrder(order=order, status='pending', warehouse=a.name)
    session.add(second)
    session.flush()
    session.add(OutOrderItem(order=second, material_id=material.id, quantity=3, amount=3))
    session.add_all([
        StockTransaction(reference_type='out_order', reference_id=first.id, material_id=material.id, transaction_type='out', quantity=-2),
        StockTransaction(reference_type='out_order', reference_id=second.id, material_id=material.id, transaction_type='out', quantity=-99),
    ])
    session.flush()
    try:
        self.assertEqual(self.report(warehouse_id=a.id)['rows'][0]['inventory_qty'], 2)
    finally:
        session.rollback()

def test_cross_warehouse_does_not_expose_an_inventory_total(self):
    order = session.query(SalesOrder).filter_by(order_no='SYN-0').one()
    outbound = order.outbound_orders[0]
    outbound.warehouse = b.name
    session.add(OutOrderItem(order=outbound, material_id=material.id, quantity=2, amount=2))
    session.add(StockTransaction(reference_type='out_order', reference_id=outbound.id,
        material_id=material.id, transaction_type='out', quantity=-2))
    session.flush()
    try:
        row = self.report(warehouse_id=a.id)['rows'][0]
        self.assertIsNone(row['inventory_qty'])
        self.assertFalse(row['ok'])
        self.assertIsNotNone(row['warehouse_reason'])
    finally:
        session.rollback()
'''


def main():
    harness = Path(__file__).with_name('test_sales_reconciliation_memory_20261109.py')
    tree = ast.parse(harness.read_text(encoding='utf-8-sig'))
    main_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    classes = [node for node in main_node.body if isinstance(node, ast.ClassDef) and node.name == 'ReconciliationMemoryTests']
    if len(classes) != 1:
        raise AssertionError('Unique source-only isolation harness required')
    existing = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    extra = ast.parse(CASES).body
    if len(existing) != 19 or len(extra) != 5:
        raise AssertionError('Explicit baseline and additional case lists must remain nonempty')
    classes[0].body.extend(extra)
    counts = [node for node in ast.walk(main_node) if isinstance(node, ast.Compare)
              and isinstance(node.left, ast.Call) and isinstance(node.left.func, ast.Attribute)
              and node.left.func.attr == 'countTestCases']
    if len(counts) != 1 or len(counts[0].comparators) != 1:
        raise AssertionError('Source harness count assertion missing')
    counts[0].comparators[0] = ast.Constant(value=24)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    namespace = {'__file__': __file__}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[*imports, main_node], type_ignores=[])),
                 '<guarded-sales-reconciliation>', 'exec'), namespace)
    namespace['main']()


def test_reconciliation_in_explicit_guarded_child():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    main()
