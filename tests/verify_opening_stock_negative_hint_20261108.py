"""Reproduce opening-stock hints with synthetic in-memory SQLite only.

Execute explicitly: python -I -S -B -X utf8 this_file.py. Current WMS code is
expected to fail warehouse-specific cases; no WMS app or database is opened.
"""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    from decimal import Decimal, ROUND_HALF_UP
    from datetime import datetime
    import math
    from pathlib import Path
    import platform
    import socket
    import sqlite3
    import sysconfig
    import types
    import unittest

    def deny(*_args, **_kwargs):
        raise AssertionError('真实应用、外部连接、文件数据库和子进程均禁止')

    class DeniedPopen:
        def __init__(self, *_args, **_kwargs):
            deny()

    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            deny()
        return original_import(name, *args, **kwargs)

    memory_connect = sqlite3.connect
    sqlite3.connect = sqlite3.dbapi2.connect = deny
    socket.socket.connect = socket.socket.connect_ex = deny
    socket.create_connection = socket.getaddrinfo = deny
    subprocess.Popen = DeniedPopen
    platform.machine = lambda: 'synthetic'
    builtins.__import__ = guarded_import
    sys.path.append(sysconfig.get_paths()['purelib'])
    from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, and_, case, create_engine, func, or_, text, update
    from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship

    root = Path(__file__).resolve().parents[1]
    source = ast.parse((root / 'app/app.py').read_text(encoding='utf-8-sig'))
    utils = ast.parse((root / 'app/utils.py').read_text(encoding='utf-8-sig'))
    identity = ast.parse((root / 'app/services/warehouse_identity.py').read_text(encoding='utf-8-sig'))

    def function(tree, name):
        matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(matches) != 1:
            raise AssertionError('源码函数不存在或不唯一：' + name)
        matches[0].decorator_list = []
        return matches[0]

    class Base(DeclarativeBase):
        pass

    class Material(Base):
        __tablename__ = 'synthetic_material'
        id: Mapped[int] = mapped_column(primary_key=True)
        code: Mapped[str] = mapped_column(String)
        stock: Mapped[float] = mapped_column(Float)

    class Warehouse(Base):
        __tablename__ = 'synthetic_warehouse'
        id: Mapped[int] = mapped_column(primary_key=True)
        name: Mapped[str] = mapped_column(String)
        code: Mapped[str] = mapped_column(String)

    class StockTransaction(Base):
        __tablename__ = 'synthetic_txn'
        id: Mapped[int] = mapped_column(primary_key=True)
        material_id: Mapped[int] = mapped_column(ForeignKey('synthetic_material.id'))
        warehouse_id: Mapped[int | None] = mapped_column(ForeignKey('synthetic_warehouse.id'))
        quantity: Mapped[float] = mapped_column(Float)
        location: Mapped[str | None] = mapped_column(String)
        reference_type: Mapped[str | None] = mapped_column(String)
        reference_id: Mapped[int | None] = mapped_column(Integer)

    class LocationInventory(Base):
        __tablename__ = 'synthetic_location'
        id: Mapped[int] = mapped_column(primary_key=True)
        material_id: Mapped[int] = mapped_column(ForeignKey('synthetic_material.id'))
        warehouse_id: Mapped[int | None] = mapped_column(ForeignKey('synthetic_warehouse.id'))
        location: Mapped[str] = mapped_column(String)
        quantity: Mapped[float] = mapped_column(Float)
        updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    class OpeningStockDoc(Base):
        __tablename__ = 'synthetic_opening_doc'
        id: Mapped[int] = mapped_column(primary_key=True)
        doc_no: Mapped[str] = mapped_column(String)
        lines = relationship('OpeningStock', cascade='all, delete-orphan')

    class OpeningStock(Base):
        __tablename__ = 'synthetic_opening'
        id: Mapped[int] = mapped_column(primary_key=True)
        material_id: Mapped[int] = mapped_column(ForeignKey('synthetic_material.id'))
        warehouse_id: Mapped[int | None] = mapped_column(ForeignKey('synthetic_warehouse.id'))
        doc_id: Mapped[int | None] = mapped_column(ForeignKey('synthetic_opening_doc.id'))
        quantity: Mapped[float] = mapped_column(Float)
        location: Mapped[str] = mapped_column(String, default='')
        material = relationship(Material)
        warehouse = relationship(Warehouse)

    class SourceDocument(Base):
        __tablename__ = 'synthetic_document'
        id: Mapped[int] = mapped_column(primary_key=True)
        warehouse_id: Mapped[int] = mapped_column(ForeignKey('synthetic_warehouse.id'))
        warehouse = relationship(Warehouse)

    class OpeningHintRegression(unittest.TestCase):
        def setUp(self):
            self.engine = create_engine('sqlite://', creator=lambda: memory_connect(':memory:'))
            Base.metadata.create_all(self.engine)
            self.session = Session(self.engine)
            self.assertTrue(all(row[1] in ('main', 'temp') and row[2] == ''
                                for row in self.session.execute(text('PRAGMA database_list'))))
            self.session.add_all([Material(id=1, code='SYNTH-M', stock=0),
                                  Warehouse(id=1, name='合成甲仓', code='SYN-A'),
                                  Warehouse(id=2, name='合成乙仓', code='SYN-B')])
            self.session.commit()
            Warehouse.query = self.session.query(Warehouse)
            Material.query = self.session.query(Material)
            StockTransaction.query = self.session.query(StockTransaction)
            LocationInventory.query = self.session.query(LocationInventory)
            SourceDocument.query = self.session.query(SourceDocument)
            OpeningStock.query = self.session.query(OpeningStock)
            OpeningStockDoc.query = self.session.query(OpeningStockDoc)
            self.location_enabled = False
            self.negative_location_allowed = False
            db = types.SimpleNamespace(session=self.session, and_=and_, or_=or_)

            self.ns = {'db': db, 'Material': Material, 'Warehouse': Warehouse,
                       'StockTransaction': StockTransaction, 'LocationInventory': LocationInventory,
                       'func': func, 'case': case, 'sa_update': update, 'STOCK_COMPARE_EPSILON': 1e-6,
                       'location_management_enabled': lambda: self.location_enabled,
                       'allow_negative_location_stock': lambda: self.negative_location_allowed,
                       'resolve_inventory_warehouse_id': lambda warehouse: warehouse.id if warehouse else None,
                       '_ledger_source_warehouse_getters': lambda: {
                           'synthetic_movement': (SourceDocument, lambda doc, _txn: doc.warehouse.name)},
                       'Decimal': Decimal, 'ROUND_HALF_UP': ROUND_HALF_UP, 'math': math,
                       'datetime': datetime}
            aliases = function(identity, 'warehouse_aliases')
            # Bind the real alias query to this fixture's synthetic models/session.
            # Keep its ambiguity checks; never import application models here.
            aliases.body = [node for node in aliases.body if not isinstance(node, ast.ImportFrom)]
            nodes = [function(utils, 'round_to_2_decimals'), function(utils, 'normalize_stock_quantity'), aliases,
                     function(source, 'get_warehouse_stock_quantities'),
                     function(source, '_warehouse_location_filter_values'),
                     function(source, '_ledger_source_warehouse_map'),
                     function(source, '_filter_txn_list_by_warehouse_scope'),
                     function(source, 'update_location_inventory'),
                     function(source, 'deduct_location_inventory_atomic'),
                     function(source, '_reverse_opening_stock_line'),
                     function(source, '_opening_stock_reverse_all_lines'),
                     function(source, '_opening_stock_negative_hint')]
            exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                         '<synthetic-opening-source>', 'exec'), self.ns)

        def tearDown(self):
            self.session.close()
            self.engine.dispose()

        def seed(self, openings, movements, locations=()):
            material = self.session.get(Material, 1)
            material.stock = sum(qty for _, qty in openings) + sum(qty for _, qty in movements)
            lines = []
            for number, (warehouse_id, quantity) in enumerate(openings, 1):
                line = OpeningStock(id=number, material_id=1, warehouse_id=warehouse_id,
                                    quantity=quantity, location='')
                lines.append(line)
                self.session.add(line)
                self.session.add(StockTransaction(material_id=1, warehouse_id=warehouse_id,
                    location=None, quantity=quantity, reference_type='opening_stock', reference_id=number))
            for warehouse_id, quantity in movements:
                self.session.add(StockTransaction(material_id=1, warehouse_id=warehouse_id,
                    location=None, quantity=quantity, reference_type='synthetic_movement', reference_id=1))
            for warehouse_id, quantity in locations:
                warehouse = self.session.get(Warehouse, warehouse_id)
                self.session.add(LocationInventory(material_id=1, warehouse_id=warehouse_id,
                                                   location=warehouse.name, quantity=quantity))
            self.session.commit()
            return lines

        def reverse(self, lines):
            for line in lines:
                self.assertEqual(self.ns['_reverse_opening_stock_line'](line), (True, ''))
            return self.ns['_opening_stock_negative_hint'](lines)

        def test_global_positive_but_selected_warehouse_negative(self):
            hints = self.reverse(self.seed([(1, 10)], [(1, -3), (2, 7)]))
            self.assertEqual(self.session.get(Material, 1).stock, 4)
            self.assertTrue(any('合成甲仓' in h and '-3' in h for h in hints), hints)
            self.assertFalse(any('合成乙仓' in h for h in hints))

        def test_global_negative_reports_each_warehouse_own_quantity(self):
            hints = self.reverse(self.seed([(1, 10), (2, 20)], [(1, -3), (2, -5)]))
            self.assertEqual(self.session.get(Material, 1).stock, -8)
            self.assertTrue(any('合成甲仓' in h and '-3' in h for h in hints), hints)
            self.assertTrue(any('合成乙仓' in h and '-5' in h for h in hints), hints)
            self.assertFalse(any('库存为 -8' in h for h in hints), hints)

        def test_global_negative_must_not_label_positive_warehouse(self):
            hints = self.reverse(self.seed([(1, 10)], [(1, 2), (2, -5)]))
            self.assertEqual(self.session.get(Material, 1).stock, -3)
            self.assertFalse(any('合成甲仓' in h and '-3' in h for h in hints), hints)

        def test_unknown_warehouse_not_falsely_attributed(self):
            hints = self.reverse(self.seed([(None, 10)], [(None, -3)]))
            self.assertEqual(self.session.get(Material, 1).stock, -3)
            self.assertTrue(any(('未知' in h or '无法确定' in h or '归属' in h) for h in hints), hints)
            self.assertFalse(any('在仓库 [' in h for h in hints), hints)

        def test_multiple_lines_same_warehouse_are_deduplicated(self):
            hints = self.reverse(self.seed([(1, 10), (1, 5)], [(1, -3), (2, 7)]))
            self.assertEqual(sum('合成甲仓' in h for h in hints), 1, hints)
            self.assertTrue(any('合成甲仓' in h and '-3' in h for h in hints), hints)

        def test_multiple_materials_share_warehouse_query_without_crossing_balances(self):
            lines = self.seed([(1, 10), (2, 20)], [(1, -3), (2, -5)])
            self.session.add(Material(id=2, code='SYNTH-N', stock=1))
            second = OpeningStock(id=3, material_id=2, warehouse_id=1, quantity=3, location='')
            self.session.add(second)
            self.session.add_all([
                StockTransaction(material_id=2, warehouse_id=1, location=None, quantity=3,
                                 reference_type='opening_stock', reference_id=3),
                StockTransaction(material_id=2, warehouse_id=1, location=None, quantity=-2,
                                 reference_type='synthetic_movement', reference_id=1),
            ])
            self.session.commit()
            calls = []
            original = self.ns['get_warehouse_stock_quantities']
            def observe(warehouse):
                calls.append(warehouse.id)
                return original(warehouse)
            self.ns['get_warehouse_stock_quantities'] = observe
            hints = self.reverse([*lines, second])
            self.assertEqual(calls, [1, 2])
            self.assertTrue(any('SYNTH-M' in h and '合成甲仓' in h and '-3' in h for h in hints), hints)
            self.assertTrue(any('SYNTH-M' in h and '合成乙仓' in h and '-5' in h for h in hints), hints)
            self.assertTrue(any('SYNTH-N' in h and '合成甲仓' in h and '-2' in h for h in hints), hints)

        def test_unknown_warehouse_is_visible_in_capped_route_message(self):
            lines = self.seed([(1, 10), (2, 20)], [(1, -3), (2, -5)])
            self.session.add_all([Material(id=2, code='SYNTH-N', stock=1),
                                  Material(id=3, code='SYNTH-U', stock=3)])
            known = OpeningStock(id=3, material_id=2, warehouse_id=1, quantity=3, location='')
            unknown = OpeningStock(id=4, material_id=3, warehouse_id=None, quantity=3, location='')
            self.session.add_all([known, unknown,
                StockTransaction(material_id=2, warehouse_id=1, location=None, quantity=3,
                                 reference_type='opening_stock', reference_id=3),
                StockTransaction(material_id=2, warehouse_id=1, location=None, quantity=-2,
                                 reference_type='synthetic_movement', reference_id=1),
                StockTransaction(material_id=3, warehouse_id=None, location=None, quantity=3,
                                 reference_type='opening_stock', reference_id=4),
            ])
            self.session.commit()
            hints = self.reverse([*lines, known, unknown])
            self.assertGreaterEqual(len(hints), 4)
            self.assertTrue(any('SYNTH-U' in h and '归属未知' in h for h in hints[:3]), hints)

        def test_lookup_failure_is_visible_in_capped_route_message(self):
            lines = self.seed([(1, 10), (2, 20)], [(1, -3), (2, -5)])
            self.session.add_all([Material(id=2, code='SYNTH-N', stock=1),
                                  Material(id=3, code='SYNTH-P', stock=2)])
            extras = []
            for row_id, material_id, movement in ((3, 2, -2), (4, 3, -1)):
                line = OpeningStock(id=row_id, material_id=material_id, warehouse_id=1,
                                    quantity=3, location='')
                extras.append(line)
                self.session.add_all([line,
                    StockTransaction(material_id=material_id, warehouse_id=1, location=None,
                                     quantity=3, reference_type='opening_stock', reference_id=row_id),
                    StockTransaction(material_id=material_id, warehouse_id=1, location=None,
                                     quantity=movement, reference_type='synthetic_movement', reference_id=1),
                ])
            self.session.commit()
            original = self.ns['get_warehouse_stock_quantities']
            def failed_second(warehouse):
                if warehouse.id == 2:
                    return self.session.execute(text('SELECT * FROM synthetic_missing_table')).all()
                return original(warehouse)
            self.ns['get_warehouse_stock_quantities'] = failed_second
            hints = self.reverse([lines[0], *extras, lines[1]])
            self.assertGreaterEqual(len(hints), 4)
            self.assertTrue(any('合成乙仓' in h and '无法' in h for h in hints[:3]), hints)

        def test_location_mode_positive_balance_preserves_normal_behavior(self):
            self.location_enabled = True
            hints = self.reverse(self.seed([(1, 2)], [(1, 1), (2, 7)], [(1, 3), (2, 7)]))
            self.assertEqual(hints, [])
            self.assertEqual(self.session.query(LocationInventory).filter_by(warehouse_id=1).one().quantity, 1)

        def test_location_failure_rollback_keeps_stock_and_transactions(self):
            self.location_enabled = True
            lines = self.seed([(1, 2)], [(1, 1), (2, 7)], [(1, 1), (2, 7)])
            before = (self.session.get(Material, 1).stock,
                      self.session.query(StockTransaction).count(),
                      self.session.query(LocationInventory).filter_by(warehouse_id=1).one().quantity)
            ok, _ = self.ns['_reverse_opening_stock_line'](lines[0])
            self.assertFalse(ok)
            self.session.rollback()
            after = (self.session.get(Material, 1).stock,
                     self.session.query(StockTransaction).count(),
                     self.session.query(LocationInventory).filter_by(warehouse_id=1).one().quantity)
            self.assertEqual(after, before)

        def test_location_mode_allows_negative_and_reports_correct_warehouse(self):
            self.location_enabled = True
            self.negative_location_allowed = True
            hints = self.reverse(self.seed([(1, 10)], [(1, -7), (2, 10)], [(1, 3), (2, 10)]))
            self.assertEqual(self.session.get(Material, 1).stock, 3)
            self.assertEqual(self.session.query(LocationInventory).filter_by(warehouse_id=1).one().quantity, -7)
            self.assertTrue(any('合成甲仓' in h and '-7' in h for h in hints), hints)
            self.assertFalse(any('合成乙仓' in h for h in hints))

        def test_later_warehouse_failure_rolls_back_both_warehouses(self):
            self.location_enabled = True
            lines = self.seed([(1, 2), (2, 2)], [(1, 1), (2, 1)], [(1, 3), (2, 1)])
            before = (self.session.get(Material, 1).stock,
                      self.session.query(StockTransaction).count(),
                      [r.quantity for r in self.session.query(LocationInventory)
                       .order_by(LocationInventory.warehouse_id)])
            ok, _message, reversed_count = self.ns['_opening_stock_reverse_all_lines'](
                types.SimpleNamespace(lines=lines))
            self.assertFalse(ok)
            self.assertEqual(reversed_count, 1)
            self.session.rollback()
            after = (self.session.get(Material, 1).stock,
                     self.session.query(StockTransaction).count(),
                     [r.quantity for r in self.session.query(LocationInventory)
                      .order_by(LocationInventory.warehouse_id)])
            self.assertEqual(after, before)

        def test_single_warehouse_keeps_existing_total_fallback(self):
            self.session.delete(self.session.get(Warehouse, 2))
            self.session.commit()
            hints = self.reverse(self.seed([(1, 10)], [(1, -3)]))
            self.assertEqual(self.session.get(Material, 1).stock, -3)
            self.assertTrue(any('合成甲仓' in h and '-3' in h for h in hints), hints)

        def test_unknown_historical_movement_not_assigned_to_known_warehouse(self):
            lines = self.seed([(1, 10)], [(1, -3), (2, 7), (None, -100)])
            hints = self.reverse(lines)
            self.assertEqual(self.session.get(Material, 1).stock, -96)
            self.assertTrue(any('合成甲仓' in h and '-3' in h for h in hints), hints)
            self.assertFalse(any('合成甲仓' in h and '-96' in h for h in hints), hints)

        def test_legacy_empty_location_uses_proved_source_warehouse(self):
            lines = self.seed([(1, 10)], [(2, 7), (None, -2)])
            self.session.add(SourceDocument(id=1, warehouse_id=1))
            self.session.commit()
            hints = self.reverse(lines)
            self.assertEqual(self.session.get(Material, 1).stock, 5)
            self.assertTrue(any('合成甲仓' in h and '-2' in h for h in hints), hints)

        def test_lookup_sql_error_does_not_undo_successful_reversal(self):
            lines = self.seed([(1, 10)], [(1, -3), (2, 7)])
            attempted = []
            def failing_lookup(warehouse):
                attempted.append(warehouse.id)
                return self.session.execute(text('SELECT * FROM synthetic_missing_table')).all()
            self.ns['get_warehouse_stock_quantities'] = failing_lookup
            hints = self.reverse(lines)
            self.assertEqual(attempted, [1])
            self.assertTrue(any('无法' in hint and '核' in hint for hint in hints), hints)
            self.session.delete(lines[0])
            self.session.commit()
            self.assertIsNone(self.session.get(OpeningStock, 1))
            self.assertEqual(self.session.get(Material, 1).stock, 4)
            self.assertEqual(self.session.query(StockTransaction).count(), 2)

        def test_one_warehouse_lookup_failure_does_not_hide_other_warehouse(self):
            lines = self.seed([(1, 10), (2, 20)], [(1, -3), (2, -5)])
            original = self.ns['get_warehouse_stock_quantities']
            def one_failure(warehouse):
                if warehouse.id == 1:
                    return self.session.execute(text('SELECT * FROM synthetic_missing_table')).all()
                return original(warehouse)
            self.ns['get_warehouse_stock_quantities'] = one_failure
            hints = self.reverse(lines)
            self.assertTrue(any('合成甲仓' in hint and '无法' in hint for hint in hints), hints)
            self.assertTrue(any('合成乙仓' in hint and '-5' in hint for hint in hints), hints)
            self.session.delete(lines[0])
            self.session.delete(lines[1])
            self.session.commit()
            self.assertEqual(self.session.query(OpeningStock).count(), 0)
            self.assertEqual(self.session.get(Material, 1).stock, -8)

        def test_outer_rollback_after_hints_restores_all_balances_and_transactions(self):
            lines = self.seed([(1, 10), (2, 20)], [(1, -3), (2, -5)])
            initial_stock = self.session.get(Material, 1).stock
            initial_txns = self.session.query(StockTransaction).count()
            hints = self.reverse(lines)
            self.assertTrue(any('合成甲仓' in hint and '-3' in hint for hint in hints), hints)
            self.session.delete(lines[0])
            self.session.delete(lines[1])
            self.session.rollback()
            self.assertEqual(self.session.get(Material, 1).stock, initial_stock)
            self.assertEqual(self.session.query(StockTransaction).count(), initial_txns)
            self.assertEqual(self.session.query(OpeningStock).count(), 2)

        def test_savepoint_creation_error_does_not_undo_reversal(self):
            lines = self.seed([(1, 10)], [(1, -3), (2, 7)])
            self.assertEqual(self.ns['_reverse_opening_stock_line'](lines[0]), (True, ''))
            connection = self.session.connection().connection.driver_connection
            denied = []
            def authorizer(action, name, _second, _database, _source):
                if action == sqlite3.SQLITE_SAVEPOINT and name == 'BEGIN':
                    denied.append(name)
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            connection.set_authorizer(authorizer)
            try:
                hints = self.ns['_opening_stock_negative_hint'](lines)
                self.assertTrue(denied, '必须确实触发合成保存点错误')
                self.assertTrue(any('无法' in hint for hint in hints), hints)
                self.session.delete(lines[0])
                self.session.commit()
                self.assertIsNone(self.session.get(OpeningStock, 1))
                self.assertEqual(self.session.get(Material, 1).stock, 4)
                self.assertEqual(self.session.query(StockTransaction).count(), 2)
            finally:
                connection.set_authorizer(None)

        def test_savepoint_release_error_does_not_undo_reversal(self):
            lines = self.seed([(1, 10)], [(1, -3), (2, 7)])
            self.assertEqual(self.ns['_reverse_opening_stock_line'](lines[0]), (True, ''))
            connection = self.session.connection().connection.driver_connection
            denied = []
            def authorizer(action, name, _second, _database, _source):
                if action == sqlite3.SQLITE_SAVEPOINT and name == 'RELEASE':
                    denied.append(name)
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            connection.set_authorizer(authorizer)
            try:
                hints = self.ns['_opening_stock_negative_hint'](lines)
                self.assertTrue(denied, '必须确实触发合成保存点释放错误')
                self.assertTrue(any('无法' in hint for hint in hints), hints)
                self.session.delete(lines[0])
                self.session.commit()
                self.assertIsNone(self.session.get(OpeningStock, 1))
                self.assertEqual(self.session.get(Material, 1).stock, 4)
                self.assertEqual(self.session.query(StockTransaction).count(), 2)
            finally:
                connection.set_authorizer(None)

        def route_with_lookup_failure(self, name):
            lines = self.seed([(1, 10)], [(1, -3), (2, 7)])
            self.session.add(OpeningStockDoc(id=1, doc_no='QS-SYNTH'))
            lines[0].doc_id = 1
            self.session.commit()
            def failing_lookup(_warehouse):
                return self.session.execute(text('SELECT * FROM synthetic_missing_table')).all()
            self.ns['get_warehouse_stock_quantities'] = failing_lookup
            self.ns.update({
                'OpeningStock': OpeningStock, 'OpeningStockDoc': OpeningStockDoc,
                'jsonify': lambda payload: payload, 'log_operation': lambda *_args: None,
                'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *_args: None)),
                'request': types.SimpleNamespace(get_json=lambda **_kwargs: {
                    'line_ids': [1], 'confirm': True}),
            })
            route_source = ast.parse((root / 'app/routes/opening_stock.py').read_text(encoding='utf-8-sig'))
            matches = [node for node in ast.walk(route_source)
                       if isinstance(node, ast.FunctionDef) and node.name == name]
            self.assertEqual(len(matches), 1)
            route = matches[0]
            route.decorator_list = []
            route.body = [node for node in route.body
                          if not (isinstance(node, ast.ImportFrom) and node.module == 'app')]
            exec(compile(ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[])),
                         '<synthetic-opening-route>', 'exec'), self.ns)
            result = self.ns[name]() if name == 'delete_all_opening_stock' else self.ns[name](1)
            self.assertEqual(result['status'], 'success')
            self.assertIn('无法', result['msg'])
            self.assertEqual(self.session.query(OpeningStock).count(), 0)
            self.assertEqual(self.session.get(Material, 1).stock, 4)
            self.assertEqual(self.session.query(StockTransaction).count(), 2)

        def test_delete_document_route_survives_hint_lookup_error(self):
            self.route_with_lookup_failure('delete_opening_stock_doc')

        def test_delete_lines_route_survives_hint_lookup_error(self):
            self.route_with_lookup_failure('batch_delete_opening_stock_lines')

        def test_delete_all_route_survives_hint_lookup_error(self):
            self.route_with_lookup_failure('delete_all_opening_stock')

        def route_with_many_hints(self, name):
            lines = self.seed([(1, 10), (2, 20)], [(1, -3), (2, -5)])
            self.session.add_all([OpeningStockDoc(id=1, doc_no='QS-SYNTH'),
                                  Material(id=2, code='SYNTH-N', stock=1),
                                  Material(id=3, code='SYNTH-U', stock=3)])
            known = OpeningStock(id=3, material_id=2, warehouse_id=1, quantity=3, location='')
            unknown = OpeningStock(id=4, material_id=3, warehouse_id=None, quantity=3, location='')
            self.session.add_all([known, unknown,
                StockTransaction(material_id=2, warehouse_id=1, location=None, quantity=3,
                                 reference_type='opening_stock', reference_id=3),
                StockTransaction(material_id=2, warehouse_id=1, location=None, quantity=-2,
                                 reference_type='synthetic_movement', reference_id=1),
                StockTransaction(material_id=3, warehouse_id=None, location=None, quantity=3,
                                 reference_type='opening_stock', reference_id=4),
            ])
            for line in [*lines, known, unknown]:
                line.doc_id = 1
            self.session.commit()
            self.ns.update({
                'OpeningStock': OpeningStock, 'OpeningStockDoc': OpeningStockDoc,
                'jsonify': lambda payload: payload, 'log_operation': lambda *_args: None,
                'app': types.SimpleNamespace(logger=types.SimpleNamespace(error=lambda *_args: None)),
                'request': types.SimpleNamespace(get_json=lambda **_kwargs: {
                    'line_ids': [1, 2, 3, 4], 'confirm': True}),
            })
            route_source = ast.parse((root / 'app/routes/opening_stock.py').read_text(encoding='utf-8-sig'))
            matches = [node for node in ast.walk(route_source)
                       if isinstance(node, ast.FunctionDef) and node.name == name]
            self.assertEqual(len(matches), 1)
            route = matches[0]
            route.decorator_list = []
            route.body = [node for node in route.body
                          if not (isinstance(node, ast.ImportFrom) and node.module == 'app')]
            exec(compile(ast.fix_missing_locations(ast.Module(body=[route], type_ignores=[])),
                         '<synthetic-opening-route>', 'exec'), self.ns)
            result = self.ns[name]() if name == 'delete_all_opening_stock' else self.ns[name](1)
            self.assertEqual(result['status'], 'success')
            self.assertIn('归属未知', result['msg'])
            self.assertIn('另有 1 条提示', result['msg'])
            self.assertEqual(self.session.query(OpeningStock).count(), 0)
            self.assertEqual(self.session.query(StockTransaction).count(), 3)

        def test_delete_document_route_reports_omitted_hints(self):
            self.route_with_many_hints('delete_opening_stock_doc')

        def test_delete_lines_route_reports_omitted_hints(self):
            self.route_with_many_hints('batch_delete_opening_stock_lines')

        def test_delete_all_route_reports_omitted_hints(self):
            self.route_with_many_hints('delete_all_opening_stock')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OpeningHintRegression)
    if suite.countTestCases() != 26:
        raise SystemExit('期初提示测试清单不完整或为空')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def test_opening_hints_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
