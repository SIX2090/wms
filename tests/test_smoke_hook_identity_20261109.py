"""Exercise smoke response hooks with in-memory HTTP adapters only."""
import io
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
NONCE = 'a' * 64
BASE = 'http://127.0.0.1:49199'


def forbidden(*_args, **_kwargs):
    raise AssertionError('network, database and subprocess are forbidden')


class ResponseHooksIsolation(unittest.TestCase):
    def setUp(self):
        for guard in (mock.patch.object(socket.socket, 'connect', forbidden),
                      mock.patch.object(socket.socket, 'connect_ex', forbidden),
                      mock.patch.object(socket, 'getaddrinfo', forbidden),
                      mock.patch.object(sqlite3, 'connect', forbidden),
                      mock.patch.object(subprocess, 'Popen', forbidden)):
            guard.start()
            self.addCleanup(guard.stop)
        path_guard = mock.patch.object(sys, 'path', list(sys.path))
        path_guard.start()
        self.addCleanup(path_guard.stop)
        purelib = sysconfig.get_paths()['purelib']
        if purelib not in sys.path:
            sys.path.append(purelib)
        import requests
        from requests.adapters import BaseAdapter
        self.requests = requests
        module = runpy.run_path(str(ROOT / 'scripts/smoke_isolation.py'))
        lease = object.__new__(module['OwnedSocketLease'])
        lease.validate = lambda _identity: None
        identity = {'base_url': BASE, 'nonce': NONCE, 'pid': 123}
        self.session = module['IsolatedSession'](identity, lease)
        self.error = module['IsolationError']

        class Adapter(BaseAdapter):
            def __init__(self):
                self.headers = {}
                self.calls = []
                self.status = 200
            def send(self, request, **_kwargs):
                self.calls.append(request.method)
                response = requests.Response()
                response.status_code = self.status
                response.url = request.url
                response.request = request
                response.headers.update(self.headers)
                response.raw = io.BytesIO(b'{}')
                return response
            def close(self):
                pass
        self.adapter = Adapter()
        self.session.mount('http://', self.adapter)

    def test_per_request_hook_cannot_skip_first_identity_check(self):
        calls = []
        with self.assertRaises(self.error):
            self.session.get(BASE + '/login', hooks={'response': [lambda r, **_: calls.append(r)]})
        self.assertEqual(self.adapter.calls, ['GET'])
        self.assertEqual(calls, [], '身份无效时不得交给外部回调')
        with self.assertRaises(self.error):
            self.session.post(BASE + '/write')
        self.assertEqual(self.adapter.calls, ['GET'])

    def test_hook_cannot_replace_a_verified_response_with_unverified_one(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE}
        self.session.get(BASE + '/login')
        def replace(response, **_kwargs):
            other = self.requests.Response()
            other.status_code, other.url, other.request = 200, response.url, response.request
            other.raw = io.BytesIO(b'{}')
            return other
        with self.assertRaises(self.error):
            self.session.get(BASE + '/changed', hooks={'response': [replace]})
        with self.assertRaises(self.error):
            self.session.post(BASE + '/write')
        self.assertEqual(self.adapter.calls, ['GET', 'GET'])

    def test_valid_hook_runs_once_and_valid_response_retains_identity(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE}
        calls = []
        response = self.session.get(BASE + '/login', hooks={'response': [lambda r, **_: calls.append(r)]})
        self.assertEqual(len(calls), 1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.session.post(BASE + '/write').status_code, 200)
        self.assertEqual(self.adapter.calls, ['GET', 'POST'])

    def test_hook_mutating_identity_revokes_permission(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE}
        self.session.get(BASE + '/login')
        def remove_identity(response, **_kwargs):
            del response.headers['X-WMS-Isolated-Smoke']
        with self.assertRaises(self.error):
            self.session.get(BASE + '/changed', hooks={'response': [remove_identity]})
        with self.assertRaises(self.error):
            self.session.post(BASE + '/write')
        self.assertEqual(self.adapter.calls, ['GET', 'GET'])

    def test_redirect_callback_cannot_override_origin_rejection(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE,
                                'Location': 'http://127.0.0.1:8080/synthetic'}
        self.adapter.status = 302
        calls = []
        with self.assertRaises(self.error):
            self.session.get(BASE + '/redirect', hooks={'response': [lambda r, **_: calls.append(r)]})
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.adapter.calls, ['GET'])
        with self.assertRaises(self.error):
            self.session.post(BASE + '/write')

    def test_bad_identity_is_checked_before_redirect_callback(self):
        self.adapter.headers = {'Location': BASE + '/next'}
        self.adapter.status = 302
        calls = []
        with self.assertRaises(self.error):
            self.session.get(BASE + '/redirect', hooks={'response': [lambda r, **_: calls.append(r)]})
        self.assertEqual(calls, [])
        self.assertEqual(self.adapter.calls, ['GET'])

    def test_explicit_proxy_options_are_rejected_before_adapter(self):
        for key in ('http', 'https', 'all', 'no'):
            with self.subTest(key=key):
                self.session.proxies = {}
                self.adapter.calls.clear()
                with self.assertRaises(self.error):
                    self.session.get(BASE + '/login', proxies={key: 'http://proxy.invalid:1234'})
                self.assertEqual(self.adapter.calls, [])

    def test_session_and_direct_send_proxy_are_rejected_before_adapter(self):
        for place in ('session', 'send'):
            with self.subTest(place=place):
                self.session.proxies = {}
                self.adapter.calls.clear()
                request = self.requests.Request('GET', BASE + '/login').prepare()
                kwargs = {}
                if place == 'session':
                    self.session.proxies = {'all': 'http://proxy.invalid:1234'}
                else:
                    kwargs['proxies'] = {'http': 'http://proxy.invalid:1234'}
                with self.assertRaises(self.error):
                    self.session.send(request, **kwargs)
                self.assertEqual(self.adapter.calls, [])

    def test_proxy_rejection_revokes_verified_identity(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE}
        self.session.get(BASE + '/login')
        with self.assertRaises(self.error):
            self.session.get(BASE + '/probe', proxies={'http': 'http://proxy.invalid:1234'})
        with self.assertRaises(self.error):
            self.session.post(BASE + '/write')
        self.assertEqual(self.adapter.calls, ['GET'])

    def test_inherited_environment_proxies_are_never_used(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE}
        with mock.patch.dict('os.environ', {
                'HTTP_PROXY': 'http://proxy.invalid:1234',
                'HTTPS_PROXY': 'http://proxy.invalid:1234',
                'ALL_PROXY': 'http://proxy.invalid:1234',
                'NO_PROXY': '',
            }):
            self.assertEqual(self.session.get(BASE + '/login', proxies={}).status_code, 200)
        self.assertEqual(self.adapter.calls, ['GET'])

    def test_enabling_environment_proxy_is_refused(self):
        self.session.trust_env = True
        with mock.patch.dict('os.environ', {'HTTP_PROXY': 'http://proxy.invalid:1234', 'NO_PROXY': ''}):
            with self.assertRaises(self.error):
                self.session.get(BASE + '/login')
        self.assertEqual(self.adapter.calls, [])

    def test_proxy_added_during_redirect_is_refused(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE, 'Location': BASE + '/next'}
        self.adapter.status = 302
        def change_proxy(response, **_kwargs):
            self.session.proxies = {'http': 'http://proxy.invalid:1234'}
            self.adapter.status = 200
            return response
        with self.assertRaises(self.error):
            self.session.get(BASE + '/login', hooks={'response': [change_proxy]})
        self.assertEqual(self.adapter.calls, ['GET'])

    def test_invalid_prepared_request_hooks_revokes_identity(self):
        self.adapter.headers = {'X-WMS-Isolated-Smoke': NONCE}
        self.session.get(BASE + '/login')
        request = self.requests.Request('GET', BASE + '/synthetic').prepare()
        request.hooks = None
        with self.assertRaises(self.error):
            self.session.send(request)
        with self.assertRaises(self.error):
            self.session.post(BASE + '/write')
        self.assertEqual(self.adapter.calls, ['GET'])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ResponseHooksIsolation)
    if suite.countTestCases() != 13:
        raise RuntimeError('synthetic test list is incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
