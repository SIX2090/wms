"""XFF trust-chain regressions, using only extracted functions and fake objects.

No application import, network, database, service or child process is used.
Run: python -I -B tests/test_xff_trust_boundary_20261108.py
"""
import ast
import ipaddress
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest.mock import MagicMock, patch


def _deny(*_args, **_kwargs):
    raise AssertionError('network, database and subprocess are forbidden')


ROOT = Path(__file__).resolve().parents[1]


def _source_function(path, name, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    code = compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                   '<isolated source function>', 'exec')
    exec(code, namespace)
    return namespace[name]


class XffTrustBoundary(unittest.TestCase):
    def setUp(self):
        for guard in (patch.object(socket.socket, 'connect', _deny),
                      patch.object(socket.socket, 'connect_ex', _deny),
                      patch.object(socket, 'create_connection', _deny),
                      patch.object(socket, 'getaddrinfo', _deny),
                      patch.object(sqlite3, 'connect', _deny),
                      patch.object(subprocess, 'Popen', _deny)):
            guard.start()
            self.addCleanup(guard.stop)
        self.request = types.SimpleNamespace(remote_addr='127.0.0.1', headers={})
        self.app = types.SimpleNamespace(config={'TRUSTED_PROXIES': ['127.0.0.1']})
        self.namespace = {'request': self.request, 'current_app': self.app, 'ipaddress': ipaddress}
        self.get_ip = _source_function(ROOT / 'app' / 'app.py', 'get_request_ip', self.namespace)

    def resolve(self, peer, header, trusted):
        self.request.remote_addr = peer
        self.request.headers = {} if header is None else {'X-Forwarded-For': header}
        self.app.config['TRUSTED_PROXIES'] = trusted
        return self.get_ip()

    def test_untrusted_or_missing_peer_does_not_trust_header(self):
        self.assertEqual(self.resolve('192.0.2.2', '198.51.100.1', ['127.0.0.1']), '192.0.2.2')
        self.assertEqual(self.resolve(None, '198.51.100.1', ['127.0.0.1']), '')
        self.assertEqual(self.resolve('invalid-peer', '198.51.100.1', ['invalid-peer']), 'invalid-peer')
        self.assertEqual(self.resolve('127.0.0.1', '198.51.100.1', []), '127.0.0.1')
        self.assertEqual(self.resolve('127.0.0.1', '198.51.100.1', ['invalid-proxy']), '127.0.0.1')

    def test_single_proxy_preserves_legitimate_client(self):
        self.assertEqual(self.resolve('127.0.0.1', '203.0.113.7', ['127.0.0.1']), '203.0.113.7')
        self.assertEqual(self.resolve('127.0.0.1', None, ['127.0.0.1']), '127.0.0.1')
        self.assertEqual(self.resolve('127.0.0.1', '', ['127.0.0.1']), '127.0.0.1')

    def test_spoofed_left_prefix_cannot_cross_first_untrusted_hop(self):
        self.assertEqual(self.resolve('127.0.0.1', '198.51.100.2, 203.0.113.7', ['127.0.0.1']),
                         '203.0.113.7')

    def test_multiple_configured_proxies(self):
        self.assertEqual(self.resolve('127.0.0.1', '198.51.100.2, 203.0.113.7, 10.0.0.2',
                                      ['127.0.0.1', '10.0.0.2']), '203.0.113.7')
        self.assertEqual(self.resolve('127.0.0.1', '10.0.0.1, 10.0.0.2',
                                      ['127.0.0.1', '10.0.0.2', '10.0.0.1']), '10.0.0.1')

    def test_ipv6_uses_ip_equality_not_textual_aliases(self):
        self.assertEqual(self.resolve('0:0:0:0:0:0:0:1', '2001:db8::4, 2001:db8::10',
                                      ['::1', '2001:0db8:0:0:0:0:0:10']), '2001:db8::4')
        self.assertEqual(self.resolve('::ffff:127.0.0.1', '198.51.100.1', ['127.0.0.1']),
                         '::ffff:127.0.0.1')

    def test_malformed_chain_refuses_all_forwarded_addresses(self):
        for header in ('not-an-ip, 203.0.113.7', ',203.0.113.7', '203.0.113.7,',
                       '203.0.113.7:80', '[2001:db8::4]', '  ', '2001:db8::1%eth0'):
            with self.subTest(header=header):
                self.assertEqual(self.resolve('127.0.0.1', header, ['127.0.0.1']), '127.0.0.1')

    def test_login_log_and_audit_use_the_checked_address(self):
        self.resolve('127.0.0.1', '198.51.100.2, 203.0.113.7', ['127.0.0.1'])
        db = MagicMock()
        login_log = MagicMock()
        audit = MagicMock()
        self.namespace.update(db=db, LoginLog=login_log, OperationAudit=audit, json=json,
                              current_user=types.SimpleNamespace(is_authenticated=False),
                              app=types.SimpleNamespace(logger=MagicMock()))
        add_log = _source_function(ROOT / 'app' / 'app.py', 'add_login_log', self.namespace)
        audit_log = _source_function(ROOT / 'app' / 'app.py', 'log_audit', self.namespace)
        add_log('failed', 'synthetic')
        audit_log('synthetic', 'synthetic', 1)
        self.assertEqual(login_log.call_args.kwargs['login_ip'], '203.0.113.7')
        self.assertEqual(audit.call_args.kwargs['ip_address'], '203.0.113.7')
        self.assertEqual(db.session.add.call_count, 2)

    def test_web_and_native_rate_keys_share_the_resolved_address(self):
        self.resolve('127.0.0.1', '198.51.100.2, 203.0.113.7', ['127.0.0.1'])
        for path, name in (('app/routes/user_auth.py', 'login'),
                           ('app/routes/native_api.py', 'native_api_login')):
            with self.subTest(path=path):
                tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
                fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
                selected = []
                for statement in ast.walk(fn):
                    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                        target = statement.targets[0]
                        if isinstance(target, ast.Name) and target.id in ('request_ip', 'rate_key'):
                            selected.append(statement)
                ip_assignment = next(n for n in selected if n.targets[0].id == 'request_ip')
                rate_assignment = next(n for n in selected if n.targets[0].id == 'rate_key')
                local = {'get_request_ip': self.get_ip}
                code = compile(ast.fix_missing_locations(ast.Module(body=[ip_assignment, rate_assignment],
                                                                     type_ignores=[])), '<rate key>', 'exec')
                exec(code, local)
                self.assertEqual(local['rate_key'], 'login_fail:203.0.113.7')


if __name__ == '__main__':
    unittest.main()
