"""Closed source/adapter checks only; never starts an app, listener or database."""
import ast
import builtins
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / 'scripts/diagnose_synthetic_push_tcp.py'


def _load():
    spec = importlib.util.spec_from_file_location('synthetic_tcp_diagnostic', DIAGNOSTIC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SyntheticTCPSourceTests(unittest.TestCase):
    def setUp(self):
        def deny(*args, **kwargs):
            raise AssertionError('app, DB, network and unowned child forbidden in source checks')
        self.deny = deny
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == 'app' or name.startswith('app.'):
                deny()
            return original(name, *args, **kwargs)
        for guard in (patch.object(builtins, '__import__', guarded),
                      patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'bind', deny),
                      patch.object(socket.socket, 'connect_ex', deny), patch.object(socket, 'getaddrinfo', deny),
                      patch.object(sqlite3, 'connect', deny), patch.object(subprocess, 'Popen', deny)):
            guard.start(); self.addCleanup(guard.stop)
        self.module = _load()

    def test_import_is_inert(self):
        before = set(sys.modules)
        _load()
        self.assertFalse(any(n == 'app' or n.startswith('app.') for n in set(sys.modules) - before))

    def test_diagnose(self):
        for rows in (None, True, 0, -1, 2, 500, 1.5, '1'):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.module.diagnose(rows)

    def test_handle_starttag(self):
        response = types.SimpleNamespace(text='<meta content="csrf&amp;value" name="csrf-token">'
            '<meta name="document-revision" content="signed-revision">', headers={})
        self.assertEqual(self.module._tokens(response, revision=True), ('csrf&value', 'signed-revision'))
        fallback = types.SimpleNamespace(text='<input name="csrf_token" value="form-token">',
                                         headers={'X-WMS-Document-Read-Revision': 'header-revision'})
        self.assertEqual(self.module._tokens(fallback, revision=True), ('form-token', 'header-revision'))

    def test_missing_tokens_do_not_fall_back_to_forged_values(self):
        for text in ('<title>login</title>', '<script>const x="<meta name=csrf-token content=fake>";</script>'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                self.module._tokens(types.SimpleNamespace(text=text, headers={}))
        with self.assertRaises(RuntimeError):
            self.module._tokens(types.SimpleNamespace(text='<meta name="csrf-token" content="csrf">', headers={}), revision=True)

    def test_os_memory_and_existing_listener_runtime_are_reused(self):
        tree = ast.parse(DIAGNOSTIC.read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'diagnose')
        calls = {n.func.id: n.lineno for statement in function.body
                 if isinstance(statement, ast.Expr) and isinstance((n := statement.value), ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id.startswith('require_')}
        initialize = next(n.lineno for n in ast.walk(function) if isinstance(n, ast.Call)
                          and isinstance(n.func, ast.Name) and n.func.id == 'initialize_synthetic_app')
        self.assertLess(calls['require_runtime'], calls['require_synthetic_memory_database'])
        self.assertLess(calls['require_synthetic_memory_database'], initialize)
        source = DIAGNOSTIC.read_text(encoding='utf-8')
        self.assertIn('with OwnedPerfHTTP(w, username, password) as server:', source)
        self.assertIn('WTF_CSRF_ENABLED=True', source)
        self.assertNotIn('WTF_CSRF_ENABLED=False', source)
        for forbidden in ('requests.Session(', 'socket.socket(', 'sqlite3.connect(', 'drop_all(', 'create_server('):
            self.assertNotIn(forbidden, source)

    def test_adapter_checks_relative_target_and_forbids_redirect_following(self):
        sys.path.insert(0, str(ROOT)); self.addCleanup(lambda: sys.path.remove(str(ROOT)))
        calls = []
        class Session:
            def request(inner, *args, **kwargs):
                calls.append((args, kwargs)); raise AssertionError('Unowned transport was called')
        server = types.SimpleNamespace(base_url='http://127.0.0.1:54321')
        for target in ('https://example.invalid/', '//example.invalid/', 'http://127.0.0.1:8080/', '/\\alias'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.module._request(server, Session(), 'GET', target)
        for method in ('PUT', 'DELETE', 'PATCH'):
            with self.subTest(method=method), self.assertRaises(RuntimeError):
                self.module._request(server, Session(), method, '/login')
        self.assertEqual(calls, [])
        # A plausible relative URL and fake components must also refuse before I/O.
        # No runtime guard is patched; positive TCP evidence belongs to Linux CI.
        with self.assertRaises((SystemExit, RuntimeError)):
            self.module._request(server, Session(), 'GET', '/login')
        self.assertEqual(calls, [])
        tree = ast.parse(DIAGNOSTIC.read_text(encoding='utf-8'))
        helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_request')
        transport = next(n for n in ast.walk(helper) if isinstance(n, ast.Call)
                         and isinstance(n.func, ast.Attribute) and n.func.attr == 'request')
        self.assertTrue(any(k.arg == 'allow_redirects' and isinstance(k.value, ast.Constant)
                            and k.value.value is False for k in transport.keywords))
        guard = next(n.lineno for n in ast.walk(helper) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == 'require_runtime')
        self.assertLess(guard, transport.lineno)
        source = ast.unparse(helper)
        for required in ('type(server) is OwnedPerfHTTP', 'isinstance(session, IsolatedSession)',
                         'owned is session', 'session.lease is server.lease',
                         'session.identity == server.identity', 'server.thread.is_alive()',
                         'server.lease.validate(server.identity)'):
            self.assertIn(required, source)

    def test_cli_has_no_target_or_credentials_escape(self):
        for args in ([], ['--scenario', 'other'], ['--scenario', 'inbound-push-tcp', '--rows', '2'],
                     ['--scenario', 'inbound-push-tcp', '--url', 'https://example.invalid'],
                     ['--scenario', 'inbound-push-tcp', '--database', 'unknown'],
                     ['--scenario', 'inbound-push-tcp', '--username', 'unknown']):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.module.main(args)
            self.assertEqual(error.exception.code, 2)

    def test_seven_business_stages_and_separate_protocol_reads(self):
        tree = ast.parse(DIAGNOSTIC.read_text(encoding='utf-8'))
        stages = [n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == 'stage'
                  and n.args and isinstance(n.args[0], ast.Constant)]
        self.assertCountEqual(stages, ['save_inbound', 'complete_inbound', 'render_inbound_detail',
            'render_push', 'push_draft', 'replay_push', 'render_target_detail'])
        self.assertEqual(len(stages), 7)
        source = DIAGNOSTIC.read_text(encoding='utf-8')
        self.assertIn("protocol_reads.append(dict(phase='completion_snapshot'", source)
        self.assertIn('not server.thread.is_alive() and server.listener.fileno() == -1', source)
        self.assertIn('X-WMS-Document-Revision', source)
        self.assertIn('synthetic-invalid-revision', source)


def test_unowned_tcp_diagnostic_refuses_before_app_db_socket_or_child():
    code = r'''
import builtins,runpy,socket,sqlite3,subprocess,sys
def deny(*a,**k):raise AssertionError('unowned diagnostic attempted app/DB/socket/child')
original=builtins.__import__
def guarded(name,*a,**k):
 if name=='app' or name.startswith('app.'):deny()
 return original(name,*a,**k)
builtins.__import__=guarded
socket.socket.connect=socket.socket.connect_ex=socket.socket.bind=socket.getaddrinfo=sqlite3.connect=subprocess.Popen=deny
script=sys.argv[1];sys.argv=[script,'--scenario','inbound-push-tcp']
try:runpy.run_path(script,run_name='__main__')
except SystemExit as exc:
 if '安全阻断' not in str(exc):raise
else:raise AssertionError('Unowned entry did not refuse')
'''
    env = {k: os.environ[k] for k in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP') if k in os.environ}
    for forged in ({}, {'DATABASE_URL': 'sqlite:///:memory:', 'WMS_DATABASE_URI': 'sqlite:///:memory:',
                        'WMS_TEST_RUNTIME_PROOF': '/synthetic-forged-proof.json', 'FLASK_ENV': 'testing'}):
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', code, str(DIAGNOSTIC)],
                                env=dict(env, **forged), capture_output=True, text=True, encoding='utf-8', timeout=25)
        assert result.returncode == 0, result.stdout + result.stderr


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticTCPSourceTests))
    if result.wasSuccessful():
        test_unowned_tcp_diagnostic_refuses_before_app_db_socket_or_child()
    raise SystemExit(not result.wasSuccessful())
