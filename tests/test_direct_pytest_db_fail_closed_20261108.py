"""Offline checks for direct pytest paths whose app import is not isolated."""
import ast
import builtins
from pathlib import Path
import socket
import sqlite3
import subprocess
import unittest
from unittest import mock


TESTS = Path(__file__).resolve().parent
TARGETS = (
    'test_ai_document_gate_wiring.py', 'test_ai_draft_idempotency_lease.py',
    'test_audit_b11_material_stock_scope.py', 'test_audit_batch_entry_guards.py',
    'test_audit_b_group_alerts_stockquery_batch.py', 'test_audit_init_business_data_order.py',
    'test_audit_legacy_quick_issue_replay.py', 'test_audit_material_search_normalization.py',
    'test_audit_multiline_stock_aggregation.py', 'test_audit_price_dimension_flag.py',
    'test_audit_print_queue_csrf.py', 'test_builtin_print_template_excel.py', 'test_diag_push_tmp.py',
    'test_doc_print_excel_routes.py', 'test_label_excel_print_route.py', 'test_out_order_batch_paste.py',
    'test_out_order_print_signature.py', 'test_print_in_with_excel_layout.py',
    'test_print_template_center.py', 'test_print_template_pages.py',
    'test_report_excel_print_route.py', 'test_resolve_active_sales_warehouse.py',
    'test_runtime_status_integration.py',
)
MESSAGE = '安全阻断'


def first_executable(tree):
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    while body and isinstance(body[0], ast.ImportFrom) and body[0].module == '__future__':
        body.pop(0)
    return body[0]


def refuse(*_args, **_kwargs):
    raise AssertionError('database, network, application or child access')


class DirectPytestGuards(unittest.TestCase):
    def test_targets_are_nonempty_unique_and_guard_before_application(self):
        self.assertEqual(len(TARGETS), 23)
        self.assertEqual(len(set(TARGETS)), len(TARGETS))
        for name in TARGETS:
            with self.subTest(path=name):
                tree = ast.parse((TESTS / name).read_text(encoding='utf-8-sig'))
                guard = first_executable(tree)
                self.assertIsInstance(guard, ast.ImportFrom)
                self.assertEqual(guard.module, 'scripts.verify_db_guard')
                self.assertEqual([item.name for item in guard.names], ['require_isolated_test_runtime'])
                call = tree.body[tree.body.index(guard) + 1]
                self.assertIsInstance(call, ast.Expr)
                self.assertIsInstance(call.value, ast.Call)
                self.assertEqual(call.value.func.id, 'require_isolated_test_runtime')
                self.assertEqual(call.value.args, [])
                self.assertTrue(any(isinstance(n, ast.Import)
                                    and any(a.name == 'app' for a in n.names) for n in tree.body))

    def test_source_snapshot_stops_before_any_application_or_database_action(self):
        original_import = builtins.__import__
        def guarded_import(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                return refuse(name)
            return original_import(name, *args, **kwargs)
        with mock.patch.object(builtins, '__import__', side_effect=guarded_import), \
                mock.patch.object(sqlite3, 'connect', refuse), \
                mock.patch.object(socket.socket, 'connect', refuse), \
                mock.patch.object(socket.socket, 'connect_ex', refuse), \
                mock.patch.object(socket, 'getaddrinfo', refuse), \
                mock.patch.object(subprocess, 'Popen', refuse):
            for name in TARGETS:
                with self.subTest(path=name):
                    source = (TESTS / name).read_text(encoding='utf-8-sig')
                    tree = ast.parse(source)
                    self.test_targets_are_nonempty_unique_and_guard_before_application()
                    # Compile exactly the checked snapshot; an intervening file change
                    # cannot substitute unguarded code into this execution.
                    code = compile(tree, '<synthetic-direct-pytest>', 'exec')
                    with mock.patch.dict(__import__('os').environ, {}, clear=True), self.assertRaisesRegex(SystemExit, MESSAGE):
                        exec(code, {'__name__': 'synthetic_probe', '__file__': str(TESTS / name)})


if __name__ == '__main__':
    unittest.main()
