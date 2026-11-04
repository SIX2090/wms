"""Initialize only a brand-new portable installation; never open an existing database."""
import argparse
import os
from pathlib import Path
import sys


def initialize_fresh(root):
    root = Path(root).resolve()
    app_dir = root / 'app'
    database = app_dir / 'instance' / 'inventory.db'
    if not (app_dir / 'app.py').is_file():
        raise ValueError('Portable app/app.py is missing.')
    database.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive reservation also rejects a competing installer or a symlink.
    descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    os.environ.update({
        'DATABASE_URL': 'sqlite:///' + database.as_posix(),
        'WMS_DATABASE_URI': 'sqlite:///' + database.as_posix(),
        'WMS_NO_DB_TOUCH': '0', 'WMS_SKIP_STARTUP_DB_UPGRADE': '0',
        'WMS_INIT_SAMPLE_DATA': '0', 'WMS_SKIP_AUTO_UPDATE': '1',
        'WMS_ALLOW_AUTO_SECRET_KEY': '1', 'WMS_ALLOW_INSECURE_COOKIE': '1',
        'LOG_FILE': str(root / 'setup.log'),
    })
    sys.path.insert(0, str(app_dir))
    os.chdir(app_dir)
    from app import app, initialize_database
    with app.app_context():
        initialize_database()
    return database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initialize', action='store_true', required=True)
    parser.parse_args()
    try:
        database = initialize_fresh(Path(__file__).resolve().parent.parent)
    except FileExistsError:
        sys.stderr.write('Existing database preserved. Initialization refused.\n')
        return 1
    sys.stdout.write('Fresh database initialized: ' + str(database) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
