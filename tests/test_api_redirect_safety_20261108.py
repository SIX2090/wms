"""Git API redirect security, exercising only an in-memory urllib transport."""
import io
import os
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
SECRET = 'synthetic-token-never-send'
SCRIPTS = ('api_push.py', 'fetch_via_api.py', 'push_via_api.py',
           'verify_remote_sync.py', 'check_ci_green.py', 'ci_change_scope.py')


def forbidden(*args, **kwargs):
    raise AssertionError('network, database and subprocess are forbidden')


class Response(io.BytesIO):
    status = 200

    def __init__(self):
        super().__init__(b'{}')


class OfflineTransport:
    def __init__(self, destination):
        self.destination = destination
        self.forwarded = []
        self.initial = []

    def perform(self, handler, request, timeout):
        self.initial.append(request)
        redirected = handler.redirect_request(request, io.BytesIO(), 302, 'Found', {}, self.destination)
        if redirected is not None:
            self.forwarded.append(redirected)
        return Response()

    def old_urlopen(self, request, timeout):
        return self.perform(urllib.request.HTTPRedirectHandler(), request, timeout)

    def build_opener(self, *handlers):
        handler = next(h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
        return type('OfflineOpener', (), {'open': lambda _, req, timeout: self.perform(handler, req, timeout)})()


class ApiRedirectSafety(unittest.TestCase):
    def setUp(self):
        for patcher in (mock.patch.object(socket.socket, 'connect', forbidden),
                        mock.patch.object(socket.socket, 'connect_ex', forbidden),
                        mock.patch.object(socket, 'getaddrinfo', forbidden),
                        mock.patch.object(sqlite3, 'connect', forbidden),
                        mock.patch.object(subprocess, 'Popen', forbidden)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def invoke(self, name, destination):
        transport = OfflineTransport(destination)
        with mock.patch.dict(os.environ, {'GH_TOKEN': SECRET}, clear=True), \
             mock.patch('urllib.request.urlopen', side_effect=transport.old_urlopen), \
             mock.patch('urllib.request.build_opener', side_effect=transport.build_opener), \
             mock.patch('shutil.which', return_value=None), \
             mock.patch('time.sleep', return_value=None):
            module = runpy.run_path(str(ROOT / 'scripts' / name), run_name='offline_api_test')
            names = {'api_push.py': 'req', 'fetch_via_api.py': 'api',
                     'push_via_api.py': '_req', 'verify_remote_sync.py': 'req',
                     'check_ci_green.py': 'gh_get', 'ci_change_scope.py': 'read_api'}
            fn = module[names[name]]
            fn.__globals__['TOKEN'] = SECRET
            args = {'api_push.py': ('GET', '/fixture'),
                    'fetch_via_api.py': ('/fixture', SECRET),
                    'push_via_api.py': ('GET', '/fixture'),
                    'verify_remote_sync.py': ('/fixture', SECRET),
                    'check_ci_green.py': ('/fixture', SECRET),
                    'ci_change_scope.py': ('https://api.github.com/fixture', SECRET)}[name]
            try:
                result = fn(*args)
            except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError, SystemExit):
                result = None
        return transport, result

    def test_cross_origin_and_https_downgrade_never_forward_credentials(self):
        for name in SCRIPTS:
            for destination in ('https://synthetic.invalid/collect',
                                'http://api.github.com/collect',
                                'https://api.github.com:444/collect'):
                with self.subTest(script=name, destination=destination):
                    transport, _ = self.invoke(name, destination)
                    self.assertTrue(transport.initial)
                    self.assertEqual(transport.initial[0].get_header('Authorization').split()[-1], SECRET)
                    self.assertEqual(transport.forwarded, [], 'unsafe redirect reached transport')

    def test_same_origin_redirect_preserves_authorization_and_success(self):
        for name in SCRIPTS:
            with self.subTest(script=name):
                transport, result = self.invoke(name, 'https://api.github.com:443/moved')
                self.assertEqual(len(transport.forwarded), 1)
                self.assertEqual(transport.forwarded[0].get_header('Authorization').split()[-1], SECRET)
                self.assertIsNotNone(result)

    def test_curl_ignores_user_configuration_and_does_not_enable_redirects(self):
        commands = []
        def fake_run(command, **kwargs):
            commands.append(command)
            return type('FakeProcess', (), {'stdout': b'{}\n200', 'returncode': 0})()
        with mock.patch.dict(os.environ, {'GH_TOKEN': SECRET}, clear=True), \
             mock.patch('subprocess.run', side_effect=fake_run):
            push = runpy.run_path(str(ROOT / 'scripts' / 'api_push.py'), run_name='offline_api_test')
            sync = runpy.run_path(str(ROOT / 'scripts' / 'verify_remote_sync.py'), run_name='offline_api_test')
            push['_req_curl']('GET', '/fixture', None)
            sync['_curl_get']('/fixture', SECRET)
            sync['_curl_get_chunked']('/fixture', SECRET, '192.0.2.1')
        self.assertEqual(len(commands), 3)
        for command in commands:
            self.assertEqual(command[:2], ['curl', '-q'])
            self.assertNotIn('--location', command)
            self.assertNotIn('--location-trusted', command)

    def test_handler_covers_redirect_codes_and_rejects_malformed_origins(self):
        helper = runpy.run_path(str(ROOT / 'scripts' / 'wms_safe_http.py'))
        handler = helper['SameOriginRedirectHandler']()
        for code in (301, 302, 303, 307, 308):
            request = urllib.request.Request('https://api.github.com/start',
                                             headers={'Authorization': 'Bearer ' + SECRET})
            with self.subTest(code=code):
                safe = handler.redirect_request(request, io.BytesIO(), code, 'Found', {},
                                                'https://api.github.com:443/next')
                self.assertEqual(safe.get_header('Authorization'), 'Bearer ' + SECRET)
                for target in ('https://synthetic.invalid/next',
                               'https://api.github.com@synthetic.invalid/next',
                               'https://api.github.com:bad/next',
                               'https://api.github.com:0/next',
                               'http://api.github.com/next'):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        handler.redirect_request(request, io.BytesIO(), code, 'Found', {}, target)
                    self.assertNotIn(SECRET, str(error.exception))

    def test_importing_scripts_does_not_change_sys_path(self):
        before = list(sys.path)
        with mock.patch.dict(os.environ, {'GH_TOKEN': SECRET}, clear=True):
            for name in SCRIPTS:
                runpy.run_path(str(ROOT / 'scripts' / name), run_name='offline_api_test')
                self.assertEqual(sys.path, before, name)

    def test_post_redirect_keeps_standard_urllib_protocol(self):
        handler = runpy.run_path(str(ROOT / 'scripts' / 'wms_safe_http.py'))['SameOriginRedirectHandler']()
        for code in (301, 302, 303):
            request = urllib.request.Request('https://api.github.com/start', data=b'{"synthetic":1}',
                                             headers={'Authorization': 'Bearer ' + SECRET}, method='POST')
            with self.subTest(code=code):
                redirected = handler.redirect_request(request, io.BytesIO(), code, 'Found', {},
                                                      'https://api.github.com/next')
                self.assertEqual(redirected.get_method(), 'GET')
                self.assertEqual(redirected.get_header('Authorization'), 'Bearer ' + SECRET)
                with self.assertRaises(urllib.error.HTTPError):
                    handler.redirect_request(request, io.BytesIO(), code, 'Found', {},
                                             'https://synthetic.invalid/next')
        for code in (307, 308):
            request = urllib.request.Request('https://api.github.com/start', data=b'{}', method='POST')
            with self.subTest(code=code), self.assertRaises(urllib.error.HTTPError):
                handler.redirect_request(request, io.BytesIO(), code, 'Found', {},
                                         'https://api.github.com/next')


if __name__ == '__main__':
    unittest.main()
