"""打印代理 TLS 回归：全部网络、数据库和子进程均禁用。"""
import ast
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import ssl
import subprocess
import sys
import types
import unittest
from unittest import mock
import urllib.error
import urllib.request
import zipfile


_SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'print_agent' / 'wms_print_agent.py'
_SPEC = importlib.util.spec_from_file_location('wms_print_agent_tls_test', _SCRIPT)
agent = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(agent)


def _deny(*_args, **_kwargs):
    raise AssertionError('此测试不允许网络、数据库或子进程')


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"status":"success","job":{"id":7}}'


class PrintAgentTlsSafety(unittest.TestCase):
    def setUp(self):
        for target in (mock.patch.object(socket.socket, 'connect', _deny),
                       mock.patch.object(socket.socket, 'connect_ex', _deny),
                       mock.patch.object(socket, 'getaddrinfo', _deny),
                       mock.patch.object(sqlite3, 'connect', _deny),
                       mock.patch.object(subprocess, 'Popen', _deny)):
            target.start()
            self.addCleanup(target.stop)

    def test_certificate_failures_never_retry_with_credentials(self):
        for reason in ('certificate has expired', 'hostname mismatch'):
            with self.subTest(reason=reason):
                opener = mock.Mock()
                opener.open.side_effect = [
                    urllib.error.URLError(ssl.SSLCertVerificationError(reason)),
                    _Response(),
                ]
                with mock.patch.object(agent.urllib.request, 'build_opener', return_value=opener) as build, \
                     mock.patch.object(agent.ssl, '_create_unverified_context') as unverified, \
                     self.assertLogs('wms_print_agent', level='ERROR') as logs:
                    result = agent.api_call('https://synthetic.invalid', 'synthetic-token', '/claim', {})
                self.assertEqual(result, (0, {}))
                self.assertEqual(build.call_count, 1)
                self.assertEqual(opener.open.call_count, 1)
                unverified.assert_not_called()
                self.assertIn('证书', '\n'.join(logs.output))
                self.assertNotIn('synthetic-token', '\n'.join(logs.output))

    def test_success_http_and_network_errors_preserve_contract(self):
        opener = mock.Mock()
        opener.open.return_value = _Response()
        with mock.patch.object(agent.urllib.request, 'build_opener', return_value=opener):
            self.assertEqual(agent.api_call('https://synthetic.invalid', 'synthetic-token', '/claim', {'x': 1}),
                             (200, {'status': 'success', 'job': {'id': 7}}))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-token')
        self.assertEqual(json.loads(request.data), {'x': 1})

        for exc, expected in (
            (urllib.error.HTTPError('https://synthetic.invalid', 409, 'Conflict', {},
                                    io.BytesIO(b'{"msg":"conflict"}')), (409, {'msg': 'conflict'})),
            (urllib.error.URLError('offline'), (0, {})),
            (TimeoutError('timeout'), (0, {})),
        ):
            with self.subTest(error=type(exc).__name__):
                opener = mock.Mock()
                opener.open.side_effect = exc
                with mock.patch.object(agent.urllib.request, 'build_opener', return_value=opener):
                    self.assertEqual(agent.api_call('https://synthetic.invalid', 'synthetic-token', '/claim'), expected)
                self.assertEqual(opener.open.call_count, 1)

    def test_all_agent_api_consumers_stop_on_certificate_failure(self):
        cfg = {'server_url': 'https://synthetic.invalid', 'token': 'synthetic-token'}
        for operation in ('heartbeat', 'claim', 'complete', 'fail'):
            with self.subTest(operation=operation):
                opener = mock.Mock()
                opener.open.side_effect = [urllib.error.URLError(ssl.SSLCertVerificationError('expired')),
                                           _Response()]
                with mock.patch.object(agent.urllib.request, 'build_opener', return_value=opener), \
                     mock.patch.object(agent.ssl, '_create_unverified_context') as unverified, \
                     mock.patch.object(agent, 'enumerate_printers', return_value=[]):
                    if operation == 'heartbeat':
                        self.assertFalse(agent.send_heartbeat(cfg))
                    elif operation == 'claim':
                        self.assertIsNone(agent.claim_job(cfg))
                    else:
                        agent.report_result(cfg, 7, operation == 'complete', lease_token='synthetic-lease')
                self.assertEqual(opener.open.call_count, 1)
                unverified.assert_not_called()

    def test_successful_consumer_requests_keep_paths_and_payloads(self):
        cfg = {'server_url': 'https://synthetic.invalid', 'token': 'synthetic-token'}
        calls = []

        def record_open(request, timeout):
            calls.append((request.full_url, json.loads(request.data), timeout))
            return _Response()

        opener = mock.Mock()
        opener.open.side_effect = record_open
        with mock.patch.object(agent.urllib.request, 'build_opener', return_value=opener), \
             mock.patch.object(agent, 'enumerate_printers', return_value=None), \
             mock.patch.object(agent, '_printer_enum_failed', False):
            self.assertTrue(agent.send_heartbeat(cfg))
            self.assertEqual(agent.claim_job(cfg), {'id': 7})
            agent.report_result(cfg, 7, True, lease_token='synthetic-lease')
            agent.report_result(cfg, 7, False, error_msg='synthetic error', lease_token='synthetic-lease')
        self.assertEqual([url for url, _, _ in calls], [
            'https://synthetic.invalid/print_queue/api/v1/heartbeat',
            'https://synthetic.invalid/print_queue/api/v1/claim',
            'https://synthetic.invalid/print_queue/api/v1/jobs/7/complete',
            'https://synthetic.invalid/print_queue/api/v1/jobs/7/fail',
        ])
        self.assertIsNone(calls[0][1]['printers'])
        self.assertEqual(calls[1][1], {})
        self.assertEqual(calls[2][1], {'error_msg': None, 'lease_token': 'synthetic-lease'})
        self.assertEqual(calls[3][1], {'error_msg': 'synthetic error', 'lease_token': 'synthetic-lease'})
        self.assertTrue(all(timeout == 15 for _, _, timeout in calls))

    def test_post_redirect_keeps_body_and_auth_on_permitted_origin(self):
        payload = b'{"copies":2,"lease_token":"synthetic"}'
        for source, destination in (
            ('https://synthetic.invalid/a', 'https://synthetic.invalid/b'),
            ('https://synthetic.invalid:443/a', 'https://synthetic.invalid/b'),
            ('http://synthetic.invalid/a', 'https://synthetic.invalid/b'),
            ('http://synthetic.invalid:8080/a', 'https://synthetic.invalid:8080/b'),
            ('https://[2001:db8::1]:443/a', 'https://[2001:db8::1]/b'),
        ):
            for code in (301, 302, 303):
                with self.subTest(source=source, destination=destination, code=code):
                    req = urllib.request.Request(source, data=payload, headers={
                        'Authorization': 'Bearer synthetic-token',
                        'Content-Type': 'application/json',
                    }, method='POST')
                    result = agent._PostRedirectHandler().redirect_request(req, None, code, 'Found', {}, destination)
                    self.assertEqual(result.full_url, destination)
                    self.assertEqual(result.get_method(), 'POST')
                    self.assertEqual(result.data, payload)
                    self.assertEqual(result.get_header('Authorization'), 'Bearer synthetic-token')
                    self.assertEqual(result.get_header('Content-type'), 'application/json')

    def test_untrusted_redirect_is_rejected_before_next_open(self):
        destinations = (
            'https://other.invalid/b', 'https://synthetic.invalid:444/b',
            'http://synthetic.invalid/b', 'https://user@synthetic.invalid/b',
            'ftp://synthetic.invalid/b', 'https://synthetic.invalid:bad/b',
            'https://synthetic.invalid:0/b',
        )
        for destination in destinations:
            with self.subTest(destination=destination):
                req = urllib.request.Request('https://synthetic.invalid/a', data=b'{}',
                                             headers={'Authorization': 'Bearer synthetic-token'}, method='POST')
                req.timeout = 15
                handler = agent._PostRedirectHandler()
                handler.parent = mock.Mock()
                with self.assertRaises(urllib.error.HTTPError) as error:
                    handler.http_error_302(req, io.BytesIO(b'{}'), 302, 'Found', {'location': destination})
                handler.parent.open.assert_not_called()
                self.assertNotIn('synthetic-token', str(error.exception))

    def test_upgrade_then_downgrade_and_unknown_port_are_refused(self):
        handler = agent._PostRedirectHandler()
        original = urllib.request.Request('http://synthetic.invalid/a', data=b'{}',
                                          headers={'Authorization': 'Bearer synthetic-token'}, method='POST')
        upgraded = handler.redirect_request(original, None, 301, 'Moved', {}, 'https://synthetic.invalid/b')
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(upgraded, None, 302, 'Found', {}, 'http://synthetic.invalid/c')
        with self.assertRaises(urllib.error.HTTPError):
            handler.redirect_request(original, None, 302, 'Found', {}, 'https://synthetic.invalid:8443/b')

    def test_post_307_and_308_retain_existing_rejection(self):
        req = urllib.request.Request('https://synthetic.invalid/a', data=b'{}', method='POST')
        for code in (307, 308):
            with self.subTest(code=code), self.assertRaises(urllib.error.HTTPError):
                agent._PostRedirectHandler().redirect_request(req, None, code, 'Redirect', {},
                                                              'https://synthetic.invalid/b')

    def test_valid_relative_redirect_is_followed_with_complete_payload(self):
        req = urllib.request.Request('https://synthetic.invalid/a', data=b'{"copies":2}', headers={
            'Authorization': 'Bearer synthetic-token', 'Content-Type': 'application/json',
            'Content-Length': '999',
        }, method='POST')
        req.timeout = 15
        handler = agent._PostRedirectHandler()
        handler.parent = mock.Mock()
        returned = handler.http_error_302(req, io.BytesIO(b'{}'), 302, 'Found', {'location': '/b'})
        self.assertIs(returned, handler.parent.open.return_value)
        redirected = handler.parent.open.call_args.args[0]
        self.assertEqual(redirected.full_url, 'https://synthetic.invalid/b')
        self.assertEqual(redirected.get_method(), 'POST')
        self.assertEqual(redirected.data, b'{"copies":2}')
        self.assertEqual(redirected.get_header('Authorization'), 'Bearer synthetic-token')
        self.assertEqual(redirected.get_header('Content-type'), 'application/json')
        self.assertIsNone(redirected.get_header('Content-length'))

    def test_redirect_loop_keeps_standard_limit(self):
        req = urllib.request.Request('https://synthetic.invalid/a', data=b'{}', method='POST')
        req.timeout = 15
        req.redirect_dict = {'https://synthetic.invalid/b': agent._PostRedirectHandler.max_repeats}
        handler = agent._PostRedirectHandler()
        handler.parent = mock.Mock()
        with self.assertRaises(urllib.error.HTTPError):
            handler.http_error_302(req, io.BytesIO(b'{}'), 302, 'Found', {'location': '/b'})
        handler.parent.open.assert_not_called()

    def test_bad_redirect_url_stops_api_call_without_exposing_token(self):
        opener = mock.Mock()
        opener.open.side_effect = ValueError('synthetic-token')
        with mock.patch.object(agent.urllib.request, 'build_opener', return_value=opener), \
                self.assertLogs('wms_print_agent', level='ERROR') as logs:
            result = agent.api_call('https://synthetic.invalid', 'synthetic-token', '/claim')
        self.assertEqual(result, (0, {}))
        self.assertEqual(opener.open.call_count, 1)
        self.assertNotIn('synthetic-token', '\n'.join(logs.output))

    def test_download_package_contains_current_agent_script(self):
        root = _SCRIPT.parents[2]
        route = root / 'app' / 'routes' / 'print_routing.py'
        tree = ast.parse(route.read_text(encoding='utf-8'))
        function = next(node for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef)
                        and node.name == 'print_routing_download_agent')
        function.decorator_list = []
        fake_app = types.ModuleType('app')
        fake_app.PrintWorkstation = types.SimpleNamespace(query=mock.Mock())
        fake_app.PrintWorkstation.query.count.return_value = 0
        fake_app.is_hashed_access_token = lambda _token: False
        request = types.SimpleNamespace(args={}, host_url='https://synthetic.invalid/')
        namespace = {'__file__': str(route), 'os': os, 'io': io, 'json': json,
                     'zipfile': zipfile, 'request': request,
                     'send_file': lambda buf, **_kwargs: buf.getvalue()}
        code = compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                       '<synthetic download function>', 'exec')
        with mock.patch.dict(sys.modules, {'app': fake_app}):
            exec(code, namespace)
            package = namespace['print_routing_download_agent']()
        with zipfile.ZipFile(io.BytesIO(package)) as archive:
            self.assertEqual(archive.read('wms_print_agent.py'), _SCRIPT.read_bytes())
            config = json.loads(archive.read('agent_config.json'))
        self.assertEqual(config['server_url'], 'https://synthetic.invalid')
        self.assertTrue(config['token'].startswith('在此粘贴'))


if __name__ == '__main__':
    unittest.main()
