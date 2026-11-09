"""Synthetic TLS server owned by this process; no WMS, DB, printer or external network."""
import datetime
import importlib.util
import ipaddress
import json
from pathlib import Path
import secrets
import socket
import sqlite3
import ssl
import subprocess
import sys
import sysconfig
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock


def deny(*_args, **_kwargs):
    raise AssertionError('outside synthetic listener or prohibited side effect')


def main():
    # -I -S avoids site startup and .pth execution; this path is used only for
    # the certificate generator, never to import the WMS application.
    sys.path.append(sysconfig.get_paths()['purelib'])
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('synthetic_print_agent', root / 'tools/print_agent/wms_print_agent.py')
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo
    default_context = ssl.create_default_context

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            if self.headers.get('Authorization') != 'Bearer ' + self.server.nonce:
                self.send_error(403)
                return
            self.server.events.append((self.path, json.loads(body)))
            response = b'{"status":"success","job":{"id":7}}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *_args):
            pass

    class Server(ThreadingHTTPServer):
        daemon_threads = True
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

        def get_request(self):
            conn, address = self.socket.accept()
            self.accepts += 1
            try:
                return self.tls_context.wrap_socket(conn, server_side=True), address
            except BaseException:
                conn.close()
                raise

    class RealTlsSafety(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.tmp = tempfile.TemporaryDirectory(prefix='wms-synthetic-print-tls-')
            cls.directory = Path(cls.tmp.name)
            now = datetime.datetime.now(datetime.timezone.utc)
            ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic WMS test CA')])
            ca_cert = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
                       .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
                       .not_valid_before(now - datetime.timedelta(days=1))
                       .not_valid_after(now + datetime.timedelta(days=1))
                       .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                       .sign(ca_key, hashes.SHA256()))
            cls.ca_file = cls.directory / 'synthetic-ca.pem'
            cls.ca_file.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
            cls.files = {}
            for kind in ('valid', 'expired', 'wrong_host'):
                key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic WMS listener')])
                before = now - datetime.timedelta(days=3) if kind == 'expired' else now - datetime.timedelta(days=1)
                after = now - datetime.timedelta(days=2) if kind == 'expired' else now + datetime.timedelta(days=1)
                san = (x509.DNSName('wrong.invalid') if kind == 'wrong_host'
                       else x509.IPAddress(ipaddress.ip_address('127.0.0.1')))
                cert = (x509.CertificateBuilder().subject_name(name).issuer_name(ca_name)
                        .public_key(key.public_key()).serial_number(x509.random_serial_number())
                        .not_valid_before(before).not_valid_after(after)
                        .add_extension(x509.SubjectAlternativeName([san]), critical=False)
                        .sign(ca_key, hashes.SHA256()))
                cert_file = cls.directory / (kind + '.pem')
                key_file = cls.directory / (kind + '-key.pem')
                cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
                key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
                cls.files[kind] = (cert_file, key_file)

        @classmethod
        def tearDownClass(cls):
            cls.tmp.cleanup()

        def setUp(self):
            self.patches = [mock.patch.object(sqlite3, 'connect', deny),
                            mock.patch.object(subprocess, 'Popen', deny),
                            mock.patch.object(agent.urllib.request, 'getproxies', return_value={})]
            for patch in self.patches:
                patch.start()
                self.addCleanup(patch.stop)

        def start_server(self, kind):
            server = Server(('127.0.0.1', 0), Handler)
            self.addCleanup(server.server_close)
            host, port = server.server_address
            self.assertEqual(host, '127.0.0.1')
            self.assertGreater(port, 1024)
            self.assertNotEqual(port, 8080)
            server.accepts, server.events, server.nonce = 0, [], secrets.token_urlsafe(24)
            server.tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server.tls_context.load_cert_chain(*map(str, self.files[kind]))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 5)
            self.addCleanup(server.shutdown)

            def check_address(address):
                if not isinstance(address, tuple) or address[:2] != (host, port):
                    deny()

            def connect(sock, address):
                check_address(address)
                return real_connect(sock, address)

            def connect_ex(sock, address):
                check_address(address)
                return real_connect_ex(sock, address)

            def resolve(node, service, *args, **kwargs):
                if node != host or int(service) != port:
                    deny()
                return real_getaddrinfo(node, service, *args, **kwargs)

            for patch in (mock.patch.object(socket.socket, 'connect', connect),
                          mock.patch.object(socket.socket, 'connect_ex', connect_ex),
                          mock.patch.object(socket, 'getaddrinfo', resolve),
                          mock.patch.object(ssl, '_create_default_https_context',
                                            lambda: default_context(cafile=str(self.ca_file)))):
                patch.start()
                self.addCleanup(patch.stop)
            return server, f'https://{host}:{port}'

        def test_valid_cert_heartbeat_claim_and_result(self):
            server, base = self.start_server('valid')
            cfg = {'server_url': base, 'token': server.nonce}
            with mock.patch.object(agent, 'enumerate_printers', return_value=[]):
                self.assertTrue(agent.send_heartbeat(cfg))
                self.assertEqual(agent.claim_job(cfg), {'id': 7})
                agent.report_result(cfg, 7, True, lease_token='synthetic-lease')
                agent.report_result(cfg, 7, False, lease_token='synthetic-lease')
            self.assertEqual([event[0] for event in server.events], [
                '/print_queue/api/v1/heartbeat', '/print_queue/api/v1/claim',
                '/print_queue/api/v1/jobs/7/complete', '/print_queue/api/v1/jobs/7/fail'])
            self.assertEqual(server.accepts, 4)

        def assert_certificate_failure(self, kind):
            server, base = self.start_server(kind)
            with self.assertLogs('wms_print_agent', level='WARNING') as logs:
                result = agent.api_call(base, server.nonce, '/claim', {'synthetic': True})
            self.assertEqual(server.accepts, 1, 'certificate failure must not trigger another connection')
            self.assertEqual(server.events, [], 'certificate failure must not send the credential or payload')
            self.assertEqual(result, (0, {}))
            self.assertIn('证书', '\n'.join(logs.output))
            self.assertTrue(any(entry.startswith('ERROR:') for entry in logs.output))
            self.assertNotIn(server.nonce, '\n'.join(logs.output))

        def test_expired_cert_never_sends_or_retries(self):
            self.assert_certificate_failure('expired')

        def test_wrong_host_never_sends_or_retries(self):
            self.assert_certificate_failure('wrong_host')

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RealTlsSafety)
    if suite.countTestCases() == 0:
        raise SystemExit('synthetic TLS test list must not be empty')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def test_synthetic_tls_handshake():
    saved_path = sys.path[:]
    try:
        main()
    finally:
        sys.path[:] = saved_path


if __name__ == '__main__':
    test_synthetic_tls_handshake()
