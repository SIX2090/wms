"""Synthetic trusted proxy audit inconsistency; current behavior is expected to fail."""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    import ipaddress
    from pathlib import Path
    import socket
    import sqlite3
    import sysconfig
    import types
    import unittest

    def refuse(*_args, **_kwargs):
        raise AssertionError('WMS import, DB, network and subprocess are forbidden')

    sqlite3.connect = refuse
    sqlite3.dbapi2.connect = refuse
    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.create_connection = refuse
    socket.getaddrinfo = refuse
    subprocess.Popen = refuse
    original_import = builtins.__import__

    def safe_import(name, *args, **kwargs):
        level = args[3] if len(args) > 3 else kwargs.get('level', 0)
        if level == 0 and (name == 'app' or name.startswith('app.')):
            return refuse()
        return original_import(name, *args, **kwargs)

    builtins.__import__ = safe_import
    sys.path.append(sysconfig.get_paths()['purelib'])
    from flask import Flask, current_app, request

    root = Path(__file__).resolve().parents[1]
    trees = {name: ast.parse((root / name).read_text(encoding='utf-8-sig'))
             for name in ('app/app.py', 'app/routes/in_order.py', 'app/routes/mobile.py')}

    def function(filename, name):
        found = [n for n in ast.walk(trees[filename]) if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(found) != 1:
            raise AssertionError('function is missing or ambiguous: ' + name)
        found[0].decorator_list = []
        return found[0]

    def operation_ip(filename, name):
        calls = [n for n in ast.walk(function(filename, name)) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'OperationLog']
        if len(calls) != 1:
            raise AssertionError('OperationLog construction is missing or ambiguous')
        args = [arg.value for arg in calls[0].keywords if arg.arg == 'ip_address']
        if len(args) != 1:
            raise AssertionError('OperationLog address is missing or ambiguous')
        return compile(ast.fix_missing_locations(ast.Expression(body=args[0])), '<synthetic-ip-expression>', 'eval')

    class OperationLogProxyConsistency(unittest.TestCase):
        def setUp(self):
            self.app = Flask('synthetic-operation-audit')
            self.app.config['TRUSTED_PROXIES'] = ['127.0.0.1', '10.0.0.2']
            self.records = []
            session = types.SimpleNamespace(add=self.records.append, commit=lambda: None, rollback=lambda: None)
            self.ns = {'request': request, 'current_app': current_app, 'ipaddress': ipaddress,
                       'db': types.SimpleNamespace(session=session),
                       'current_user': types.SimpleNamespace(is_authenticated=True, id=1),
                       'OperationLog': lambda **values: values, 'app': self.app}
            module = ast.fix_missing_locations(ast.Module(
                body=[function('app/app.py', 'get_request_ip'), function('app/app.py', 'log_operation')],
                type_ignores=[]))
            exec(compile(module, '<synthetic-operation-log>', 'exec'), self.ns)

        def context(self, xff='198.51.100.2, 203.0.113.7, 10.0.0.2'):
            return self.app.test_request_context('/synthetic', headers={'X-Forwarded-For': xff},
                                                 environ_overrides={'REMOTE_ADDR': '127.0.0.1'})

        def test_regular_operation_log_uses_resolved_client(self):
            with self.context():
                self.ns['log_operation']('synthetic', 'synthetic', 'synthetic', 1)
                self.assertEqual(self.ns['get_request_ip'](), '203.0.113.7')
                self.assertEqual(self.records[-1]['ip_address'], '203.0.113.7')

        def test_inbound_push_operation_log_uses_resolved_client(self):
            expr = operation_ip('app/routes/in_order.py', 'create_in_order_push')
            with self.context():
                self.assertEqual(eval(expr, self.ns), self.ns['get_request_ip']())

        def test_bearer_scan_operation_log_uses_resolved_client(self):
            expr = operation_ip('app/app.py', '_void_check_scan')
            with self.context():
                self.assertEqual(eval(expr, self.ns), self.ns['get_request_ip']())

        def test_invalid_chain_preserves_peer_fallback(self):
            with self.context('198.51.100.2, malformed'):
                self.ns['log_operation']('synthetic', 'synthetic', 'synthetic', 1)
                self.assertEqual(self.records[-1]['ip_address'], self.ns['get_request_ip']())
                self.assertEqual(self.records[-1]['ip_address'], '127.0.0.1')

        def test_operation_log_outside_request_preserves_none(self):
            self.ns['log_operation']('synthetic', 'synthetic', 'synthetic', 1)
            self.assertIsNone(self.records[-1]['ip_address'])

        def test_untrusted_direct_peer_cannot_spoof_audit_ip(self):
            with self.app.test_request_context('/synthetic',
                    headers={'X-Forwarded-For': '203.0.113.7'},
                    environ_overrides={'REMOTE_ADDR': '192.0.2.5'}):
                self.ns['log_operation']('synthetic', 'synthetic', 'synthetic', 1)
                self.assertEqual(self.records[-1]['ip_address'], '192.0.2.5')

        def test_mobile_recognition_fallback_uses_resolved_client(self):
            route = function('app/routes/mobile.py', 'mobile_recognize_material')
            assignments = [n for n in ast.walk(route) if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'rate_key' for t in n.targets)]
            self.assertEqual(len(assignments), 1)
            expr = compile(ast.fix_missing_locations(ast.Expression(body=assignments[0].value)),
                           '<synthetic-mobile-rate-key>', 'eval')
            self.ns['_user'] = None
            with self.context():
                self.assertEqual(eval(expr, self.ns), 'ip:203.0.113.7')
            with self.context('198.51.100.2, malformed'):
                self.assertEqual(eval(expr, self.ns), 'ip:127.0.0.1')
            self.ns['_user'] = types.SimpleNamespace(id=42)
            with self.context():
                self.assertEqual(eval(expr, self.ns), 'user:42')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OperationLogProxyConsistency)
    if suite.countTestCases() != 7:
        raise SystemExit('operation log test list is incomplete or empty')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def test_operation_log_proxy_ips_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
