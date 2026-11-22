import os
import sqlite3
import subprocess
import sys
from pathlib import Path


from runtime_guard import acquire_database_lease

APP_DIR = Path(__file__).resolve().parents[1] / 'app'


def direct_start(target):
    # Only exercise startup in the child. Any scheduler, listener, or SQLite
    # connection to a different database would invalidate the result.
    probe = """
import runpy, sys
from pathlib import Path
app_dir, target = map(Path, sys.argv[1:])
sys.path.insert(0, str(app_dir))
def audit(event, args):
    if event in ('socket.bind', 'socket.connect'):
        raise AssertionError('unexpected network access')
    if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
        assert Path(args[0]).resolve() == target
sys.addaudithook(audit)
import notifications
def unexpected_scheduler(*args, **kwargs):
    raise SystemExit('unexpected scheduler start')
notifications.init_notification_scheduler = unexpected_scheduler
runpy.run_path(str(app_dir/'app.py'),run_name='__main__')
"""
    uri = 'sqlite:///' + target.as_posix()
    env = dict(os.environ, FLASK_ENV='production', DATABASE_URL=uri, WMS_DATABASE_URI=uri,
               WMS_NO_DB_TOUCH='1', WMS_SCHEMA_CHECK='strict',
               WMS_SKIP_AUTO_UPDATE='1', WMS_LOCAL_PRINT_AGENT='0', WMS_INIT_SAMPLE_DATA='0')
    return subprocess.run([sys.executable, '-B', '-c', probe, str(APP_DIR), str(target)],
                          env=env, cwd=target.parent, capture_output=True,
                          encoding='utf-8', errors='replace', timeout=45)


def test_direct_start_obeys_database_maintenance_lock(tmp_path):
    target = tmp_path / 'reserved.db'
    with acquire_database_lease(target):
        result = direct_start(target)
    assert result.returncode != 0
    assert '独占运行锁' in result.stderr
    assert not target.exists()


def test_direct_start_rejects_incompatible_protected_database(tmp_path):
    target = tmp_path / 'legacy.db'
    with sqlite3.connect(target) as conn:
        conn.execute('CREATE TABLE marker(value TEXT)')
        conn.execute("INSERT INTO marker VALUES('preserved')")
    result = direct_start(target)
    assert result.returncode != 0 and 'schema-check 失败' in result.stderr
    assert 'unexpected scheduler start' not in result.stderr
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [('marker',)]
        assert conn.execute('SELECT value FROM marker').fetchall() == [('preserved',)]


def test_direct_start_accepts_compatible_database(tmp_path):
    from sqlalchemy import create_engine
    from app import db

    target = tmp_path / 'compatible.db'
    engine = create_engine('sqlite:///' + target.as_posix())
    try:
        db.metadata.create_all(engine)
    finally:
        engine.dispose()

    result = direct_start(target)
    assert 'unexpected scheduler start' in result.stderr
    assert '[OK] database initialized' in result.stdout
