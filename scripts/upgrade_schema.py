"""Preview first; explicit --apply requires a fresh verified backup and offline lock."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from db import db
import models  # noqa: F401 -- metadata only, deliberately never import app.py
from runtime_guard import acquire_database_lease
from schema_upgrade import plan_schema_upgrade, apply_schema_upgrade


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args(argv)
    target = args.db.resolve(strict=True)
    if args.apply and (args.backup is None or args.backup.resolve() == target or args.backup.exists()):
        parser.error('--apply 必须指定尚不存在、且不同于源库的 --backup 路径')
    lease = acquire_database_lease(target) if args.apply else None
    try:
        with sqlite3.connect(target.as_uri() + '?mode=ro', uri=True) as source:
            plan = plan_schema_upgrade(source, db.metadata)
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            if plan['blocked']:
                return 2
            if not args.apply or not plan['statements']:
                return 0
            backup = args.backup.resolve()
            backup.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation: never overwrite a backup, even on a concurrent race.
            with backup.open('xb'):
                pass
            with sqlite3.connect(backup) as snapshot:
                source.backup(snapshot)
                if snapshot.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise RuntimeError('备份完整性校验失败，未执行升级')
        with sqlite3.connect(target) as connection:
            count = apply_schema_upgrade(connection, db.metadata)
        print(json.dumps({'applied': count, 'backup': str(backup)}, ensure_ascii=False))
        return 0
    finally:
        if lease is not None:
            lease.close()


if __name__ == '__main__':
    raise SystemExit(main())
