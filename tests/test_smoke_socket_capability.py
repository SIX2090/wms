"""Offline safety checks for ownership of the writable smoke listener.

No application, real database, service or outbound connection is used.
"""
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]

import requests
from requests.adapters import BaseAdapter
with mock.patch.object(sys, 'path', [str(ROOT), *sys.path]):
    from scripts import full_smoke_test, run_smoke_in_ci, smoke_isolation

_REAL_POPEN = subprocess.Popen


def deny(*args, **kwargs):
    raise AssertionError('real connections and databases are prohibited')


class FakeAdapter(BaseAdapter):
    def __init__(self, nonce):
        self.calls = []
        self.nonce = nonce

    def send(self, request, **kwargs):
        self.calls.append(request.url)
        response = requests.Response()
        response.status_code = 200
        response.url = request.url
        response.request = request
        response.headers['X-WMS-Isolated-Smoke'] = self.nonce
        response.raw = io.BytesIO(b'{}')
        return response

    def close(self):
        pass


class SmokeListenerCapabilityTests(unittest.TestCase):
    def setUp(self):
        for target in (mock.patch.object(socket.socket, 'connect', deny),
                       mock.patch.object(socket.socket, 'connect_ex', deny),
                       mock.patch.object(socket, 'getaddrinfo', deny),
                       mock.patch.object(sqlite3, 'connect', deny),
                       mock.patch.object(subprocess, 'Popen', deny)):
            target.start()
            self.addCleanup(target.stop)
        self.nonce = 'a' * 64
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(self.listener.close)
        if os.name == 'nt':
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        host, port = self.listener.getsockname()
        self.assertGreaterEqual(port, 10240)
        self.identity = {'schema': 1, 'base_url': f'http://{host}:{port}',
                         'nonce': self.nonce, 'pid': 12345, 'database': 'synthetic.db'}

    def test_session_refuses_missing_ownership_capability(self):
        with self.assertRaises(ValueError):
            smoke_isolation.IsolatedSession(self.identity, None)
        with self.assertRaises(ValueError):
            smoke_isolation.IsolatedSession(self.identity, SimpleNamespace(validate=lambda _identity: None))

    def test_valid_owned_listener_allows_offline_get(self):
        lease = smoke_isolation.OwnedSocketLease(self.listener, self.identity)
        session = smoke_isolation.IsolatedSession(self.identity, lease)
        adapter = FakeAdapter(self.nonce)
        session.mount('http://', adapter)
        self.assertEqual(session.get(self.identity['base_url'] + '/login').status_code, 200)
        self.assertEqual(len(adapter.calls), 1)

    def test_closed_listener_blocks_first_get_before_adapter(self):
        lease = smoke_isolation.OwnedSocketLease(self.listener, self.identity)
        session = smoke_isolation.IsolatedSession(self.identity, lease)
        adapter = FakeAdapter(self.nonce)
        session.mount('http://', adapter)
        self.listener.close()
        with self.assertRaises(ValueError):
            session.get(self.identity['base_url'] + '/login')
        self.assertEqual(adapter.calls, [])

    def test_changed_identity_blocks_first_get_before_adapter(self):
        lease = smoke_isolation.OwnedSocketLease(self.listener, self.identity)
        session = smoke_isolation.IsolatedSession(self.identity, lease)
        adapter = FakeAdapter(self.nonce)
        session.mount('http://', adapter)
        session.identity['nonce'] = 'b' * 64
        with self.assertRaises(ValueError):
            session.get(self.identity['base_url'] + '/login')
        self.assertEqual(adapter.calls, [])

    def test_foreign_listener_cannot_match_a_forged_receipt(self):
        fake_identity = dict(self.identity, base_url='http://127.0.0.1:49199')
        if fake_identity['base_url'] == self.identity['base_url']:
            fake_identity['base_url'] = 'http://127.0.0.1:49200'
        with self.assertRaises(ValueError):
            smoke_isolation.OwnedSocketLease(self.listener, fake_identity)

    def test_private_pipe_roundtrip_holds_an_owned_listener(self):
        listener = self.listener if os.name == 'nt' else self.listener.dup()
        payload = smoke_isolation.encode_listener_capability(
            listener, os.getpid(), self.nonce, self.identity['pid'])
        if os.name != 'nt':
            listener.detach()
        received, lease = smoke_isolation.receive_listener_capability(io.BytesIO(payload))
        with received:
            lease.validate(self.identity)
            self.assertEqual(received.getsockname(), self.listener.getsockname())
        self.assertGreaterEqual(self.listener.getsockname()[1], 10240)

    def test_listener_transfer_to_owned_child(self):
        child_code = """\
import socket, sqlite3, sys
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])  # explicit requests dependencies; do not load site .pth
def deny(*args, **kwargs): raise AssertionError('network and database prohibited')
socket.socket.connect = deny
socket.socket.connect_ex = deny
socket.getaddrinfo = deny
sqlite3.connect = deny
from scripts.smoke_isolation import receive_listener_capability
listener, lease = receive_listener_capability(sys.stdin.buffer)
with listener:
    assert lease.nonce == 'a' * 64
    assert lease.pid == 12345
    assert listener.getsockname()[0] == '127.0.0.1'
print('owned capability verified')
"""
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'PATH', 'TEMP', 'TMP')
               if key in os.environ}
        # This call starts only the explicit -I child above; its connect and
        # SQLite functions are denied before it imports the smoke helper.
        real_popen = mock.patch.object(subprocess, 'Popen', _REAL_POPEN)
        with real_popen:
            proc = subprocess.Popen(
                [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', child_code,
                 str(ROOT), str(Path(requests.__file__).resolve().parent.parent)],
                cwd=str(ROOT), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, **run_smoke_in_ci._socket_child_options(self.listener))
            try:
                run_smoke_in_ci._send_capability(proc, self.listener, self.nonce, self.identity['pid'])
                self.assertEqual(proc.wait(timeout=10), 0)
                self.assertIn(b'owned capability verified', proc.stdout.read())
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
        self.assertGreaterEqual(self.listener.getsockname()[1], 10240)

    def test_invalid_private_pipe_is_rejected(self):
        for data in (b'', b'{}', b'not-json', b'x' * 32769,
                     json.dumps({'kind': 'wrong-platform'}).encode('ascii')):
            with self.subTest(data=data[:20]), self.assertRaises(ValueError):
                smoke_isolation.receive_listener_capability(io.BytesIO(data))

    def test_ready_child_dying_before_return_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
            root = Path(directory).resolve()
            receipt = dict(self.identity, database=str(root / 'synthetic.db'))
            (root / 'ready.json').write_text(json.dumps(receipt), encoding='utf-8')
            child = mock.Mock(pid=self.identity['pid'])
            child.poll.side_effect = [None, 1]
            with self.assertRaises(RuntimeError):
                run_smoke_in_ci.wait_ready(child, root, self.listener, self.nonce, timeout=1)

    def test_direct_server_mode_requires_owned_capability(self):
        with mock.patch.object(run_smoke_in_ci, 'serve_isolated') as serve:
            with self.assertRaises(SystemExit):
                run_smoke_in_ci.main(['--serve', 'synthetic-directory'])
            serve.assert_not_called()

    def test_server_capability_interrupt_stops_owned_child(self):
        actions = []
        child = SimpleNamespace(pid=12345, stdin=io.BytesIO(), poll=lambda: None,
                                terminate=lambda: actions.append('terminate'),
                                wait=lambda timeout: actions.append(('wait', timeout)))
        with mock.patch.object(run_smoke_in_ci.subprocess, 'Popen', return_value=child), \
             mock.patch.object(run_smoke_in_ci, '_send_capability', side_effect=KeyboardInterrupt):
            with tempfile.TemporaryDirectory(prefix='wms-child-failure-') as directory:
                with self.assertRaises(KeyboardInterrupt):
                    run_smoke_in_ci.start_server(Path(directory), io.StringIO(), self.listener, self.nonce)
        self.assertEqual(actions, ['terminate', ('wait', 5)])

    def test_client_interrupt_stops_owned_client(self):
        actions = []
        def wait(timeout=None):
            if timeout is None:
                raise KeyboardInterrupt
            actions.append(('wait', timeout))
        child = SimpleNamespace(pid=12345, stdin=io.BytesIO(), poll=lambda: None,
                                terminate=lambda: actions.append('terminate'), wait=wait)
        with mock.patch.object(run_smoke_in_ci.subprocess, 'Popen', return_value=child), \
             mock.patch.object(run_smoke_in_ci, '_send_capability'):
            with tempfile.TemporaryDirectory(prefix='wms-child-failure-') as directory:
                root = Path(directory)
                with self.assertRaises(KeyboardInterrupt):
                    run_smoke_in_ci.run_client(root, root / 'ready.json', self.listener,
                                               self.nonce, self.identity['pid'])
        self.assertEqual(actions, ['terminate', ('wait', 5)])

    def test_parent_interrupt_stops_owned_server(self):
        child = SimpleNamespace(pid=12345)
        with mock.patch.object(run_smoke_in_ci, 'start_server', return_value=child), \
             mock.patch('scripts.linux_test_runtime.require_subprocess_boundary'), \
             mock.patch.object(run_smoke_in_ci, 'wait_ready', return_value=Path('synthetic-ready.json')), \
             mock.patch.object(run_smoke_in_ci, 'run_client', side_effect=KeyboardInterrupt), \
             mock.patch.object(run_smoke_in_ci, 'stop_server') as stop:
            with self.assertRaises(KeyboardInterrupt):
                run_smoke_in_ci.main([])
        stop.assert_called_once_with(child)

    def test_unproven_source_copy_stops_before_copy_or_app_import(self):
        with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
            root = Path(directory).resolve()
            identity = dict(self.identity, pid=os.getpid())
            lease = smoke_isolation.OwnedSocketLease(self.listener, identity)
            with mock.patch.dict(os.environ, {'DATABASE_URL': 'sqlite:///' + (root / 'synthetic.db').as_posix(),
                                              'WMS_TEST_RUNTIME_PROOF': ''}), \
                 mock.patch.object(run_smoke_in_ci.shutil, 'copytree') as copy, \
                 mock.patch.object(run_smoke_in_ci.os, 'chdir', side_effect=deny) as chdir:
                with self.assertRaisesRegex(SystemExit, '安全阻断'):
                    run_smoke_in_ci.serve_isolated(root, self.listener, lease)
                copy.assert_not_called()
                chdir.assert_not_called()
                self.assertFalse((root / 'synthetic.db').exists())

    def test_ready_file_alone_cannot_authorize_cli(self):
        with mock.patch.object(full_smoke_test, 'read_identity', return_value=self.identity), \
             mock.patch.object(full_smoke_test, 'IsolatedSession') as session:
            with self.assertRaises((ValueError, SystemExit)):
                full_smoke_test.main(['--isolation-file', 'synthetic-ready.json'])
            session.assert_not_called()


if __name__ == '__main__':
    unittest.main()
