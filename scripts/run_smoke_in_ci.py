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
import subprocess
import sys
import tempfile
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
WAIT_TIMEOUT_SEC = 60


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
    env.update(
        DATABASE_URL='sqlite:///' + (root / 'synthetic.db').as_posix(),
        SECRET_KEY='isolated-smoke-only-secret', WECHAT_HELPER_TOKEN='isolated-smoke-only-helper',
        WMS_NO_DB_TOUCH='1', WMS_SKIP_AUTO_UPDATE='1', WMS_SKIP_STARTUP_BACKUP='1',
        WMS_LOCAL_PRINT_AGENT='0', WMS_EXTERNAL_OPERATIONS_PAUSED='1',
        AUTO_BACKUP_ENABLED='false', SESSION_COOKIE_SECURE='false',
        LOG_FILE=str(root / 'app.log'), UPLOAD_FOLDER=str(root / 'uploads'),
        PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    return env


def start_server(root, log_file):
    """Launch only the owned child; no connection to an existing service."""
    env = clean_environment(root)
    # Explicit production-cookie opt-in at this startup consumer (A14/R6).
    env["FLASK_ENV"] = "production"
    env["WMS_ALLOW_INSECURE_COOKIE"] = "1"
    return subprocess.Popen(
        [sys.executable, '-I', '-B', '-X', 'utf8', str(Path(__file__).resolve()), '--serve', str(root)],
        cwd=str(root), env=env, stdout=log_file, stderr=subprocess.STDOUT)


def wait_ready(proc, root, timeout=WAIT_TIMEOUT_SEC):
    """Wait for our child's bound-socket receipt without making HTTP requests."""
    if __package__:
        from .smoke_isolation import read_identity
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from smoke_isolation import read_identity
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and proc.poll() is None:
        path = root / 'ready.json'
        if path.exists():
            identity = read_identity(path)
            if identity['pid'] != proc.pid:
                raise ValueError('Ready file belongs to another process')
            return path
        time.sleep(0.1)
    raise RuntimeError('Owned smoke child did not become ready')


def serve_isolated(root):
    """Import a copied application only after proving the new state is empty."""
    root = root.resolve(strict=True)
    if (root.parent != Path(tempfile.gettempdir()).resolve()
            or not root.name.startswith('wms-isolated-smoke-')
            or (root / 'synthetic.db').exists() or (root / 'program').exists()
            or os.environ.get('DATABASE_URL') != 'sqlite:///' + (root / 'synthetic.db').as_posix()):
        raise ValueError('Refusing reused or unowned smoke state')
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
    nonce = secrets.token_hex(32)  # Instance identity, never an account password.

    @w.app.after_request
    def identify_smoke_response(response):
        response.headers['X-WMS-Isolated-Smoke'] = nonce
        return response

    server = create_server(w.app, host='127.0.0.1', port=0, threads=4)
    port = int(server.effective_port)
    if port < 10240:
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.serve:
        serve_isolated(args.serve)
        return 0
    with tempfile.TemporaryDirectory(prefix='wms-isolated-smoke-') as directory:
        root = Path(directory).resolve()
        proc = None
        with (root / 'server.log').open('w', encoding='utf-8') as log_file:
            try:
                proc = start_server(root, log_file)
                identity_file = wait_ready(proc, root)
                print(f'[isolation] owned child PID={proc.pid}; fresh database={root / "synthetic.db"}',
                      flush=True)
                result = subprocess.run(
                    [sys.executable, '-I', '-B', '-X', 'utf8', str(REPO_ROOT / 'scripts/full_smoke_test.py'),
                     '--isolation-file', str(identity_file)], cwd=str(root),
                    env=clean_environment(root))
                return result.returncode
            except (OSError, ValueError, RuntimeError) as error:
                print(f'Isolated smoke startup refused: {error}', flush=True)
                log_file.flush()
                print((root / 'server.log').read_text(encoding='utf-8')[-8000:], flush=True)
                return 2
            finally:
                stop_server(proc)


if __name__ == '__main__':
    sys.exit(main())
