#!/usr/bin/env python3
"""Run writable smoke checks against a new owned server and disposable database.

BUG-2026-11-06-001: no inherited database, default production URL or HTTP readiness
probe. The child publishes its identity only after binding an OS-assigned port.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
WAIT_TIMEOUT_SEC = 60

if __package__:
    from .smoke_isolation import (OwnedSocketLease, encode_listener_capability,
                                  listener_url, read_identity, receive_listener_capability)
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from smoke_isolation import (OwnedSocketLease, encode_listener_capability,
                                 listener_url, read_identity, receive_listener_capability)


def clean_environment(root):
    """Discard inherited application state before the child imports Flask."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('WMS_', 'FLASK_', 'SQLALCHEMY_', 'WECHAT_',
                                  'OPENAI_', 'ANTHROPIC_', 'DEEPSEEK_', 'DASHSCOPE_',
                                  'TENCENT', 'SESSION_', 'REMEMBER_', 'AUTO_BACKUP_'))
           and key not in {'DATABASE_URL', 'SECRET_KEY', 'UPLOAD_FOLDER', 'LOG_FILE',
                           'PYTHONPATH', 'PYTHONHOME'}}
    env['FLASK_ENV'] = 'production'
    env['WMS_ALLOW_INSECURE_COOKIE'] = '1'
    # This reference is not proof by itself; every child rechecks the kernel.
    env['WMS_TEST_RUNTIME_PROOF'] = os.environ.get('WMS_TEST_RUNTIME_PROOF', '')
    env.update(
        DATABASE_URL='sqlite:///' + (root / 'synthetic.db').as_posix(),
        SECRET_KEY='isolated-smoke-only-secret', WECHAT_HELPER_TOKEN='isolated-smoke-only-helper',
        WMS_NO_DB_TOUCH='1', WMS_SKIP_AUTO_UPDATE='1', WMS_SKIP_STARTUP_BACKUP='1',
        WMS_LOCAL_PRINT_AGENT='0', WMS_EXTERNAL_OPERATIONS_PAUSED='1',
        AUTO_BACKUP_ENABLED='false', SESSION_COOKIE_SECURE='false',
        LOG_FILE=str(root / 'app.log'), UPLOAD_FOLDER=str(root / 'uploads'),
        PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    return env


def _socket_child_options(listener):
    return {'pass_fds': (listener.fileno(),)} if os.name != 'nt' else {}


def _send_capability(proc, listener, nonce, server_pid):
    data = encode_listener_capability(listener, proc.pid, nonce, server_pid)
    if proc.stdin is None:
        raise RuntimeError('Owned child has no private capability pipe')
    proc.stdin.write(data)
    proc.stdin.close()


def start_server(root, log_file, listener, nonce):
    """Launch only the owned child; no connection to an existing service."""
    env = clean_environment(root)
    # Explicit production-cookie opt-in at this startup consumer (A14/R6).
    env["FLASK_ENV"] = "production"
    env["WMS_ALLOW_INSECURE_COOKIE"] = "1"
    proc = subprocess.Popen(
        [sys.executable, '-I', '-B', '-X', 'utf8', str(Path(__file__).resolve()),
         '--serve', str(root), '--listener-stdin'],
        cwd=str(root), env=env, stdin=subprocess.PIPE, stdout=log_file,
        stderr=subprocess.STDOUT, **_socket_child_options(listener))
    try:
        _send_capability(proc, listener, nonce, proc.pid)
    except BaseException:
        stop_server(proc)
        raise
    return proc


def wait_ready(proc, root, listener, nonce, timeout=WAIT_TIMEOUT_SEC):
    """Wait for our child's bound-socket receipt without making HTTP requests."""
    lease = OwnedSocketLease(listener, dict(base_url=listener_url(listener), nonce=nonce, pid=proc.pid))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and proc.poll() is None:
        path = root / 'ready.json'
        if path.exists():
            identity = read_identity(path)
            lease.validate(identity)
            if proc.poll() is not None:
                raise RuntimeError('Owned smoke child exited before readiness')
            return path
        time.sleep(0.1)
    raise RuntimeError('Owned smoke child did not become ready')


def serve_isolated(root, listener, lease):
    """Import a copied application only after proving the new state is empty."""
    if lease.pid != os.getpid():
        raise ValueError('Listener capability belongs to another child')
    lease.validate(dict(base_url=listener_url(listener), nonce=lease.nonce, pid=os.getpid()))
    root = Path(os.path.abspath(root))
    if (root.parent != Path(os.path.abspath(tempfile.gettempdir()))
            or not root.name.startswith('wms-isolated-smoke-')
            or (root / 'synthetic.db').exists() or (root / 'program').exists()
            or os.environ.get('DATABASE_URL') != 'sqlite:///' + (root / 'synthetic.db').as_posix()):
        raise ValueError('Refusing reused or unowned smoke state')
    # The source is immutable and contains Git blobs only; no host files/network
    # are accessible to this process or descendants, including native libraries.
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.linux_test_runtime import require_subprocess_boundary
    require_subprocess_boundary()
    # Copy program files so import-time relative files cannot modify the checkout.
    program = root / 'program'
    shutil.copytree(REPO_ROOT / 'app', program,
                    ignore=shutil.ignore_patterns('instance', 'logs', 'uploads', 'backups',
                                                 '__pycache__', '*.db', '*.db-*', '.env*',
                                                 'android-native-wms', '.venv', 'venv'))
    sys.path[:0] = [str(program), str(REPO_ROOT)]
    os.chdir(root)
    # A14: clean_environment explicitly sets WMS_ALLOW_INSECURE_COOKIE=1.
    import app as w
    from werkzeug.security import generate_password_hash
    from waitress import create_server
    with w.app.app_context():
        if Path(w.db.engine.url.database).resolve() != root / 'synthetic.db':
            raise ValueError('Application database does not match owned synthetic state')
        w.db.create_all()
        w.db.session.add(w.User(username='admin', role='admin', status='normal',
                               password_hash=generate_password_hash('admin'),
                               must_change_password=True))
        w.db.session.commit()
    nonce = lease.nonce

    @w.app.after_request
    def identify_smoke_response(response):
        response.headers['X-WMS-Isolated-Smoke'] = nonce
        return response

    server = create_server(w.app, sockets=[listener], threads=4)
    port = int(server.effective_port)
    if listener_url(listener) != f'http://127.0.0.1:{port}':
        server.close()
        raise ValueError('OS assigned a port outside the isolated test range')
    identity = dict(schema=1, pid=os.getpid(), nonce=nonce,
                    base_url=f'http://127.0.0.1:{port}', database=str(root / 'synthetic.db'))
    draft = root / 'ready.tmp'
    draft.write_text(json.dumps(identity), encoding='utf-8')
    draft.replace(root / 'ready.json')
    try:
        server.run()
    finally:
        server.close()


def stop_server(proc):
    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def run_client(root, identity_file, listener, nonce, server_pid):
    proc = subprocess.Popen(
        [sys.executable, '-I', '-B', '-X', 'utf8', str(REPO_ROOT / 'scripts/full_smoke_test.py'),
         '--isolation-file', str(identity_file), '--listener-stdin'],
        cwd=str(root), env=clean_environment(root), stdin=subprocess.PIPE,
        **_socket_child_options(listener))
    try:
        _send_capability(proc, listener, nonce, server_pid)
        return proc.wait()
    except BaseException:
        stop_server(proc)
        raise


def main(argv=None):
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.linux_test_runtime import require_subprocess_boundary
    require_subprocess_boundary()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--listener-stdin', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.serve:
        if not args.listener_stdin:
            parser.error('隔离服务必须接收启动器持有的监听句柄')
        listener, lease = receive_listener_capability(sys.stdin.buffer)
        with listener:
            serve_isolated(args.serve, listener, lease)
        return 0
    with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
        root = Path(directory).resolve()
        proc = None
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener, \
                (root / 'server.log').open('w', encoding='utf-8') as log_file:
            try:
                if os.name == 'nt':
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                listener.bind(('127.0.0.1', 0))
                listener.listen(8)
                listener_url(listener)
                nonce = secrets.token_hex(32)
                proc = start_server(root, log_file, listener, nonce)
                identity_file = wait_ready(proc, root, listener, nonce)
                print(f'[isolation] owned child PID={proc.pid}; fresh database={root / "synthetic.db"}',
                      flush=True)
                return run_client(root, identity_file, listener, nonce, proc.pid)
            except (OSError, ValueError, RuntimeError) as error:
                print(f'Isolated smoke startup refused: {error}', flush=True)
                log_file.flush()
                print((root / 'server.log').read_text(encoding='utf-8')[-8000:], flush=True)
                return 2
            finally:
                stop_server(proc)


if __name__ == '__main__':
    sys.exit(main())
