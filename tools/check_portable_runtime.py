"""Verify a pristine Windows package in a disposable copy, never production."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request

RECEIPT_CHECKS = ['dependencies', 'manifest', 'imports', 'fresh_initialization',
                  'existing_database_preserved', 'guarded_startup', 'chinese_login', 'footer_css']


@contextmanager
def disposable_directory():
    temporary = tempfile.TemporaryDirectory(prefix='wms-package-check-')
    try:
        yield temporary.name
    finally:
        # Windows can briefly retain directory handles after the server exits.
        # Retry only our own temporary directory and still fail if it stays locked.
        for attempt in range(21):
            try:
                temporary.cleanup()
                break
            except PermissionError:
                if attempt == 20:
                    raise
                time.sleep(.5)


def verify_package(package):
    package = Path(package).resolve(strict=True)
    if (package / 'app/instance/inventory.db').exists():
        raise ValueError('Distribution contains a database; do not publish it.')
    if not (package / 'python/python.exe').is_file():
        raise ValueError('Embedded Python is missing.')
    with disposable_directory() as temporary:
        root = Path(temporary) / 'WMS'
        shutil.copytree(package, root)
        python = str(root / 'python/python.exe')
        env = {k: v for k, v in os.environ.items() if not k.startswith('WMS_')
               and k not in {'DATABASE_URL', 'PYTHONPATH', 'LOG_FILE', 'SECRET_KEY'}}
        env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                   WMS_LOCAL_PRINT_AGENT='0', WMS_SKIP_STARTUP_BACKUP='1', AUTO_BACKUP_ENABLED='false',
                   WMS_BACKUP_DIR=str(root / 'backups'), UPLOAD_FOLDER=str(root / 'uploads'))
        subprocess.run([python, str(root / 'tools/check_runtime_dependencies.py')],
                       cwd=root, env=env, check=True, timeout=60)
        # Keep the existing dependency gate first, then verify the complete artifact
        # in this empty reconstruction before imports or synthetic initialization.
        subprocess.run([python, str(root / 'tools/manage_release_manifest.py'), 'verify', '--root', str(root)],
                       cwd=root, env=env, check=True, timeout=120)
        identity = json.loads((root / 'wms-release.json').read_text(encoding='utf-8-sig'))
        subprocess.run([python, '-c', 'import flask, flask_sqlalchemy, flask_wtf, pandas, numpy, openpyxl, PIL, pydantic, cryptography, waitress; import importlib.util; assert importlib.util.find_spec("flasgger") is None'], env=env, check=True, timeout=60)
        initializer = [python, str(root / 'tools/init_portable_database.py'), '--initialize']
        subprocess.run(initializer, cwd=root, env=env, check=True, timeout=120)
        database = root / 'app/instance/inventory.db'
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        repeated = subprocess.run(initializer, cwd=root, env=env, capture_output=True, timeout=30)
        assert repeated.returncode != 0 and hashlib.sha256(database.read_bytes()).hexdigest() == before
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env.update(DATABASE_URL='sqlite:///' + database.as_posix(), WMS_NO_DB_TOUCH='1',
                   WMS_SKIP_AUTO_UPDATE='1', WMS_ALLOW_AUTO_SECRET_KEY='1',
                   WMS_ALLOW_INSECURE_COOKIE='1', WMS_HOST='127.0.0.1', WMS_PORT=str(port),
                   LOG_FILE=str(root / 'server.log'))
        with (root / 'console.log').open('w', encoding='utf-8') as log:
            proc = subprocess.Popen([python, str(root / 'app/run_server.py')], cwd=root / 'app', env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 60
                while True:
                    if proc.poll() is not None:
                        raise RuntimeError((root / 'console.log').read_text(encoding='utf-8'))
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/login', timeout=3) as response:
                            html = response.read().decode('utf-8')
                        break
                    except OSError:
                        if time.monotonic() > deadline:
                            raise
                        time.sleep(.5)
                assert 'OK1949-2024' in html and '问题反馈' in html and '登录' in html
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/static/css/copyright.css', timeout=3) as response:
                    assert response.status == 200
            finally:
                proc.terminate()
                proc.wait(timeout=20)
    print('PASS: embedded imports, no Flasgger, fresh initialization, existing database preservation, guarded startup, Chinese login and footer CSS.')
    return dict(success=True, source_sha=identity['source_sha'],
                artifact_id=identity['artifact_id'], checks=RECEIPT_CHECKS)


def write_runtime_receipt(path, result):
    """Write once, only after the actual disposable installation checks pass."""
    if (not isinstance(result, dict) or result.get('success') is not True or
            not re.fullmatch(r'[0-9a-f]{40}', str(result.get('source_sha', ''))) or
            not re.fullmatch(r'[0-9a-f]{64}', str(result.get('artifact_id', ''))) or
            result.get('checks') != RECEIPT_CHECKS):
        raise ValueError('No complete runtime validation result.')
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args(argv)
    result = verify_package(args.package)
    if args.receipt:
        write_runtime_receipt(args.receipt, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
