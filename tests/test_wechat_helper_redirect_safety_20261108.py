"""Synthetic-only redirect and target checks; never sends WeChat or network traffic."""
import ast
import contextlib
import hashlib
import io
import ipaddress
import json
import logging
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import types
import unittest
from unittest import mock
from urllib.parse import urljoin, urlsplit, urlparse

import requests
import pytest
from requests.adapters import BaseAdapter


ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('real network, database or subprocess forbidden')


def load_nodes(path, names, namespace):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    nodes = [node for node in tree.body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    code = compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                   '<synthetic functions>', 'exec')
    exec(code, namespace)
    return namespace


class MemoryAdapter(BaseAdapter):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.requests = []

    def send(self, request, **_kwargs):
        self.calls.append((request.url, request.headers.get('X-Wechat-Helper-Token')))
        self.requests.append(request)
        status, headers, content = self.responses.pop(0)
        response = requests.Response()
        response.status_code = status
        response.headers.update(headers)
        response.url = request.url
        response.request = request
        response.raw = io.BytesIO(content)
        response._content = content
        return response

    def close(self):
        pass


class WechatRedirectSafety(unittest.TestCase):
    def setUp(self):
        for target in (mock.patch.object(socket.socket, 'connect', deny),
                       mock.patch.object(socket.socket, 'connect_ex', deny),
                       mock.patch.object(socket, 'create_connection', deny),
                       mock.patch.object(socket, 'getaddrinfo', deny),
                       mock.patch.object(sqlite3, 'connect', deny),
                       mock.patch.object(subprocess, 'Popen', deny)):
            target.start()
            self.addCleanup(target.stop)
        self.helper = load_nodes(ROOT / 'app/wechat_helper.py',
                                 {'helper_headers', 'absolute_wms_url', 'poll_once', 'poll_loop',
                                  '_wms_origin', '_WmsSession', '_WmsReportUncertain', '_require_wms_response',
                                  '_require_wms_report_response'},
                                 {'requests': requests, 'urljoin': urljoin, 'urlsplit': urlsplit,
                                  'ipaddress': ipaddress,
                                  'WMS_BASE_URL': 'https://wms.invalid',
                                  'WMS_HELPER_TOKEN': 'synthetic-token',
                                  '_LOOPBACK_NO_PROXY': {'http': None, 'https': None},
                                  'logger': logging.getLogger('synthetic-wechat'),
                                  'send_image_task': mock.Mock(return_value=('ready', 'ok', 'test'))})

    def session(self, responses, *, guarded=True):
        cls = self.helper.get('_WmsSession', requests.Session) if guarded else requests.Session
        session = cls()
        session.trust_env = False
        adapter = MemoryAdapter(responses)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        self.addCleanup(session.close)
        return session, adapter

    def poll(self, session):
        self.helper['_WmsSession'] = lambda: session
        with mock.patch.object(requests, 'get', side_effect=session.get), \
             mock.patch.object(requests, 'post', side_effect=session.post):
            return self.helper['poll_once']()

    def direct_sender(self, session):
        request_lib = types.SimpleNamespace(post=session.post, exceptions=requests.exceptions)
        app = types.SimpleNamespace(config={'WECHAT_HELPER_TOKEN': 'synthetic-token'}, logger=mock.Mock())
        ns = load_nodes(ROOT / 'app/app.py', {'_wechat_share_helper_url_allowed', '_wechat_share_send_image'},
                        {'requests': request_lib, 'app': app, 'os': os, 'urlparse': urlparse,
                         'open': lambda *_args, **_kwargs: io.BytesIO(b'synthetic-png'),
                         '_LOOPBACK_NO_PROXY': {'http': None, 'https': None}})
        cfg = types.SimpleNamespace(helper_url='http://127.0.0.1:18765/send', sender_name='',
                                    sender_wechat_id='', receiver_name='synthetic', receiver_wechat_id='',
                                    receiver_search_key='', receiver_type='person', auto_send=False)
        return ns['_wechat_share_send_image'], cfg

    def wecom_sender(self, session):
        request_lib = types.SimpleNamespace(post=session.post, exceptions=requests.exceptions)
        app = types.SimpleNamespace(logger=mock.Mock())
        ns = load_nodes(ROOT / 'app/app.py',
                        {'_wechat_share_wecom_webhook_allowed', '_wechat_share_send_wecom'},
                        {'requests': request_lib, 'app': app, 'urlparse': urlparse,
                         '_LOOPBACK_NO_PROXY': {'http': None, 'https': None},
                         '_WECOM_WEBHOOK_HOST': 'qyapi.weixin.qq.com',
                         '_WECOM_WEBHOOK_PATH': '/cgi-bin/webhook/send',
                         '_wechat_share_wecom_image_bytes': lambda _path: b'synthetic-png'})
        return ns['_wechat_share_send_wecom']

    def test_task_urls_must_be_same_origin_and_without_userinfo(self):
        resolve = self.helper['absolute_wms_url']
        for url in ('https://other.invalid/image', 'http://wms.invalid/image',
                    'https://wms.invalid:444/image', 'https://fake@wms.invalid/image',
                    'https://wms.invalid@other.invalid/image', '//other.invalid/image'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                resolve(url)
        self.assertEqual(resolve('/api/a'), 'https://wms.invalid/api/a')
        self.assertEqual(resolve('https://wms.invalid:443/api/a'), 'https://wms.invalid:443/api/a')
        self.helper['WMS_BASE_URL'] = 'https://[::1]'
        self.assertEqual(resolve('https://[0:0:0:0:0:0:0:1]:443/api/a'),
                         'https://[0:0:0:0:0:0:0:1]:443/api/a')

    def test_poll_cross_origin_redirect_does_not_leak_helper_token(self):
        session, adapter = self.session([
            (302, {'Location': 'https://other.invalid/tasks'}, b'{}'),
            (200, {}, b'{"status":"success","tasks":[]}'),
        ])
        with self.assertRaises(ValueError):
            self.poll(session)
        self.assertEqual(adapter.calls, [('https://wms.invalid/api/wechat_helper/tasks?limit=3', 'synthetic-token')])

    def test_send(self):
        session, adapter = self.session([
            (302, {'Location': '/second'}, b'{}'),
            (302, {'Location': 'https://other.invalid/third'}, b'{}'),
            (200, {}, b'{}'),
        ])
        with self.assertRaises(ValueError):
            session.get('https://wms.invalid/first', headers={'X-Wechat-Helper-Token': 'synthetic-token'})
        self.assertEqual(adapter.calls, [('https://wms.invalid/first', 'synthetic-token'),
                                         ('https://wms.invalid/second', 'synthetic-token')])

    def test_poll_once(self):
        tasks = json.dumps({'status': 'success', 'tasks': [
            {'id': 42, 'claim_token':'a'*64, 'image_url': '/image', 'report_url': '/report'}]}).encode()
        session, adapter = self.session([(200, {}, tasks), (200, {}, b'synthetic-png'),
                                         (200, {}, b'{"status":"success"}')])
        self.assertEqual(self.poll(session), 1)
        self.helper['send_image_task'].assert_called_once()
        self.assertEqual([url for url, _ in adapter.calls], [
            'https://wms.invalid/api/wechat_helper/tasks?limit=3',
            'https://wms.invalid/api/wechat_helper/task/42/image', 'https://wms.invalid/api/wechat_helper/task/42/report'])
        self.assertTrue(all(token == 'synthetic-token' for _, token in adapter.calls))
        self.assertEqual(json.loads(adapter.requests[-1].body),
                         {'status': 'ready', 'code': 'ok', 'msg': 'test'})

    def test_unsafe_image_and_unfinished_redirect_never_send_wechat(self):
        for image_url, image_response in (
            ('https://other.invalid/image', None),
            ('/image', (302, {}, b'synthetic-png')),
            ('/image', (302, {'Location': 'https://other.invalid/image'}, b'')),
        ):
            with self.subTest(image_url=image_url, response=image_response):
                self.helper['send_image_task'].reset_mock()
                tasks = json.dumps({'status': 'success', 'tasks': [
                    {'id': 42, 'claim_token':'a'*64, 'image_url': image_url, 'report_url': '/report'}]}).encode()
                responses = [(200, {}, tasks)]
                responses.append(image_response if image_response is not None else (200,{},b'synthetic-png'))
                responses.append((200, {}, b'{"status":"success"}'))
                session, adapter = self.session(responses)
                self.assertEqual(self.poll(session), int(image_response is None))
                if image_response is None:
                    # The new protocol ignores task-supplied URLs and uses the authenticated canonical endpoint.
                    self.helper['send_image_task'].assert_called_once()
                else:
                    self.helper['send_image_task'].assert_not_called()
                self.assertTrue(all(url.startswith('https://wms.invalid/') for url, _ in adapter.calls))
                self.assertEqual(adapter.calls[1][0], 'https://wms.invalid/api/wechat_helper/task/42/image')
                self.assertEqual(json.loads(adapter.requests[-1].body)['status'], 'ready' if image_response is None else 'failed')

    def test_report_requires_success_json_after_wechat_action(self):
        tasks = json.dumps({'status': 'success', 'tasks': [
            {'id': 42, 'claim_token':'a'*64, 'image_url': '/image', 'report_url': '/report'}]}).encode()
        for body in (b'{"status":"error","msg":"synthetic-secret"}', b'{}', b'',
                     b'not-json', b'[]', b'null', b'{"status":null}'):
            with self.subTest(body=body):
                session, adapter = self.session([(200, {}, tasks), (200, {}, b'synthetic-png'),
                                                 (200, {}, body)])
                with self.assertRaises(self.helper['_WmsReportUncertain']) as raised:
                    self.poll(session)
                self.assertNotIn('synthetic-secret', str(raised.exception))
                self.assertEqual(len(adapter.calls), 3)
                self.assertEqual(json.loads(adapter.requests[-1].body)['status'], 'ready')

    def test_sent_action_with_valid_success_receipt(self):
        tasks = json.dumps({'status': 'success', 'tasks': [
            {'id': 42, 'claim_token':'a'*64, 'image_url': '/image', 'report_url': '/report'}]}).encode()
        self.helper['send_image_task'].return_value = ('sent', 'ok', 'test')
        session, adapter = self.session([(200, {}, tasks), (200, {}, b'synthetic-png'),
                                         (200, {}, b'{"status":"success"}')])
        self.assertEqual(self.poll(session), 1)
        self.assertEqual(json.loads(adapter.requests[-1].body),
                         {'status': 'sent', 'code': 'ok', 'msg': 'test'})

    def test_failed_action_report_requires_success_json(self):
        tasks = json.dumps({'status': 'success', 'tasks': [
            {'id': 42, 'claim_token':'a'*64, 'image_url': '/image', 'report_url': '/report'}]}).encode()
        for status, body in ((200, b'{"status":"error"}'), (200, b''),
                             (200, b'not-json'), (200, b'[]'), (503, b'{}'), (302, b'{}')):
            with self.subTest(status=status, body=body):
                session, adapter = self.session([(200, {}, tasks), (404, {}, b''),
                                                 (status, {}, body)])
                with self.assertRaises(self.helper['_WmsReportUncertain']):
                    self.poll(session)
                self.assertEqual(len(adapter.calls), 3)
                self.assertEqual(json.loads(adapter.requests[-1].body)['status'], 'failed')
                self.helper['send_image_task'].assert_not_called()

    def test_failed_action_with_valid_success_receipt_continues(self):
        tasks = json.dumps({'status': 'success', 'tasks': [
            {'id': 42, 'claim_token':'a'*64, 'image_url': '/image', 'report_url': '/report'}]}).encode()
        session, adapter = self.session([(200, {}, tasks), (404, {}, b''),
                                         (200, {}, b'{"status":"success"}')])
        self.assertEqual(self.poll(session), 0)
        self.assertEqual(json.loads(adapter.requests[-1].body)['status'], 'failed')
        self.helper['send_image_task'].assert_not_called()

    def test_report_failure_never_sends_a_false_failed_status(self):
        for status, headers in ((302, {}), (302, {'Location': 'https://other.invalid/report'}),
                                (307, {'Location': '/other-report'})):
            with self.subTest(status=status, headers=headers):
                tasks = json.dumps({'status': 'success', 'tasks': [
                    {'id': 42, 'claim_token':'a'*64, 'image_url': '/image', 'report_url': '/report'}]}).encode()
                session, adapter = self.session([(200, {}, tasks), (200, {}, b'synthetic-png'),
                                                 (status, headers, b'{}')])
                with self.assertRaises(self.helper.get('_WmsReportUncertain', RuntimeError)):
                    self.poll(session)
                self.assertEqual(len(adapter.calls), 3)
                self.assertEqual(json.loads(adapter.requests[-1].body)['status'], 'ready')

    def test_uncertain_report_stops_polling_without_sleep_or_replay(self):
        self.helper['poll_once'] = mock.Mock(side_effect=self.helper.get('_WmsReportUncertain', RuntimeError)('synthetic'))
        clock = types.SimpleNamespace(sleep=mock.Mock())
        self.helper['time'] = clock
        self.helper['POLL_INTERVAL'] = 30
        self.helper['POLL_ENABLED'] = True
        self.helper['poll_loop']()
        self.helper['poll_once'].assert_called_once()
        clock.sleep.assert_not_called()
        self.assertFalse(self.helper['POLL_ENABLED'])

    def test_untrusted_report_url_is_ignored_for_authenticated_canonical_endpoint(self):
        tasks = json.dumps({'status': 'success', 'tasks': [
            {'id': 42, 'claim_token':'a'*64, 'image_url': '/image', 'report_url': 'https://other.invalid/report'}]}).encode()
        session, adapter = self.session([(200, {}, tasks),(200, {}, b'synthetic-png'),
                                         (200, {}, b'{"status":"success"}')])
        self.assertEqual(self.poll(session),1)
        self.assertEqual(len(adapter.calls),3)
        self.helper['send_image_task'].assert_called_once()
        self.assertEqual(adapter.calls[-1][0],'https://wms.invalid/api/wechat_helper/task/42/report')
        self.assertTrue(all(url.startswith('https://wms.invalid/') for url,_ in adapter.calls))
        self.assertEqual(adapter.requests[-1].headers['X-Wechat-Task-Claim'],'a'*64)

    def test_missing_token_and_userinfo_refused_before_adapter(self):
        session, adapter = self.session([])
        self.helper['WMS_HELPER_TOKEN'] = None
        with self.assertRaises(RuntimeError):
            self.poll(session)
        with self.assertRaises(ValueError):
            session.get('https://fake-user@wms.invalid/private', headers={'X-Wechat-Helper-Token': 'synthetic-token'})
        self.assertEqual(adapter.calls, [])

    def test_direct_send_rejects_redirect_without_second_request(self):
        session, adapter = self.session([
            (302, {'Location': 'https://other.invalid/send'}, b'{}'),
            (200, {}, b'{"status":"sent"}'),
        ], guarded=False)
        send, cfg = self.direct_sender(session)
        result = send(cfg, 'synthetic.png')
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(result[0], 'failed')
        self.assertIn('重定向', result[2])

    def test_direct_send_keeps_normal_and_auth_error_behavior(self):
        for status, content, expected in (
            (200, b'{"status":"sent","code":"ok","msg":"synthetic"}', ('sent', 'ok')),
            (200, b'{"status":"ready","code":"ok","msg":"synthetic"}', ('uncertain', 'ok')),
            (403, b'{}', ('failed', 'auth_failed')),
            (302, b'{"status":"sent"}', ('failed', 'helper_redirect_refused')),
        ):
            with self.subTest(status=status, content=content):
                session, adapter = self.session([(status, {}, content)], guarded=False)
                send, cfg = self.direct_sender(session)
                result = send(cfg, 'synthetic.png')
                self.assertEqual(result[:2], expected)
                self.assertEqual(len(adapter.calls), 1)
                self.assertEqual(adapter.calls[0][1], 'synthetic-token')

    def test_direct_send_rejects_userinfo_and_invalid_port_before_request(self):
        session, adapter = self.session([], guarded=False)
        send, cfg = self.direct_sender(session)
        for value in ('http://fake-user:fake-password@127.0.0.1:18765/send',
                      'http://127.0.0.1:bad/send', 'http://127.0.0.1:0/send'):
            with self.subTest(value=value):
                cfg.helper_url = value
                self.assertEqual(send(cfg, 'synthetic.png')[1], 'invalid_helper_url')
        self.assertEqual(adapter.calls, [])

    def test_wecom_redirect_does_not_forward_image_or_webhook_key(self):
        for status in (307, 308):
            with self.subTest(status=status):
                session, adapter = self.session([
                    (status, {'Location': 'https://other.invalid/send?key=synthetic-key'}, b'{}'),
                    (200, {}, b'{"errcode":0}'),
                ], guarded=False)
                send = self.wecom_sender(session)
                result = send(
                    'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=synthetic-key', 'synthetic.png')
                self.assertEqual(len(adapter.calls), 1)
                self.assertEqual(result[0], 'failed')
                self.assertIn('重定向', result[2])

    def test_wecom_normal_and_no_location_redirect(self):
        for status, content, expected in (
            (200, b'{"errcode":0}', ('sent', 'ok')),
            (200, b'{"errcode":93000,"errmsg":"invalid"}', ('failed', 'wecom_93000')),
            (302, b'{"errcode":0}', ('failed', 'wecom_redirect_refused')),
        ):
            with self.subTest(status=status, content=content):
                session, adapter = self.session([(status, {}, content)], guarded=False)
                result = self.wecom_sender(session)(
                    'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=synthetic-key', 'synthetic.png')
                self.assertEqual(result[:2], expected)
                self.assertEqual(len(adapter.calls), 1)

    def test_wecom_rejects_userinfo_and_nonstandard_port(self):
        session, adapter = self.session([], guarded=False)
        send = self.wecom_sender(session)
        for value in ('https://fake@qyapi.weixin.qq.com/cgi-bin/webhook/send?key=synthetic-key',
                      'https://qyapi.weixin.qq.com:444/cgi-bin/webhook/send?key=synthetic-key',
                      'https://qyapi.weixin.qq.com:bad/cgi-bin/webhook/send?key=synthetic-key'):
            with self.subTest(value=value):
                self.assertEqual(send(value, 'synthetic.png')[1], 'invalid_wecom_webhook')
        self.assertEqual(adapter.calls, [])

    def test_wecom_connection_error_does_not_disclose_key(self):
        error = requests.exceptions.ConnectionError('synthetic-key in URL')
        request_lib = types.SimpleNamespace(post=mock.Mock(side_effect=error), exceptions=requests.exceptions)
        app = types.SimpleNamespace(logger=mock.Mock())
        ns = load_nodes(ROOT / 'app/app.py',
                        {'_wechat_share_wecom_webhook_allowed', '_wechat_share_send_wecom'},
                        {'requests': request_lib, 'app': app, 'urlparse': urlparse,
                         '_LOOPBACK_NO_PROXY': {'http': None, 'https': None},
                         '_WECOM_WEBHOOK_HOST': 'qyapi.weixin.qq.com',
                         '_WECOM_WEBHOOK_PATH': '/cgi-bin/webhook/send',
                         '_wechat_share_wecom_image_bytes': lambda _path: b'synthetic-png'})
        result = ns['_wechat_share_send_wecom'](
            'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=synthetic-key', 'synthetic.png')
        self.assertEqual(result[:2], ('failed', 'wecom_offline'))
        self.assertNotIn('synthetic-key', result[2])
        self.assertNotIn('synthetic-key', str(app.logger.warning.call_args))

    def test_existing_adjacent_contracts_with_synthetic_app(self):
        app = types.SimpleNamespace(config={'WECHAT_HELPER_TOKEN': 'synthetic-token'},
                                    logger=mock.Mock(), app_context=lambda: contextlib.nullcontext())
        scope = load_nodes(ROOT / 'app/app.py',
                           {'_wechat_share_helper_url_allowed', '_wechat_share_send_image',
                            '_wechat_share_wecom_webhook_allowed', '_wechat_share_send_wecom'},
                           {'requests': requests, 'app': app, 'os': os, 'urlparse': urlparse,
                            '_LOOPBACK_NO_PROXY': {'http': None, 'https': None},
                            '_WECOM_WEBHOOK_HOST': 'qyapi.weixin.qq.com',
                            '_WECOM_WEBHOOK_PATH': '/cgi-bin/webhook/send',
                            '_wechat_share_wecom_image_bytes': lambda path: Path(path).read_bytes()})
        fake_app = types.SimpleNamespace(app=app, **{
            key: value for key, value in scope.items() if key.startswith('_wechat_share_')})
        cases = (
            ('tests/verify_bug_2026_08_11_008_wechat_push_token.py',
             {'_make_config', '_make_image', '_FakeResponse', 'TestDirectPushToken'},
             [('TestDirectPushToken', name) for name in (
                 'test_t1_push_carries_helper_token', 'test_t2_non_loopback_url_rejected',
                 'test_t3_missing_token_rejected')]),
            ('tests/verify_bug_2026_08_11_010_wms_result_mapping.py',
             {'_make_config', '_make_image', '_FakeResponse', '_send', 'TestStructuredCodeMapping'},
             [('TestStructuredCodeMapping', name) for name in (
                 'test_t1_helper_error_code_passthrough', 'test_t2_helper_ready_maps_uncertain',
                 'test_t3_connection_error_never_blindly_retried', 'test_t4_timeout_never_retried',
                 'test_t5_http_403_auth_failed', 'test_t6_persistent_connection_error_offline',
                 'test_t7_no_helper_url_pending_no_request')]),
            ('tests/verify_bug_2026_09_14_034_loopback_no_proxy.py',
             {'_make_config', '_make_image', '_SentResponse', 'TestSendImageNoProxy'},
             [('TestSendImageNoProxy', 'test_t1_send_image_passes_no_proxy')]),
            ('tests/verify_wecom_bot_001_channel.py',
             {'_make_png', '_Resp', 'TestSendWecom', 'TestCaptionOrdering'},
             [('TestSendWecom', name) for name in (
                 'test_t2_image_payload_and_success', 'test_t2b_errcode_maps_to_failed',
                 'test_t2c_invalid_webhook_rejected_before_request')] +
             [('TestCaptionOrdering', 'test_t5_caption_markdown_sent_before_image')]),
        )
        with mock.patch.dict(os.environ, {'WMS_WECHAT_HELPER_URL': ''}):
            for filename, names, methods in cases:
                ns = load_nodes(ROOT / filename, names,
                                {'app_module': fake_app, 'types': types, 'os': os, 'Path': Path,
                                 'requests': requests, 'hashlib': hashlib,
                                 'WEBHOOK': 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=synthetic',
                                 'NO_PROXY': {'http': None, 'https': None}})
                for cls, method in methods:
                    with self.subTest(file=filename, test=method), \
                            tempfile.TemporaryDirectory(prefix='wms-wechat-adjacent-') as directory:
                        app.config['WECHAT_HELPER_TOKEN'] = 'synthetic-token'
                        monkeypatch = pytest.MonkeyPatch()
                        try:
                            getattr(ns[cls](), method)(Path(directory), monkeypatch)
                        finally:
                            monkeypatch.undo()


if __name__ == '__main__':
    unittest.main()
