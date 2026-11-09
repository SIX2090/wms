"""SQLite-only synthetic transition prototype; no WMS import or file DB.

An actual deployment must independently review schema, all consumers and
backends. Historical deleted numbers without records cannot be reconstructed.
"""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    from pathlib import Path
    import secrets
    import socket
    import sqlite3
    import threading
    import time
    import unittest
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch

    def deny(*_args, **_kwargs):
        raise AssertionError('application import, file DB, network and subprocess forbidden')
    actual_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            deny()
        return actual_import(name, *args, **kwargs)

    connect_memory = sqlite3.connect
    nonce = secrets.token_hex(16)
    uri = 'file:wms_trigger_' + nonce + '?mode=memory&cache=shared'
    def connect():
        if len(nonce) != 32 or any(c not in '0123456789abcdef' for c in nonce):
            raise AssertionError('invalid private memory DB identity')
        conn = connect_memory(uri, uri=True, isolation_level=None, timeout=0.2)
        rows = conn.execute('PRAGMA database_list').fetchall()
        if not rows or any(name not in ('main', 'temp') or path != '' for _, name, path in rows):
            conn.close()
            raise AssertionError('database is not a memory database')
        return conn

    # Fixed synthetic identifiers only. Shared SR, PR and SO exercise consumers
    # that use the same prefix from different source tables.
    sources = {
        'IN': (('inbound', 'number'),),
        'PI': (('inbound', 'number'),), 'OI': (('inbound', 'number'),),
        'OU': (('outbound', 'number'),), 'OO': (('outbound', 'number'),),
        'CK': (('inventory_check', 'number'),), 'CS': (('inventory_check_scan', 'number'),),
        'SC': (('subcontract_order', 'number'),), 'SUB': (('subcontract_order', 'number'),),
        'SF': (('subcontract_issue', 'number'),),
        'SR': (('inbound', 'number'), ('subcontract_receive', 'number')),
        'PR': (('purchase_request', 'number'), ('outbound', 'number')),
        'SO': (('sales_order', 'number'), ('outbound', 'number')),
        'PO': (('purchase_order', 'number'),), 'ASO': (('after_sale', 'number'),),
        'BOM': (('bom', 'number'),), 'REQ': (('requisition', 'number'),),
        'TF': (('transfer', 'number'),), 'ADJ': (('adjustment', 'number'),),
        'QS': (('opening_stock_doc', 'number'),),
    }
    tables = tuple(sorted({table for entries in sources.values() for table, _column in entries}))
    real_sources = {
        'IN': (('InOrder', 'order_no'),), 'PI': (('InOrder', 'order_no'),),
        'OI': (('InOrder', 'order_no'),), 'OU': (('OutOrder', 'order_no'),),
        'OO': (('OutOrder', 'order_no'),), 'CK': (('InventoryCheck', 'check_no'),),
        'CS': (('InventoryCheckScan', 'check_no'),), 'SC': (('SubcontractOrder', 'order_no'),),
        'SUB': (('SubcontractOrder', 'order_no'),), 'SF': (('SubcontractIssue', 'issue_no'),),
        'SR': (('InOrder', 'order_no'), ('SubcontractReceive', 'receive_no')),
        'PR': (('PurchaseRequest', 'request_no'), ('OutOrder', 'order_no')),
        'SO': (('SalesOrder', 'order_no'), ('OutOrder', 'order_no')),
        'PO': (('PurchaseOrder', 'order_no'),), 'ASO': (('AfterSaleOutOrder', 'order_no'),),
        'BOM': (('BOM', 'bom_no'),), 'REQ': (('ProductionRequisition', 'req_no'),),
        'TF': (('TransferOrder', 'transfer_no'),), 'ADJ': (('AdjustmentOrder', 'adjustment_no'),),
        'QS': (('OpeningStockDoc', 'doc_no'),),
    }
    model_to_synthetic = {
        'InOrder': 'inbound', 'OutOrder': 'outbound', 'InventoryCheck': 'inventory_check',
        'InventoryCheckScan': 'inventory_check_scan', 'SubcontractOrder': 'subcontract_order',
        'SubcontractIssue': 'subcontract_issue', 'SubcontractReceive': 'subcontract_receive',
        'PurchaseRequest': 'purchase_request', 'SalesOrder': 'sales_order', 'PurchaseOrder': 'purchase_order',
        'AfterSaleOutOrder': 'after_sale', 'BOM': 'bom', 'ProductionRequisition': 'requisition',
        'TransferOrder': 'transfer', 'AdjustmentOrder': 'adjustment', 'OpeningStockDoc': 'opening_stock_doc',
    }

    def begin(conn):
        deadline = time.monotonic() + 5
        while True:
            try:
                conn.execute('BEGIN IMMEDIATE')
                return
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() or time.monotonic() >= deadline:
                    raise
                time.sleep(0.005)

    def install(conn, fail=False, on_locked=None):
        """Prototype transition as one transaction; never used on real DBs."""
        begin(conn)
        try:
            if on_locked is not None:
                on_locked()
            previous_install = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name IN ('sequence_state', 'issued_number', 'issued_raw_number') LIMIT 1"
            ).fetchone() is not None
            def ensure_object(kind, name, sql):
                existing = conn.execute('SELECT type, sql FROM sqlite_master WHERE name=?', (name,)).fetchone()
                if existing:
                    if existing[0] != kind or existing[1].strip() != sql.strip():
                        raise RuntimeError('synthetic schema object mismatch: ' + name)
                else:
                    if previous_install:
                        raise RuntimeError('synthetic schema object missing: ' + name)
                    conn.execute(sql)
            ensure_object('table', 'sequence_state', 'CREATE TABLE sequence_state '
                          '(prefix TEXT NOT NULL, month TEXT NOT NULL, value TEXT NOT NULL, '
                          'PRIMARY KEY(prefix, month))')
            ensure_object('table', 'issued_number', 'CREATE TABLE issued_number '
                          '(prefix TEXT NOT NULL, month TEXT NOT NULL, value TEXT NOT NULL, '
                          'PRIMARY KEY(prefix, month, value))')
            ensure_object('table', 'issued_raw_number', 'CREATE TABLE issued_raw_number '
                          '(source TEXT NOT NULL, number TEXT NOT NULL, PRIMARY KEY(source, number))')
            for table in tables:
                for action in ('INSERT', 'UPDATE OF number'):
                    suffix = 'insert' if action == 'INSERT' else 'update'
                    changed = '' if action == 'INSERT' else ' AND OLD.number IS NOT NEW.number'
                    legacy = " AND substr(NEW.number, 1, 8) <> 'QSLEGACY'" if table == 'opening_stock_doc' else ''
                    name = f'claim_raw_{table}_{suffix}'
                    sql = f'''CREATE TRIGGER {name} BEFORE {action} ON {table}
                        WHEN NEW.number <> ''{legacy}{changed}
                        BEGIN
                          SELECT CASE WHEN EXISTS (
                            SELECT 1 FROM issued_raw_number WHERE source='{table}' AND number=NEW.number
                          ) THEN RAISE(ABORT, 'synthetic number already issued') END;
                          INSERT INTO issued_raw_number(source, number) VALUES ('{table}', NEW.number);
                        END'''
                    ensure_object('trigger', name, sql)
                for (number,) in conn.execute(f'SELECT number FROM {table}'):
                    if not isinstance(number, str) or not number:
                        continue
                    if table == 'opening_stock_doc' and number.startswith('QSLEGACY'):
                        continue
                    conn.execute('INSERT OR IGNORE INTO issued_raw_number VALUES (?, ?)', (table, number))
            for prefix, entries in sources.items():
                for table, column in entries:
                    # Fixed identifiers above are not supplied by test callers.
                    plen = len(prefix)
                    value = f"substr(NEW.{column}, {plen + 5})"
                    normalized = f"coalesce(nullif(ltrim({value}, '0'), ''), '0')"
                    valid = (f"substr(NEW.{column}, 1, {plen}) = '{prefix}' "
                             f"AND substr(NEW.{column}, {plen + 1}, 4) GLOB '[0-9][0-9][0-9][0-9]' "
                             f"AND {value} <> '' AND {value} NOT GLOB '*[^0-9]*'")
                    for action in ('INSERT', f'UPDATE OF {column}'):
                        suffix = 'insert' if action == 'INSERT' else 'update'
                        name = f'track_{table}_{prefix}_{suffix}'
                        changed = '' if action == 'INSERT' else f' AND OLD.{column} IS NOT NEW.{column}'
                        claim_name = f'claim_{table}_{prefix}_{suffix}'
                        claim_sql = f'''CREATE TRIGGER {claim_name} BEFORE {action} ON {table}
                            WHEN {valid}{changed}
                            BEGIN
                              SELECT CASE WHEN EXISTS (
                                SELECT 1 FROM issued_number WHERE prefix='{prefix}'
                                  AND month=substr(NEW.{column}, {plen + 1}, 4) AND value={normalized}
                              ) THEN RAISE(ABORT, 'synthetic number already issued') END;
                              INSERT INTO issued_number(prefix, month, value)
                              VALUES ('{prefix}', substr(NEW.{column}, {plen + 1}, 4), {normalized});
                            END'''
                        ensure_object('trigger', claim_name, claim_sql)
                        track_sql = f'''CREATE TRIGGER {name} AFTER {action} ON {table}
                            WHEN {valid}
                            BEGIN
                              INSERT INTO sequence_state(prefix, month, value)
                              VALUES ('{prefix}', substr(NEW.{column}, {plen + 1}, 4), {normalized})
                              ON CONFLICT(prefix, month) DO UPDATE SET value=excluded.value
                              WHERE length(excluded.value)>length(sequence_state.value)
                                 OR (length(excluded.value)=length(sequence_state.value)
                                     AND excluded.value > sequence_state.value COLLATE BINARY);
                            END'''
                        ensure_object('trigger', name, track_sql)
            # Same write transaction: no old writer can insert between seed and
            # trigger activation. Seeds use string comparison, not SQL integers.
            for prefix, entries in sources.items():
                high = {}
                for table, column in entries:
                    for (number,) in conn.execute(f'SELECT {column} FROM {table}'):
                        if not isinstance(number, str) or not number.startswith(prefix):
                            continue
                        rest = number[len(prefix):]
                        if len(rest) < 5 or not rest[:4].isascii() or not rest[:4].isdigit():
                            continue
                        suffix = rest[4:]
                        if not suffix.isascii() or not suffix.isdigit():
                            continue
                        canon = suffix.lstrip('0') or '0'
                        # Historical duplicates may exist across tables: keep
                        # their current rows while reserving their number once.
                        conn.execute('INSERT OR IGNORE INTO issued_number VALUES (?, ?, ?)',
                                     (prefix, rest[:4], canon))
                        if (len(canon), canon) > (len(high.get(rest[:4], '0')), high.get(rest[:4], '0')):
                            high[rest[:4]] = canon
                for month, value in high.items():
                    conn.execute('INSERT INTO sequence_state VALUES (?, ?, ?) '
                                 'ON CONFLICT(prefix, month) DO UPDATE SET value=excluded.value '
                                 'WHERE length(excluded.value)>length(sequence_state.value) '
                                 'OR (length(excluded.value)=length(sequence_state.value) '
                                 'AND excluded.value > sequence_state.value COLLATE BINARY)',
                                 (prefix, month, value))
            if fail:
                raise RuntimeError('synthetic schema failure')
            conn.commit()
        except BaseException:
            conn.rollback()
            raise

    def allocate(conn, prefix, month):
        # Caller must already own SQLite's writer reservation.
        if not conn.in_transaction:
            raise AssertionError('allocator requires the caller transaction')
        conn.execute('INSERT OR IGNORE INTO sequence_state VALUES (?, ?, ?)', (prefix, month, '0'))
        old = conn.execute('SELECT value FROM sequence_state WHERE prefix=? AND month=?',
                           (prefix, month)).fetchone()[0]
        number = int(old) + 1
        conn.execute('UPDATE sequence_state SET value=? WHERE prefix=? AND month=?',
                     (str(number), prefix, month))
        return prefix + month + f'{number:04d}'

    class Transition(unittest.TestCase):
        def setUp(self):
            blockers = [patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny),
                        patch.object(socket, 'getaddrinfo', deny), patch.object(socket, 'create_connection', deny),
                        patch.object(subprocess, 'Popen', deny), patch.object(sqlite3, 'connect', deny),
                        patch.object(builtins, '__import__', side_effect=guarded_import)]
            for blocker in blockers:
                blocker.start()
                self.addCleanup(blocker.stop)
            self.conn = connect()
            self.addCleanup(self.conn.close)
            for table in tables:
                self.conn.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, number TEXT NOT NULL UNIQUE)')

        def next(self, prefix='IN', month='2611', table='inbound'):
            begin(self.conn)
            try:
                number = allocate(self.conn, prefix, month)
                self.conn.execute(f'INSERT INTO {table}(number) VALUES (?)', (number,))
                self.conn.commit()
                return number
            except BaseException:
                self.conn.rollback()
                raise

        def test_seed_cross_table_and_five_digit_suffix(self):
            self.conn.execute("INSERT INTO inbound(number) VALUES ('SR26119999')")
            self.conn.execute("INSERT INTO subcontract_receive(number) VALUES ('SR261110000')")
            self.conn.execute("INSERT INTO sales_order(number) VALUES ('SO26110008')")
            self.conn.execute("INSERT INTO outbound(number) VALUES ('SO26110077')")
            install(self.conn)
            self.assertEqual(self.next('SR'), 'SR261110001')
            self.assertEqual(self.next('SO', table='outbound'), 'SO26110078')

        def test_all_current_prefix_families_track_old_writes_and_deletes(self):
            install(self.conn)
            for prefix, entries in sources.items():
                with self.subTest(prefix=prefix):
                    table = entries[0][0]
                    old = prefix + '26110077'
                    self.conn.execute(f'INSERT INTO {table}(number) VALUES (?)', (old,))
                    self.conn.execute(f'DELETE FROM {table} WHERE number=?', (old,))
                    self.assertEqual(self.next(prefix, table=table), prefix + '26110078')

        def test_documented_mapping_points_to_actual_model_fields(self):
            source = (Path(__file__).resolve().parents[1] / 'app/models/documents.py').read_text(encoding='utf-8-sig')
            classes = {node.name: node for node in ast.parse(source).body if isinstance(node, ast.ClassDef)}
            self.assertEqual(set(real_sources), set(sources))
            for prefix, entries in real_sources.items():
                self.assertEqual(tuple((model_to_synthetic[model], 'number') for model, _field in entries),
                                 sources[prefix])
                for model, field in entries:
                    self.assertIn(model, classes)
                    columns = {target.id for node in classes[model].body if isinstance(node, ast.Assign)
                               and isinstance(node.value, ast.Call)
                               for target in node.targets if isinstance(target, ast.Name)}
                    self.assertIn(field, columns, f'{model}.{field}')

        def test_real_generator_normalizes_out_alias(self):
            source = (Path(__file__).resolve().parents[1] / 'app/app.py').read_text(encoding='utf-8-sig')
            matches = [node for node in ast.parse(source).body
                       if isinstance(node, ast.FunctionDef) and node.name == 'generate_order_no']
            self.assertEqual(len(matches), 1)
            env = {'_order_no_generation_lock': threading.Lock(), '_generate_order_no_locked': lambda value: value}
            exec(compile(ast.fix_missing_locations(ast.Module(body=matches, type_ignores=[])),
                         '<generator-alias>', 'exec'), env)
            self.assertEqual(env['generate_order_no']('OUT'), 'OU')
            self.assertIn(env['generate_order_no']('OUT'), sources)

        def test_old_writer_insert_then_delete_still_advances_counter(self):
            install(self.conn)
            self.assertEqual(self.next(), 'IN26110001')
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110002')")
            self.conn.execute("DELETE FROM inbound WHERE number='IN26110002'")
            self.assertEqual(self.next(), 'IN26110003')

        def test_trigger_update_observes_changed_number(self):
            install(self.conn)
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110001')")
            self.conn.execute("UPDATE inbound SET number='IN26110010' WHERE number='IN26110001'")
            self.conn.execute("DELETE FROM inbound WHERE number='IN26110010'")
            self.assertEqual(self.next(), 'IN26110011')

        def test_old_writer_cannot_reuse_deleted_formal_number(self):
            install(self.conn)
            number = self.next()
            self.conn.execute('DELETE FROM inbound WHERE number=?', (number,))
            with self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute('INSERT INTO inbound(number) VALUES (?)', (number,))
            self.assertEqual(self.next(), 'IN26110002')

        def test_old_writer_insert_or_ignore_cannot_reuse_number(self):
            install(self.conn)
            number = self.next()
            self.conn.execute('DELETE FROM inbound WHERE number=?', (number,))
            try:
                self.conn.execute('INSERT OR IGNORE INTO inbound(number) VALUES (?)', (number,))
            except sqlite3.IntegrityError:
                pass
            self.assertEqual(self.conn.execute('SELECT count(*) FROM inbound WHERE number=?', (number,)).fetchone()[0], 0)

        def test_old_writer_insert_or_replace_cannot_reuse_number(self):
            install(self.conn)
            number = self.next()
            self.conn.execute('DELETE FROM inbound WHERE number=?', (number,))
            try:
                self.conn.execute('INSERT OR REPLACE INTO inbound(number) VALUES (?)', (number,))
            except sqlite3.IntegrityError:
                pass
            self.assertEqual(self.conn.execute('SELECT count(*) FROM inbound WHERE number=?', (number,)).fetchone()[0], 0)

        def test_old_writer_update_or_ignore_cannot_reuse_number(self):
            install(self.conn)
            number = self.next()
            self.conn.execute('DELETE FROM inbound WHERE number=?', (number,))
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110010')")
            try:
                self.conn.execute('UPDATE OR IGNORE inbound SET number=? WHERE number=?',
                                  (number, 'IN26110010'))
            except sqlite3.IntegrityError:
                pass
            self.assertEqual(self.conn.execute('SELECT number FROM inbound').fetchone()[0], 'IN26110010')

        def test_shared_prefix_old_writer_cannot_reuse_number_from_other_table(self):
            self.conn.execute("INSERT INTO inbound(number) VALUES ('SR26110001')")
            self.conn.execute("INSERT INTO subcontract_receive(number) VALUES ('SR26110001')")
            install(self.conn)
            self.conn.execute("DELETE FROM inbound WHERE number='SR26110001'")
            self.conn.execute("DELETE FROM subcontract_receive WHERE number='SR26110001'")
            with self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute("INSERT INTO subcontract_receive(number) VALUES ('SR26110001')")
            self.assertEqual(self.next('SR'), 'SR26110002')

        def test_existing_cross_table_duplicates_remain_editable_and_unchanged(self):
            self.conn.execute("INSERT INTO inbound(number) VALUES ('SR26110001')")
            self.conn.execute("INSERT INTO subcontract_receive(number) VALUES ('SR26110001')")
            install(self.conn)
            self.conn.execute('UPDATE inbound SET number=number')
            self.conn.execute('UPDATE subcontract_receive SET number=number')
            self.assertEqual(self.conn.execute('SELECT number FROM inbound').fetchone()[0], 'SR26110001')
            self.assertEqual(self.conn.execute('SELECT number FROM subcontract_receive').fetchone()[0], 'SR26110001')
            self.assertEqual(self.next('SR'), 'SR26110002')

        def test_legacy_transaction_rollback_does_not_consume(self):
            install(self.conn)
            begin(self.conn)
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110009')")
            self.conn.rollback()
            self.assertEqual(self.next(), 'IN26110001')

        def test_formal_transaction_rollback_does_not_consume(self):
            install(self.conn)
            begin(self.conn)
            self.assertEqual(allocate(self.conn, 'IN', '2611'), 'IN26110001')
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110001')")
            self.conn.rollback()
            self.assertEqual(self.next(), 'IN26110001')

        def test_schema_install_failure_is_atomic(self):
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110042')")
            with self.assertRaisesRegex(RuntimeError, 'synthetic schema failure'):
                install(self.conn, fail=True)
            self.assertIsNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='sequence_state'").fetchone())
            self.assertIsNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='issued_number'").fetchone())
            self.assertIsNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='issued_raw_number'").fetchone())
            self.assertEqual(self.conn.execute("SELECT count(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0], 0)
            self.assertEqual(self.conn.execute('SELECT number FROM inbound').fetchone()[0], 'IN26110042')
            install(self.conn)
            self.assertEqual(self.next(), 'IN26110043')

        def test_schema_reinstall_keeps_deleted_number_reservation(self):
            install(self.conn)
            number = self.next()
            self.conn.execute('DELETE FROM inbound WHERE number=?', (number,))
            install(self.conn)
            self.assertEqual(self.next(), 'IN26110002')
            with self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute('INSERT INTO inbound(number) VALUES (?)', (number,))

        def test_failed_reinstall_preserves_previous_protection(self):
            install(self.conn)
            number = self.next()
            self.conn.execute('DELETE FROM inbound WHERE number=?', (number,))
            with self.assertRaisesRegex(RuntimeError, 'synthetic schema failure'):
                install(self.conn, fail=True)
            with self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute('INSERT INTO inbound(number) VALUES (?)', (number,))
            self.assertEqual(self.next(), 'IN26110002')

        def test_existing_wrong_schema_is_rejected_and_not_replaced(self):
            self.conn.execute('CREATE TABLE sequence_state (wrong TEXT)')
            with self.assertRaisesRegex(RuntimeError, 'schema object mismatch'):
                install(self.conn)
            columns = self.conn.execute('PRAGMA table_info(sequence_state)').fetchall()
            self.assertEqual([column[1] for column in columns], ['wrong'])
            self.assertIsNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='issued_number'").fetchone())

        def test_existing_wrong_trigger_is_rejected_and_not_replaced(self):
            install(self.conn)
            self.conn.execute('DROP TRIGGER claim_inbound_IN_insert')
            self.conn.execute('CREATE TRIGGER claim_inbound_IN_insert BEFORE INSERT ON inbound BEGIN SELECT 1; END')
            with self.assertRaisesRegex(RuntimeError, 'schema object mismatch'):
                install(self.conn)
            definition = self.conn.execute("SELECT sql FROM sqlite_master WHERE name='claim_inbound_IN_insert'").fetchone()[0]
            self.assertIn('SELECT 1', definition)

        def test_missing_trigger_reinstall_fails_closed(self):
            install(self.conn)
            self.conn.execute('DROP TRIGGER claim_inbound_IN_insert')
            with self.assertRaisesRegex(RuntimeError, 'schema object missing'):
                install(self.conn)
            self.assertIsNone(self.conn.execute("SELECT name FROM sqlite_master WHERE name='claim_inbound_IN_insert'").fetchone())

        def test_malformed_suffix_and_month_are_ignored(self):
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110008x')")
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26XX0099')")
            install(self.conn)
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26110009x')")
            self.assertEqual(self.next(), 'IN26110001')

        def test_opening_stock_legacy_identifier_keeps_special_semantics(self):
            install(self.conn)
            self.conn.execute("INSERT INTO opening_stock_doc(number) VALUES ('QSLEGACY2611')")
            self.conn.execute("DELETE FROM opening_stock_doc WHERE number='QSLEGACY2611'")
            self.conn.execute("INSERT INTO opening_stock_doc(number) VALUES ('QSLEGACY2611')")
            self.assertEqual(self.conn.execute("SELECT count(*) FROM issued_number WHERE prefix='QS'").fetchone()[0], 0)
            self.assertEqual(self.next('QS', table='opening_stock_doc'), 'QS26110001')

        def test_deleted_imported_custom_number_cannot_be_reused(self):
            install(self.conn)
            self.conn.execute("INSERT INTO inbound(number) VALUES ('supplier-import-123')")
            self.conn.execute("DELETE FROM inbound WHERE number='supplier-import-123'")
            try:
                self.conn.execute("INSERT INTO inbound(number) VALUES ('supplier-import-123')")
            except sqlite3.IntegrityError:
                pass
            self.assertEqual(self.conn.execute("SELECT count(*) FROM inbound WHERE number='supplier-import-123'").fetchone()[0], 0,
                             '导入单据使用的非标准号删除后仍不得复用')

        def test_import_savepoints_keep_valid_rows_when_old_number_rejected(self):
            install(self.conn)
            used = self.next()
            self.conn.execute('DELETE FROM inbound WHERE number=?', (used,))
            begin(self.conn)
            self.conn.execute('SAVEPOINT import_one')
            self.conn.execute("INSERT INTO inbound(number) VALUES ('external-a')")
            self.conn.execute('RELEASE import_one')
            self.conn.execute('SAVEPOINT import_two')
            with self.assertRaises(sqlite3.IntegrityError):
                self.conn.execute('INSERT INTO inbound(number) VALUES (?)', (used,))
            self.conn.execute('ROLLBACK TO import_two')
            self.conn.execute('RELEASE import_two')
            self.conn.execute('SAVEPOINT import_three')
            self.conn.execute("INSERT INTO inbound(number) VALUES ('external-b')")
            self.conn.execute('RELEASE import_three')
            self.conn.commit()
            rows = self.conn.execute('SELECT number FROM inbound ORDER BY number').fetchall()
            self.assertEqual(rows, [('external-a',), ('external-b',)])

        def test_large_suffix_keeps_full_decimal_precision(self):
            self.conn.execute("INSERT INTO inbound(number) VALUES ('IN26119223372036854775809')")
            install(self.conn)
            self.assertEqual(self.next(), 'IN26119223372036854775810')

        def test_excessively_long_suffix_fails_without_losing_watermark(self):
            limit = sys.get_int_max_str_digits()
            if not limit:
                self.skipTest('interpreter has no integer digit limit')
            install(self.conn)
            suffix = '9' * (limit + 1)
            self.conn.execute('INSERT INTO inbound(number) VALUES (?)', ('IN2611' + suffix,))
            self.conn.execute('DELETE FROM inbound')
            with self.assertRaises(ValueError):
                self.next()
            self.assertEqual(self.conn.execute('SELECT value FROM sequence_state WHERE prefix=? AND month=?',
                                               ('IN', '2611')).fetchone()[0], suffix)
            self.assertEqual(self.conn.execute('SELECT count(*) FROM inbound').fetchone()[0], 0)

        def test_parallel_separate_connections_allocate_without_collision(self):
            install(self.conn)
            barrier = threading.Barrier(8)
            def worker(_index):
                conn = connect()
                try:
                    barrier.wait(timeout=5)
                    begin(conn)
                    number = allocate(conn, 'IN', '2611')
                    conn.execute('INSERT INTO inbound(number) VALUES (?)', (number,))
                    conn.commit()
                    return number
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(worker, range(8)))
            self.assertEqual(len(set(results)), 8)
            self.assertEqual(self.conn.execute('SELECT count(*) FROM inbound').fetchone()[0], 8)

        def test_parallel_legacy_writers_and_allocators_never_duplicate(self):
            install(self.conn)
            barrier = threading.Barrier(8)
            def worker(index):
                conn = connect()
                try:
                    barrier.wait(timeout=5)
                    begin(conn)
                    if index < 4:
                        number = f'IN2611{index + 1:04d}'
                    else:
                        number = allocate(conn, 'IN', '2611')
                    try:
                        conn.execute('INSERT INTO inbound(number) VALUES (?)', (number,))
                        conn.commit()
                        return number
                    except sqlite3.IntegrityError:
                        conn.rollback()
                        return None
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(worker, range(8)))
            successful = [number for number in results if number is not None]
            self.assertEqual(len(successful), len(set(successful)))
            self.assertEqual(self.conn.execute('SELECT count(*) FROM inbound').fetchone()[0], len(successful))
            self.assertTrue(successful)
            self.assertNotIn(self.next(), successful)

        def test_legacy_writer_waits_until_schema_transition_commits(self):
            entered = threading.Event()
            release = threading.Event()
            writer_started = threading.Event()
            writer_done = threading.Event()
            def on_locked():
                entered.set()
                if not release.wait(timeout=3):
                    raise TimeoutError('synthetic transition timeout')
            def migration():
                conn = connect()
                try:
                    install(conn, on_locked=on_locked)
                finally:
                    conn.close()
            def legacy_writer():
                conn = connect()
                try:
                    writer_started.set()
                    begin(conn)
                    conn.execute("INSERT INTO inbound(number) VALUES ('IN26110004')")
                    conn.commit()
                    conn.execute("DELETE FROM inbound WHERE number='IN26110004'")
                    writer_done.set()
                finally:
                    conn.close()
            with ThreadPoolExecutor(max_workers=2) as pool:
                transition = pool.submit(migration)
                self.assertTrue(entered.wait(timeout=3))
                writer = pool.submit(legacy_writer)
                self.assertTrue(writer_started.wait(timeout=3))
                try:
                    self.assertFalse(writer_done.wait(timeout=0.1))
                finally:
                    release.set()
                transition.result(timeout=5)
                writer.result(timeout=5)
            self.assertEqual(self.next(), 'IN26110005')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Transition)
    if suite.countTestCases() != 29:
        raise RuntimeError('synthetic test list incomplete')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())


def test_trigger_transition_in_isolated_subprocess():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
