from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage6-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    backup_dir = Path(wms_app.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    verify_backup = backup_dir / 'stage6_verify_backup.db'
    verify_backup.write_bytes(b'stage6 backup marker')

    try:
        with app.app_context():
            wms_app.db.create_all()
            for username in ('stage6-admin', 'stage6-warehouse'):
                wms_app.User.query.filter_by(username=username).delete()
            wms_app.db.session.commit()

            admin = wms_app.User(username='stage6-admin', password_hash='not-used', role='admin', status='normal')
            warehouse = wms_app.User(username='stage6-warehouse', password_hash='not-used', role='warehouse', status='normal')
            wms_app.db.session.add_all([admin, warehouse])
            wms_app.db.session.commit()
            admin_id = admin.id
            warehouse_id = warehouse.id

        client = app.test_client()
        _login(client, admin_id)
        page = client.get('/ai/prelaunch')
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'BACKUP-READY' in html
        assert 'SECRET-KEY' in html
        assert 'AI-ROLLBACK-SWITCH' in html
        assert 'REGRESSION-COMMAND' in html

        _login(client, warehouse_id)
        forbidden = client.get('/ai/prelaunch')
        assert forbidden.status_code in (302, 403)

        with app.test_request_context('/_verify/stage6-prelaunch'):
            report = wms_app._ai_prelaunch_checks()

        expected_codes = {
            'BACKUP-READY',
            'SECRET-KEY',
            'AI-ROLLBACK-SWITCH',
            'AI-UNAUTHORIZED-ZERO',
            'AI-SUCCESS-RATE',
            'AI-WORK-QUEUE',
            'DB-ACCESS',
            'REGRESSION-COMMAND',
        }
        check_codes = {item['code'] for item in report['checks']}
        assert expected_codes.issubset(check_codes)
        assert isinstance(report['ready'], bool)
        assert report['passed'] + report['warned'] + report['failed'] == len(report['checks'])
        assert any(item['code'] == 'BACKUP-READY' and item['status'] == 'pass' for item in report['checks'])
    finally:
        try:
            verify_backup.unlink()
        except FileNotFoundError:
            pass

    print('PASS AI-STAGE6-PRELAUNCH: prelaunch checks, admin access, rollback readiness, and regression guidance are stable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
