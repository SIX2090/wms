"""Synthetic Flask requests; no WMS app, DB, network, subprocess, or real accounts."""
import os
import subprocess
import sys


def main():
    import ast
    import builtins
    from collections import deque
    import ipaddress
    import json
    from pathlib import Path
    import socket
    import sqlite3
    import sysconfig
    import threading
    import time
    import types
    import unittest
    from unittest.mock import MagicMock

    def refuse(*_args, **_kwargs):
        raise AssertionError('database, network, WMS and subprocess are forbidden')

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
    # Explicit dependency path only: -S prevents sitecustomize and .pth startup.
    sys.path.append(sysconfig.get_paths()['purelib'])
    from flask import Flask, current_app, jsonify, request

    root = Path(__file__).resolve().parents[1]

    def extract(path, name, *, strip_imports=()):
        tree = ast.parse((root / path).read_text(encoding='utf-8-sig'))
        found = [item for item in ast.walk(tree) if isinstance(item, ast.FunctionDef) and item.name == name]
        if len(found) != 1:
            raise AssertionError('source function missing or ambiguous: ' + name)
        function = found[0]
        function.decorator_list = []
        function.body = [node for node in function.body if not (
            isinstance(node, ast.ImportFrom) and node.module in strip_imports)]
        return function

    def compile_into(namespace, *functions):
        tree = ast.fix_missing_locations(ast.Module(body=list(functions), type_ignores=[]))
        exec(compile(tree, '<synthetic-xff-functions>', 'exec'), namespace)

    class SyntheticRateAndAudit(unittest.TestCase):
        def setUp(self):
            self.app = Flask('synthetic-xff')
            self.app.config.update(TRUSTED_PROXIES=['127.0.0.1', '10.0.0.2'], TESTING=True)
            self.records = []
            self.session = types.SimpleNamespace(add=self.records.append, commit=lambda: None,
                                                  rollback=lambda: None)
            self.user = types.SimpleNamespace(is_authenticated=False)
            query = types.SimpleNamespace(filter_by=lambda **_kw: types.SimpleNamespace(first=lambda: None))
            ns = {
                'request': request, 'current_app': current_app, 'ipaddress': ipaddress,
                'db': types.SimpleNamespace(session=self.session),
                'current_user': self.user, 'app': self.app, 'jsonify': jsonify, 'json': json,
                'LoginLog': lambda **values: ('login', values),
                'OperationAudit': lambda **values: ('audit', values),
                'User': types.SimpleNamespace(query=query),
                'LOGIN_IP_RATE_LIMIT_PER_MINUTE': 2,
                '_LOCK': threading.Lock(), '_BUCKETS': {}, 'deque': deque, 'time': time,
                'flash': lambda *_args: None,
                'render_template': lambda *_args, **_kwargs: 'synthetic login',
                'api_json_error': lambda msg, code: (jsonify({'status': 'error', 'msg': msg}), code),
                '_ensure_login_schema': lambda: None,
            }
            compile_into(ns, extract('app/app.py', 'get_request_ip'),
                         extract('app/app.py', 'add_login_log'),
                         extract('app/app.py', 'log_audit'),
                         extract('app/rate_limit.py', '_prune'),
                         extract('app/rate_limit.py', 'is_rate_limited'),
                         extract('app/rate_limit.py', 'record_failure'),
                         extract('app/routes/user_auth.py', 'login', strip_imports=('app', 'rate_limit', 'flask_login', 'werkzeug.security')),
                         extract('app/routes/native_api.py', 'native_api_login', strip_imports=('app', 'rate_limit', 'werkzeug.security')))
            self.functions = ns
            self.app.add_url_rule('/login', 'login', ns['login'], methods=['POST'])
            self.app.add_url_rule('/api/login', 'native_login', ns['native_api_login'], methods=['POST'])

            def audit():
                ns['log_audit']('synthetic', 'synthetic', 1)
                return 'ok'
            self.app.add_url_rule('/audit', 'audit', audit, methods=['POST'])
            self.client = self.app.test_client()

        def post(self, path, peer, xff):
            # The Flask client is in-process WSGI; socket/network operations are denied.
            kwargs = {'environ_overrides': {'REMOTE_ADDR': peer}, 'headers': {'X-Forwarded-For': xff}}
            if path == '/login':
                kwargs['data'] = {'username': 'synthetic-user', 'password': 'synthetic-value'}
            elif path == '/api/login':
                kwargs['json'] = {'username': 'synthetic-user', 'password': 'synthetic-value'}
            return self.client.post(path, **kwargs)

        def test_web_native_share_rate_bucket_and_trusted_chain(self):
            first = '198.51.100.10, 203.0.113.7, 10.0.0.2'
            forged = '198.51.100.11, 203.0.113.7, 10.0.0.2'
            self.assertEqual(self.post('/login', '127.0.0.1', first).status_code, 401)
            self.assertEqual(self.post('/api/login', '127.0.0.1', forged).status_code, 401)
            self.assertEqual(self.post('/login', '127.0.0.1', forged).status_code, 429)
            self.assertEqual(self.post('/api/login', '127.0.0.1', first).status_code, 429)
            self.assertEqual(self.post('/api/login', '127.0.0.1', '203.0.113.8, 10.0.0.2').status_code, 401)
            login_ips = [item[1]['login_ip'] for item in self.records if item[0] == 'login']
            self.assertEqual(login_ips, ['203.0.113.7', '203.0.113.7', '203.0.113.8'])
            self.assertEqual(set(self.functions['_BUCKETS']), {'login_fail:203.0.113.7', 'login_fail:203.0.113.8'})

        def test_untrusted_peer_ignores_spoofed_header(self):
            for spoof in ('198.51.100.10', '198.51.100.11'):
                self.assertEqual(self.post('/api/login', '192.0.2.5', spoof).status_code, 401)
            self.assertEqual(self.post('/login', '192.0.2.5', '198.51.100.12').status_code, 429)
            self.assertEqual(set(self.functions['_BUCKETS']), {'login_fail:192.0.2.5'})

        def test_malformed_xff_falls_back_to_peer(self):
            self.assertEqual(self.post('/api/login', '127.0.0.1', '198.51.100.1, broken').status_code, 401)
            self.assertEqual(self.records[-1][1]['login_ip'], '127.0.0.1')
            self.assertIn('login_fail:127.0.0.1', self.functions['_BUCKETS'])

        def test_ipv6_audit_uses_same_chain_resolution(self):
            self.app.config['TRUSTED_PROXIES'] = ['::1', '2001:db8::10']
            response = self.post('/audit', '::1', '2001:db8::beef, 2001:db8::4, 2001:db8::10')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.records[-1][0], 'audit')
            self.assertEqual(self.records[-1][1]['ip_address'], '2001:db8::4')

        def test_ipv6_web_native_share_client_rate_bucket(self):
            self.app.config['TRUSTED_PROXIES'] = ['::1', '2001:db8::10']
            first = '2001:db8::beef, 2001:db8::4, 2001:db8::10'
            second = '2001:db8::cafe, 2001:db8::4, 2001:db8::10'
            self.assertEqual(self.post('/login', '::1', first).status_code, 401)
            self.assertEqual(self.post('/api/login', '::1', second).status_code, 401)
            self.assertEqual(self.post('/login', '::1', first).status_code, 429)
            self.assertEqual(set(self.functions['_BUCKETS']), {'login_fail:2001:db8::4'})

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticRateAndAudit)
    if suite.countTestCases() != 5:
        raise SystemExit('synthetic Flask test list is incomplete or empty')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


def test_xff_flask_login_audit_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    main()
