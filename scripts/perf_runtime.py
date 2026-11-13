"""Owned synthetic performance runtime; imports are inert until explicitly called."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sys
import threading
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def require_runtime():
    if not sys.platform.startswith('linux'):
        raise SystemExit('安全阻断：性能诊断须使用现有 Linux 真隔离启动器')
    sys.path.insert(0, str(ROOT))
    from scripts.verify_db_guard import require_isolated_test_runtime
    return require_isolated_test_runtime()


def initialize_synthetic_app():
    require_runtime()
    from scripts.verify_db_guard import require_synthetic_memory_database
    require_synthetic_memory_database()
    # Only the authenticated synthetic process opts into loopback HTTP cookies.
    os.environ.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')
    os.environ.setdefault('WMS_SKIP_AUTO_UPDATE', '1')
    os.environ.setdefault('WMS_SKIP_STARTUP_BACKUP', '1')
    sys.path.insert(0, str(ROOT / 'app'))
    import app as w
    assert_memory_app(w)
    w.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    from werkzeug.security import generate_password_hash
    username, password = 'perf-' + secrets.token_hex(8), secrets.token_hex(24)
    with w.app.app_context():
        w.db.create_all()
        w.db.session.add(w.User(username=username, password_hash=generate_password_hash(password),
                               role='admin', status='normal', must_change_password=False))
        w.db.session.commit()
    return w, username, password


def assert_memory_app(w):
    require_runtime()
    with w.app.app_context():
        if str(w.db.engine.url) != 'sqlite:///:memory:':
            raise ValueError('安全阻断：性能诊断只允许当前新建内存库')
        if any(row[2] for row in w.db.session.execute(w.db.text('PRAGMA database_list'))):
            raise ValueError('安全阻断：性能诊断不能附加文件库')


def output_path(value, filename):
    require_runtime()
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    if path != ROOT / 'output' / filename:
        raise ValueError('安全阻断：性能结果仅可写入本次隔离 output 的指定文件')
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError('安全阻断：性能结果路径不能是链接')
    return path


def source_sha():
    require_runtime()
    # The launcher binds and protects this exact source SHA; no Git subprocess.
    from scripts.linux_test_runtime import PROOF
    return json.loads(PROOF.read_text(encoding='utf-8'))['sha']


def relative_target(path):
    parsed = urlsplit(path)
    if (not path.startswith('/') or path.startswith('//') or parsed.scheme or parsed.netloc
            or parsed.fragment or '\\' in path):
        raise ValueError('安全阻断：只能请求本次合成服务的相对路径')
    return path


class OwnedPerfHTTP:
    """Own the exact listening socket until all requests and channels are closed."""
    def __init__(self, w, username, password):
        assert_memory_app(w)
        self.w, self.username, self.password = w, username, password
        self.listener = self.server = self.thread = None
        self.sessions = []

    def __enter__(self):
        require_runtime()
        import socket
        from waitress import create_server
        from scripts.smoke_isolation import OwnedSocketLease, listener_url
        nonce = secrets.token_hex(32)
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if os.name == 'nt':
                self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            # Hold the socket continuously: never release a candidate port.
            self.listener.bind(('127.0.0.1', 0))
            self.listener.listen(128)
            base_url = listener_url(self.listener)
            identity = dict(base_url=base_url, nonce=nonce, pid=os.getpid())
            self.lease = OwnedSocketLease(self.listener, identity)
            self.identity, self.base_url = identity, base_url

            def identified_app(environ, start_response):
                def identified_start(status, headers, exc_info=None):
                    headers = [(name, value) for name, value in headers
                               if name.lower() != 'x-wms-isolated-smoke']
                    headers.append(('X-WMS-Isolated-Smoke', nonce))
                    return start_response(status, headers, exc_info)
                return self.w.app(environ, identified_start)

            self.channels = {}
            self.server = create_server(identified_app, sockets=[self.listener], map=self.channels,
                                        threads=4, asyncore_loop_timeout=0.1)
            if base_url != f'http://127.0.0.1:{int(self.server.effective_port)}':
                raise ValueError('安全阻断：waitress 监听身份变化')
            self.lease.validate(identity)
            self.thread = threading.Thread(target=self.server.run, daemon=True)
            self.thread.start()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def session(self):
        require_runtime()
        from scripts.smoke_isolation import IsolatedSession, IsolationError

        class NoRedirectSession(IsolatedSession):
            def send(self, request, **kwargs):
                if kwargs.get('allow_redirects') is not False:
                    raise IsolationError('性能请求不允许自动重定向')
                return super().send(request, **kwargs)

        if self.thread is None or not self.thread.is_alive():
            raise ValueError('安全阻断：自有性能服务不在运行')
        self.lease.validate(self.identity)
        session = NoRedirectSession(self.identity, self.lease)
        self.sessions.append(session)
        return session

    def __exit__(self, *_args):
        for session in self.sessions:
            session.close()
        if self.server is not None:
            self.server.task_dispatcher.shutdown()
            # Close only this server's private asyncore map, never global maps.
            for channel in list(self.channels.values()):
                channel.close()
        if self.listener is not None:
            self.listener.close()
        if self.thread is not None:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError('自有性能服务未能停止')
