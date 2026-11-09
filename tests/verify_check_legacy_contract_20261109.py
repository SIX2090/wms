"""Replay legacy confirmation contracts using extracted routes and memory-only models.

The isolation harness is AST-copied into this process; the real WMS app is not
imported and no existing regression file is executed or changed.
"""
import ast
from pathlib import Path


TESTS = r'''
class Integration(unittest.TestCase):
    def setUp(self):
        with app.app_context():
            db.session.remove()
            self.assertEqual(db.session.connection().exec_driver_sql('PRAGMA database_list').fetchone()[2], '')
            db.session.rollback()
            db.drop_all()
            db.create_all()
            db.session.add(Warehouse(id=2, name='B仓', code='WB', status='active'))
            db.session.add(Warehouse(id=1, name='合成仓', code='SYN', status='active'))
            db.session.add_all([Material(id=10, code='M001', name='合成1', unit_id=1),
                                Material(id=11, code='M002', name='合成2', unit_id=1)])
            db.session.add(InventoryCheck(id=10, check_no='CK-10', status='pending', warehouse='合成仓',
                date=datetime.date(2020, 1, 1), frozen_at=datetime.datetime(2020, 1, 1, 10), operator_id=1))
            db.session.add_all([
                InventoryCheckItem(id=10, inventory_check_id=10, material_id=10, system_stock=60,
                                   actual_stock=58, difference=-2, counted_by=1,
                                   counted_at=datetime.datetime(2020, 1, 1, 10, 1)),
                InventoryCheckItem(id=11, inventory_check_id=10, material_id=11, system_stock=30,
                                   actual_stock=30, difference=0, counted_by=None, counted_at=None),
            ])
            db.session.commit()
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['_user_id'], session['_fresh'] = '1', True
        self.headers = {'X-CSRFToken': self.client.get('/synthetic/csrf').get_json()['token']}

    def post(self, ident, payload):
        response = self.client.post(f'/synthetic/check/{ident}/complete', json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_uncounted_warning_force_and_exact_loss_draft(self):
        plain = self.client.post('/synthetic/check/10/complete', headers=self.headers)
        self.assertEqual(plain.status_code, 200)
        self.assertEqual((plain.json['status'], plain.json['code']), ('confirm', 'check_risks'))
        self.assertIn('共 2 行，其中 1 行未盘', plain.json['msg'])
        before = self.post(10, {})
        self.assertEqual((before['status'], before['code']), ('confirm', 'check_risks'))
        self.assertIn('共 2 行，其中 1 行未盘', before['msg'])
        self.assertEqual([item['code'] for item in before['samples']], ['M002'])
        with app.app_context():
            self.assertEqual(db.session.get(InventoryCheck, 10).status, 'pending')
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)
        old_force = self.post(10, {'force': True})
        self.assertEqual((old_force['status'], old_force['code']), ('confirm', 'check_risks'))
        self.assertIn('凭据缺失', old_force['msg'])
        with app.app_context():
            self.assertEqual(db.session.get(InventoryCheck, 10).status, 'pending')
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)
        done = self.post(10, {'force': True, 'confirmation_token': old_force['confirmation_token']})
        self.assertEqual(done['status'], 'success')
        with app.app_context():
            self.assertEqual(db.session.get(InventoryCheck, 10).status, 'completed')
            draft = AdjustmentOrder.query.filter_by(source_type='check', source_id=10).one()
            self.assertEqual((draft.status, draft.adjustment_type, draft.warehouse), ('pending', 'loss', '合成仓'))
            lines = AdjustmentOrderItem.query.filter_by(adjustment_order_id=draft.id).all()
            self.assertEqual(len(lines), 1)
            self.assertEqual((lines[0].material_id, lines[0].quantity), (10, -2))
            self.assertEqual(StockTransaction.query.count(), 0)

    def test_movement_warning_preserves_exact_nets_and_excludes_other_warehouse(self):
        with app.app_context():
            for item in InventoryCheckItem.query.filter_by(inventory_check_id=10):
                item.counted_by = 1
                item.counted_at = datetime.datetime(2020, 1, 1, 10, 1)
                item.actual_stock = item.system_stock
                item.difference = 0
            db.session.add_all([
                StockTransaction(material_id=10, warehouse_id=1, quantity=-10,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 2), transaction_type='out'),
                StockTransaction(material_id=11, warehouse_id=1, quantity=5,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 2), transaction_type='in'),
                StockTransaction(material_id=10, warehouse_id=2, quantity=20,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 2), transaction_type='in'),
            ])
            db.session.commit()
        warning = self.post(10, {})
        self.assertEqual((warning['status'], warning['code']), ('confirm', 'check_risks'))
        self.assertIn('本仓 2 个物料发生出入库流水', warning['msg'])
        samples = {row['code']: row['net'] for row in warning['samples']}
        self.assertEqual(samples, {'M001': -10, 'M002': 5})
        forced = self.post(10, {'force': True})
        self.assertEqual(forced['status'], 'confirm')
        done = self.post(10, {'force': True, 'confirmation_token': forced['confirmation_token']})
        self.assertEqual(done['status'], 'success')
        with app.app_context():
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)
            self.assertEqual(StockTransaction.query.count(), 3)

    def test_mixed_uncounted_and_movement_cannot_be_bypassed(self):
        with app.app_context():
            db.session.add(StockTransaction(material_id=10, warehouse_id=1, quantity=-10,
                           created_at=datetime.datetime(2020, 1, 1, 10, 2), transaction_type='out'))
            db.session.commit()
        warning = self.post(10, {'force': True})
        self.assertEqual((warning['status'], warning['code']), ('confirm', 'check_risks'))
        self.assertIn('1 行未盘', warning['msg'])
        self.assertIn('本仓 1 个物料发生出入库流水', warning['msg'])
        samples = warning['samples']
        self.assertTrue(any(row['code'] == 'M002' for row in samples))
        self.assertTrue(any(row['code'] == 'M001' and row.get('net') == -10 for row in samples))
        with app.app_context():
            self.assertEqual(db.session.get(InventoryCheck, 10).status, 'pending')
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)
        done = self.post(10, {'force': True, 'confirmation_token': warning['confirmation_token']})
        self.assertEqual(done['status'], 'success')
        with app.app_context():
            draft = AdjustmentOrder.query.filter_by(source_id=10).one()
            self.assertEqual(AdjustmentOrderItem.query.filter_by(adjustment_order_id=draft.id).one().quantity, -2)

    def test_frozen_sixty_actual_fifty_seven_with_movement_stays_minus_three(self):
        with app.app_context():
            first = db.session.get(InventoryCheckItem, 10)
            first.actual_stock, first.difference = 57, -3
            first.counted_at = first.counted_by = None
            db.session.delete(db.session.get(InventoryCheckItem, 11))
            db.session.add(StockTransaction(material_id=10, warehouse_id=1, quantity=-30,
                           created_at=datetime.datetime(2020, 1, 1, 10, 2), transaction_type='out'))
            db.session.commit()
        warning = self.post(10, {'force': True})
        self.assertEqual((warning['status'], warning['code']), ('confirm', 'check_risks'))
        self.assertIn('1 行未盘', warning['msg'])
        self.assertIn('本仓 1 个物料发生出入库流水', warning['msg'])
        done = self.post(10, {'force': True, 'confirmation_token': warning['confirmation_token']})
        self.assertEqual(done['status'], 'success')
        with app.app_context():
            draft = AdjustmentOrder.query.filter_by(source_id=10).one()
            self.assertEqual(AdjustmentOrderItem.query.filter_by(adjustment_order_id=draft.id).one().quantity, -3)
            self.assertEqual(StockTransaction.query.count(), 1)

    def test_mixed_pc_and_scanned_rows_preserve_both_differences(self):
        with app.app_context():
            first = db.session.get(InventoryCheckItem, 10)
            second = db.session.get(InventoryCheckItem, 11)
            first.counted_at = first.counted_by = None
            second.actual_stock, second.difference = 29, -1
            second.counted_by, second.counted_at = 1, datetime.datetime(2020, 1, 1, 10, 1)
            db.session.commit()
        warning = self.post(10, {'force': True})
        self.assertEqual(warning['status'], 'confirm')
        self.assertIn('1 行未盘', warning['msg'])
        self.assertEqual(self.post(10, {'force': True, 'confirmation_token': warning['confirmation_token']})['status'], 'success')
        with app.app_context():
            draft = AdjustmentOrder.query.filter_by(source_type='check', source_id=10).one()
            lines = AdjustmentOrderItem.query.filter_by(adjustment_order_id=draft.id).all()
            self.assertEqual({line.material_id: line.quantity for line in lines}, {10: -2, 11: -1})
            self.assertEqual(StockTransaction.query.count(), 0)

    def test_unknown_freeze_requires_acknowledgement_then_completes(self):
        with app.app_context():
            check = db.session.get(InventoryCheck, 10)
            check.frozen_at = None
            for item in check.items:
                item.counted_by = 1
                item.counted_at = datetime.datetime(2020, 1, 1, 10, 1)
                item.actual_stock = item.system_stock
                item.difference = 0
            db.session.commit()
        warning = self.post(10, {})
        self.assertEqual((warning['status'], warning['code']), ('confirm', 'check_risks'))
        self.assertIn('盘点冻结时间未知', warning['msg'])
        self.assertEqual(self.post(10, {'force': True})['status'], 'confirm')
        self.assertEqual(self.post(10, {'force': True, 'confirmation_token': warning['confirmation_token']})['status'], 'success')
        with app.app_context():
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)

    def test_fully_counted_without_movement_completes_directly(self):
        with app.app_context():
            for item in InventoryCheckItem.query.filter_by(inventory_check_id=10):
                item.counted_by = 1
                item.counted_at = datetime.datetime(2020, 1, 1, 10, 1)
                item.actual_stock = item.system_stock
                item.difference = 0
            db.session.commit()
        response = self.post(10, {})
        self.assertEqual(response['status'], 'success')
        self.assertIn('无库存差异', response['msg'])
        with app.app_context():
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)

    def test_current_check_own_transaction_is_excluded(self):
        with app.app_context():
            for item in InventoryCheckItem.query.filter_by(inventory_check_id=10):
                item.counted_by = 1
                item.counted_at = datetime.datetime(2020, 1, 1, 10, 1)
                item.actual_stock = item.system_stock
                item.difference = 0
            db.session.add(StockTransaction(material_id=10, warehouse_id=1, quantity=-10,
                created_at=datetime.datetime(2020, 1, 1, 10, 2), transaction_type='out',
                reference_type='check', reference_id=10))
            db.session.commit()
        self.assertEqual(self.post(10, {})['status'], 'success')
        with app.app_context():
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)
            self.assertEqual(StockTransaction.query.count(), 1)

    def test_all_uncounted_no_difference_after_confirmation_has_no_draft(self):
        with app.app_context():
            for item in InventoryCheckItem.query.filter_by(inventory_check_id=10):
                item.counted_by = None
                item.counted_at = None
                item.actual_stock = item.system_stock
                item.difference = 0
            db.session.commit()
        warning = self.post(10, {'force': True})
        self.assertEqual((warning['status'], warning['code']), ('confirm', 'check_risks'))
        self.assertIn('2 行未盘', warning['msg'])
        self.assertEqual(self.post(10, {'force': True, 'confirmation_token': warning['confirmation_token']})['status'],
                         'success')
        with app.app_context():
            self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)

    def test_area_rows_preserve_exact_combined_net_after_confirmation(self):
        with app.app_context():
            first = db.session.get(InventoryCheckItem, 10)
            second = db.session.get(InventoryCheckItem, 11)
            first.system_stock, first.actual_stock, first.area = 100, 30, 'Zone A'
            second.material_id, second.system_stock, second.actual_stock, second.area = 10, 100, 68, 'Zone B'
            first.counted_by = second.counted_by = None
            first.counted_at = second.counted_at = None
            db.session.commit()
        warning = self.post(10, {'force': True})
        self.assertEqual(warning['status'], 'confirm')
        self.assertIn('2 行未盘', warning['msg'])
        self.assertEqual(self.post(10, {'force': True, 'confirmation_token': warning['confirmation_token']})['status'],
                         'success')
        with app.app_context():
            order = AdjustmentOrder.query.filter_by(source_id=10).one()
            item = AdjustmentOrderItem.query.filter_by(adjustment_order_id=order.id).one()
            self.assertEqual((order.status, order.warehouse, item.quantity), ('pending', '合成仓', -2))
            self.assertEqual(StockTransaction.query.count(), 0)

    def test_area_location_guard_remains_after_confirmation(self):
        with app.app_context():
            first = db.session.get(InventoryCheckItem, 10)
            second = db.session.get(InventoryCheckItem, 11)
            first.system_stock, first.actual_stock, first.area = 100, 100, 'Location 1'
            second.material_id, second.system_stock, second.actual_stock, second.area = 10, 100, 2, 'Location 2'
            db.session.commit()
        settings['location'] = True
        try:
            warning = self.post(10, {'force': True})
            self.assertEqual(warning['status'], 'confirm')
            response = self.client.post('/synthetic/check/10/complete',
                                        json={'force': True, 'confirmation_token': warning['confirmation_token']},
                                        headers=self.headers)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json['status'], 'error')
            self.assertIn('不能跨多个区域合并', response.json['msg'])
            with app.app_context():
                self.assertEqual(AdjustmentOrder.query.filter_by(source_id=10).count(), 0)
                self.assertEqual(db.session.get(InventoryCheck, 10).status, 'pending')
        finally:
            settings['location'] = False

    def test_two_warehouse_stock_unchanged_and_only_plus_two_draft(self):
        with app.app_context():
            first = db.session.get(InventoryCheckItem, 10)
            first.system_stock, first.actual_stock, first.difference = 10, 12, 2
            db.session.delete(db.session.get(InventoryCheckItem, 11))
            db.session.add_all([
                StockTransaction(material_id=10, warehouse_id=1, quantity=10,
                                 created_at=datetime.datetime(2019, 12, 31, 10), transaction_type='in'),
                StockTransaction(material_id=10, warehouse_id=2, quantity=20,
                                 created_at=datetime.datetime(2019, 12, 31, 10), transaction_type='in'),
                StockTransaction(material_id=10, warehouse_id=1, quantity=3,
                                 created_at=datetime.datetime(2020, 1, 1, 10, 2), transaction_type='in'),
            ])
            db.session.commit()
        def stock():
            with app.app_context():
                rows = StockTransaction.query.filter_by(material_id=10).order_by(StockTransaction.id).all()
                return ([sum(row.quantity for row in rows if row.warehouse_id == wh) for wh in (1, 2)],
                        [(row.id, row.warehouse_id, row.quantity) for row in rows])
        before = stock()
        self.assertEqual(before[0], [13, 20])
        with app.app_context():
            engine = db.engine
        def deny_schema(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith(('DROP ', 'ALTER ', 'CREATE ')):
                raise AssertionError('schema write forbidden during request')
        def deny_delete(_conn, cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith('DELETE ') and cursor.rowcount:
                raise AssertionError('nonempty delete forbidden during request')
        event.listen(engine, 'before_cursor_execute', deny_schema)
        event.listen(engine, 'after_cursor_execute', deny_delete)
        try:
            warning = self.post(10, {'force': False})
            self.assertEqual((warning['status'], warning['code']), ('confirm', 'check_risks'))
            self.assertIn('本仓 1 个物料发生出入库流水', warning['msg'])
            self.assertEqual([(row['code'], row['net']) for row in warning['samples']], [('M001', 3)])
            self.assertEqual(stock(), before)
            self.assertEqual(self.post(10, {'force': True})['status'], 'confirm')
            self.assertEqual(stock(), before)
            done = self.post(10, {'force': True, 'confirmation_token': warning['confirmation_token']})
            self.assertEqual(done['status'], 'success')
        finally:
            event.remove(engine, 'before_cursor_execute', deny_schema)
            event.remove(engine, 'after_cursor_execute', deny_delete)
        self.assertEqual(stock(), before)
        with app.app_context():
            draft = AdjustmentOrder.query.filter_by(source_type='check', source_id=10).one()
            self.assertEqual((draft.status, draft.warehouse), ('pending', '合成仓'))
            self.assertEqual(AdjustmentOrderItem.query.filter_by(adjustment_order_id=draft.id).one().quantity, 2)
'''


def main():
    source = Path(__file__).with_name('test_inventory_confirmation_flask_memory_20261109.py')
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    main_node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    classes = [node for node in main_node.body if isinstance(node, ast.ClassDef) and node.name == 'Integration']
    if len(classes) != 1:
        raise RuntimeError('isolation harness test class missing or ambiguous')
    classes[0].body = ast.parse(TESTS).body[0].body
    tests = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    if len(tests) != 12:
        raise RuntimeError('explicit synthetic test manifest incomplete')
    counts = [node for node in ast.walk(main_node) if isinstance(node, ast.Compare)
              and isinstance(node.left, ast.Call) and isinstance(node.left.func, ast.Attribute)
              and node.left.func.attr == 'countTestCases']
    if len(counts) != 1 or len(counts[0].comparators) != 1:
        raise RuntimeError('isolation harness count check missing')
    counts[0].comparators[0] = ast.Constant(value=12)
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    module = ast.fix_missing_locations(ast.Module(body=[*imports, main_node], type_ignores=[]))
    namespace = {'__file__': __file__}
    exec(compile(module, '<synthetic-check-contract>', 'exec'), namespace)
    namespace['main']()


if __name__ == '__main__':
    main()
