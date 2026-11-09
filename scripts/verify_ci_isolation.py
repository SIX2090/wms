"""Exercise the actual container boundary before running business assertions."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.linux_test_runtime import PROOF, SOURCE, require_linux_runtime
from scripts.verify_db_guard import owned_test_file, validate_owned_test_file


def main():
    profile = require_linux_runtime()
    count = 0
    def check(condition, message):
        nonlocal count
        if not condition:
            raise AssertionError(message)
        count += 1
        print('[isolation self-test] PASS ' + message, flush=True)

    with tempfile.TemporaryDirectory(prefix='boundary-') as directory:
        root = Path(directory)
        check(root.is_relative_to(profile), 'temporary files belong to this run')
        with sqlite3.connect(':memory:') as db:
            check(db.execute('select 41 + 1').fetchone() == (42,), 'new memory database executes SQL')
        database = root / 'synthetic.db'
        with sqlite3.connect(database) as db:
            db.execute('create table synthetic(value integer)')
            db.execute('insert into synthetic values (42)')
        check(validate_owned_test_file(database) == database, 'owned synthetic file accepted')
        with owned_test_file(database) as pinned:
            with sqlite3.connect(pinned.as_uri() + '?mode=ro', uri=True) as db:
                check(db.execute('select value from synthetic').fetchone() == (42,), 'pinned synthetic database is readable')
        alias = root / 'alias'; alias.symlink_to(SOURCE / 'README.md')
        try:
            validate_owned_test_file(alias)
        except SystemExit:
            check(True, 'symlink outside synthetic profile refused')
        else:
            check(False, 'symlink accepted')
        for path in (PROOF, SOURCE / 'app/app.py'):
            try:
                fd = os.open(path, os.O_WRONLY)
            except PermissionError:
                check(True, 'proof/source cannot be opened for writing')
            except OSError as exc:
                import errno
                check(exc.errno == errno.EROFS, 'source is mounted read-only')
            else:
                os.close(fd)
                check(False, 'protected file writable')
        code = ('import sys;sys.path.insert(0,"/opt/wms");'
                'from scripts.linux_test_runtime import require_linux_runtime;'
                'require_linux_runtime();print("actual-child-ran")')
        child = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=10)
        check(child.returncode == 0 and 'actual-child-ran' in child.stdout, 'descendant inherits the kernel boundary')
        for key, value in [('WMS_TEST_RUNTIME_PROOF', str(root / 'forged.json')),
                           ('DATABASE_URL', 'sqlite:////synthetic-invalid.db'),
                           ('WMS_DATABASE_URI', 'mysql://synthetic.invalid/test'), ('FLASK_ENV', 'production')]:
            rejected = subprocess.run([sys.executable, '-I', '-B', '-c', code],
                                      env=dict(os.environ, **{key: value}), capture_output=True, text=True, timeout=10)
            check(rejected.returncode != 0 and 'actual-child-ran' not in rejected.stdout,
                  'child rejects invalid ' + key + ' before application import')
        # This is a new listener in this container, never the host's loopback.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen(1)
            check(listener.getsockname()[1] >= 10240, 'private loopback gets a high test port')
    print(json.dumps({'isolation_self_tests': count, 'success': True}), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
