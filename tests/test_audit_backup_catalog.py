"""Repair task: AUDIT-FULL-20261016-001-F08; temporary databases/backups only."""
import hashlib
import importlib.util
import os
import re
from pathlib import Path
import sqlite3
import stat
from types import SimpleNamespace
from urllib.parse import quote

import pytest

import app as wms
import backup_catalog as catalog
import backup_scheduler

ROOT = Path(__file__).resolve().parents[1]


def make_database(path, value='synthetic'):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute('CREATE TABLE sample (value TEXT)')
        connection.execute('INSERT INTO sample VALUES (?)', (value,))
        connection.commit()
    finally:
        connection.close()
    return path


@pytest.fixture
def case(tmp_path, monkeypatch):
    manual, daily, update = (tmp_path / name for name in ('manual', 'daily', 'update'))
    for directory in (manual, daily, update): directory.mkdir()
    database = make_database(tmp_path / 'business.db', 'current-business')
    monkeypatch.setattr(wms, 'BACKUP_DIR', str(manual))
    monkeypatch.setattr(wms, 'get_database_file_path', lambda: str(database))
    monkeypatch.setattr(catalog, 'UPDATE_BACKUP_DIR', update)
    monkeypatch.setenv('WMS_BACKUP_DIR', str(daily))
    monkeypatch.setenv('BACKUP_RETENTION_DAYS', '30')
    monkeypatch.setenv('AUTO_BACKUP_TIME', '02:00')
    monkeypatch.setenv('AUTO_BACKUP_ENABLED', 'true')
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        assert all(engine.url.database in (None, '', ':memory:') for engine in wms.db.engines.values())
        wms.db.drop_all(); wms.db.create_all()
        admin = wms.User(username='backup-audit-admin', password_hash='synthetic-unused', role='admin', must_change_password=False)
        viewer = wms.User(username='backup-audit-viewer', password_hash='synthetic-unused', role='viewer', must_change_password=False)
        wms.db.session.add_all([admin, viewer]); wms.db.session.commit()
        admin_id, viewer_id = admin.id, viewer.id
    client = wms.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(admin_id); session['_fresh'] = True
    yield SimpleNamespace(client=client, manual=manual, daily=daily, update=update,
                          database=database, viewer_id=viewer_id)
    with wms.app.app_context():
        wms.db.session.remove()
        assert all(engine.url.database in (None, '', ':memory:') for engine in wms.db.engines.values())
        wms.db.drop_all()


def test_get_backup_sources(case):
    sources = catalog.get_backup_sources(case.manual)
    assert list(sources) == ['daily', 'manual', 'update']
    assert sources['daily']['directory'] == case.daily
    assert sources['manual']['directory'] == case.manual
    assert sources['update']['directory'] == case.update
    assert sources['daily']['retention'] == '保留最近 30 天'
    assert sources['manual']['retention'] == sources['update']['retention'] == '不自动清理'


@pytest.mark.parametrize('raw,expected', [('30', 30), ('7', 7), ('0', 1), ('invalid', 30)])
def test_get_retention_days(monkeypatch, raw, expected):
    monkeypatch.setenv('BACKUP_RETENTION_DAYS', raw)
    assert backup_scheduler.get_retention_days() == expected


def test_get_backup_settings(monkeypatch):
    monkeypatch.setenv('AUTO_BACKUP_ENABLED', '0')
    monkeypatch.setenv('AUTO_BACKUP_TIME', 'invalid')
    monkeypatch.setenv('BACKUP_RETENTION_DAYS', '7')
    assert catalog.get_backup_settings() == {'enabled': False, 'time': '02:00', 'retention_days': 7}


def test_list_backup_files(case, monkeypatch):
    make_database(case.manual / 'manual.db')
    make_database(case.daily / 'auto_daily_synthetic_inventory.db')
    make_database(case.daily / 'unregistered.db')
    make_database(case.update / 'before_github_update_synthetic_inventory.db')
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in case.manual.parent.rglob('*.db')}
    sources = catalog.get_backup_sources(case.manual)
    rows, warnings = catalog.list_backup_files(sources, [case.database])
    assert not warnings
    assert {row['source'] for row in rows} == {'manual', 'daily', 'update'}
    assert len(rows) == 3
    assert all('path' not in row for row in rows)
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in case.manual.parent.rglob('*.db')}
    assert before == after
    monkeypatch.setenv('WMS_BACKUP_DIR', str(case.manual))
    make_database(case.manual / 'auto_daily_shared_inventory.db')
    rows, warnings = catalog.list_backup_files(catalog.get_backup_sources(case.manual))
    shared = [row for row in rows if row['filename'] == 'auto_daily_shared_inventory.db']
    assert len(shared) == 1 and shared[0]['source'] == 'daily'


def test_resolve_backup_file(case):
    path = make_database(case.daily / 'auto_daily_selected_inventory.db')
    assert catalog.resolve_backup_file(catalog.get_backup_sources(case.manual), 'daily', path.name) == path
    with pytest.raises(ValueError, match='业务数据库'):
        catalog.resolve_backup_file(catalog.get_backup_sources(case.manual), 'daily', path.name, [path])


@pytest.mark.parametrize('filename', ['../business.db', r'..\business.db', 'C:business.db', 'config.py', 'bad\x00.db'])
def test_backup_resolver_rejects_non_backup_paths(case, filename):
    with pytest.raises(ValueError): catalog.resolve_backup_file(catalog.get_backup_sources(case.manual), 'manual', filename)


def test_backup_resolver_rejects_reparse_file(case, monkeypatch):
    path = make_database(case.manual / 'linked.db')
    original = Path.lstat
    def fake_lstat(self):
        if self == path: return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        return original(self)
    monkeypatch.setattr(Path, 'lstat', fake_lstat)
    with pytest.raises(ValueError, match='链接'):
        catalog.resolve_backup_file(catalog.get_backup_sources(case.manual), 'manual', path.name)


@pytest.mark.parametrize('kind,expected', [('valid', True), ('corrupt', False), ('wal', None), ('missing', None)])
def test_verify_backup_integrity(tmp_path, kind, expected):
    path = tmp_path / 'backup.db'
    if kind in {'valid', 'wal'}: make_database(path)
    if kind == 'corrupt': path.write_bytes(b'synthetic invalid database')
    if kind == 'wal': Path(str(path) + '-wal').write_bytes(b'synthetic wal must not be ignored')
    before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
    result = catalog.verify_backup_integrity(path)
    assert result['valid'] is expected
    assert {file.name: file.read_bytes() for file in tmp_path.iterdir()} == before


def test_backup_page_includes_actual_daily_and_update_sources(case):
    make_database(case.manual / 'manual.db')
    make_database(case.daily / 'auto_daily_shown_inventory.db')
    make_database(case.update / 'before_github_update_shown_inventory.db')
    result = case.client.get('/backup')
    assert result.status_code == 200
    html = result.get_data(as_text=True)
    assert 'auto_daily_shown_inventory.db' in html and 'before_github_update_shown_inventory.db' in html
    assert '保留最近 30 天' in html and '不自动清理' in html
    assert '02:00' in html and '每日自动备份' in html
    filtered = case.client.get('/backup?source=daily&search=shown&sort=size_bytes&order=asc').get_data(as_text=True)
    assert 'auto_daily_shown_inventory.db' in filtered
    assert 'manual.db' not in filtered and 'before_github_update_shown_inventory.db' not in filtered


def test_template_supports_old_running_backend_until_manual_restart(case):
    from flask import render_template
    legacy = {'filename': 'old-directory.db', 'created_at': None, 'size': '1 KB',
              'url': '/backup/download/old-directory.db'}
    with wms.app.test_request_context('/backup?embedded=1'):
        html = render_template('backup.html', backups=[legacy], filters={'search': ''},
                               sort_by='created_at', sort_order='desc')
    assert 'old-directory.db' in html and '需重启 WMS 服务后启用' in html
    assert 'data-backup-action="verify"' not in html
    assert 'data-backup-action="delete"' not in html


def test_daily_backup_generation_is_visible_without_moving_files(case):
    path = backup_scheduler.run_daily_backup(wms.app)
    assert path.parent == case.daily
    assert path.name in case.client.get('/backup?source=daily').get_data(as_text=True)
    result = case.client.get('/backup/download/' + path.name + '?source=daily')
    assert result.status_code == 200 and result.data == path.read_bytes()


@pytest.mark.parametrize('source', ['manual', 'daily', 'update'])
def test_download_uses_explicit_registered_source(case, source):
    filename = 'auto_daily_same_inventory.db'
    for key in ['manual', 'daily', 'update']:
        (getattr(case, key) / filename).write_bytes(key.encode())
    result = case.client.get('/backup/download/' + filename + '?source=' + source)
    assert result.status_code == 200 and result.data == source.encode()


@pytest.mark.parametrize('source', ['unknown', '../daily', r'C:\outside'])
def test_request_cannot_register_an_arbitrary_backup_root(case, source):
    (case.manual / 'manual.db').write_bytes(b'manual')
    assert case.client.get('/backup/download/manual.db?source=' + quote(source)).status_code == 400
    assert (case.manual / 'manual.db').read_bytes() == b'manual'


@pytest.mark.parametrize('source', ['manual', 'daily', 'update'])
def test_delete_only_the_human_selected_source(case, source):
    filename = 'auto_daily_delete_selected_inventory.db'
    for key in ['manual', 'daily', 'update']: (getattr(case, key) / filename).write_bytes(key.encode())
    result = case.client.post('/backup/delete', json={'source': source, 'filename': filename})
    assert result.status_code == 200 and result.get_json()['status'] == 'success'
    for key in ['manual', 'daily', 'update']:
        assert (getattr(case, key) / filename).exists() == (key != source)
    assert case.database.exists()


def test_verify_backup(case):
    path = make_database(case.daily / 'auto_daily_verify_inventory.db')
    before = path.read_bytes()
    result = case.client.get('/backup/verify/' + path.name + '?source=daily')
    assert result.status_code == 200 and result.get_json()['valid'] is True
    assert path.read_bytes() == before
    assert not Path(str(path) + '-wal').exists() and not Path(str(path) + '-shm').exists()
    assert case.client.post('/backup/restore', data={'filename': path.name, 'source': 'daily'}).status_code == 403


def test_backup_actions_require_admin(case):
    filename = 'auto_daily_private_inventory.db'
    make_database(case.daily / filename)
    with case.client.session_transaction() as session: session['_user_id'] = str(case.viewer_id)
    for url in ['/backup', '/backup/download/' + filename + '?source=daily', '/backup/verify/' + filename + '?source=daily']:
        assert case.client.get(url, headers={'X-Requested-With': 'XMLHttpRequest'}).status_code == 403
    assert case.client.get('/backup').status_code == 302
    assert case.client.post('/backup/delete', json={'source': 'daily', 'filename': filename},
                            headers={'X-Requested-With': 'XMLHttpRequest'}).status_code == 403
    assert (case.daily / filename).exists()


def test_active_business_database_is_not_a_backup_action(case, monkeypatch):
    monkeypatch.setattr(wms, 'BACKUP_DIR', str(case.database.parent))
    before = case.database.read_bytes()
    assert case.client.get('/backup/download/business.db').status_code == 400
    assert case.client.post('/backup/delete', json={'filename': 'business.db'}).status_code == 400
    assert case.database.read_bytes() == before
    assert 'business.db' not in case.client.get('/backup').get_data(as_text=True)


def test_delete_keeps_the_exact_selected_filename(case):
    selected = case.manual / ' selected.db'; selected.write_bytes(b'selected')
    other = case.manual / 'selected.db'; other.write_bytes(b'keep-other')
    result = case.client.post('/backup/delete', data={'source': 'manual', 'filename': selected.name})
    assert result.status_code == 200
    assert not selected.exists() and other.read_bytes() == b'keep-other'


def test_backup_delete_requires_csrf_and_accepts_valid_frontend_header(case, monkeypatch):
    filename = 'auto_daily_csrf_inventory.db'
    path = case.daily / filename; path.write_bytes(b'synthetic backup')
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', True)
    html = case.client.get('/backup').get_data(as_text=True)
    token = re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)
    payload = {'filename': filename, 'source': 'daily'}
    assert case.client.post('/backup/delete', json=payload).status_code == 400
    assert path.exists()
    assert case.client.post('/backup/delete', json=payload, headers={'X-CSRFToken': token}).status_code == 200
    assert not path.exists()


@pytest.mark.parametrize('payload', [{'filename': ['manual.db']}, {'filename': 42},
                                    {'filename': 'manual.db', 'source': '../outside'}])
def test_delete_rejects_invalid_input_without_deleting_files(case, payload):
    path = case.manual / 'manual.db'; path.write_bytes(b'keep')
    assert case.client.post('/backup/delete', json=payload).status_code == 400
    assert path.read_bytes() == b'keep'


@pytest.mark.parametrize('sort', ['filename', 'created_at', 'size_bytes'])
def test_all_backup_sort_keys_keep_type_safe_none_defaults(case, monkeypatch, sort):
    from datetime import datetime
    import routes.backup as routes
    rows = [dict(id='manual:one.db', filename='one.db', source='manual', source_label='manual',
                 retention='keep', size_bytes=None, created_at=None),
            dict(id='manual:two.db', filename='two.db', source='manual', source_label='manual',
                 retention='keep', size_bytes=5, created_at=datetime(2026, 1, 1))]
    monkeypatch.setattr(routes, 'list_backup_files', lambda sources, protected: (rows, []))
    result = case.client.get('/backup?sort=' + sort)
    assert result.status_code == 200
    assert 'one.db' in result.get_data(as_text=True) and 'two.db' in result.get_data(as_text=True)


def test_unreadable_source_is_visible_and_does_not_hide_other_backups(case, monkeypatch):
    make_database(case.manual / 'visible.db')
    original = Path.iterdir
    def read_directory(path):
        if path == case.daily: raise PermissionError('synthetic source permission failure')
        return original(path)
    monkeypatch.setattr(Path, 'iterdir', read_directory)
    result = case.client.get('/backup')
    assert result.status_code == 200
    assert 'visible.db' in result.get_data(as_text=True)
    assert '每日自动备份目录读取失败' in result.get_data(as_text=True)


def test_catalog_listing_does_not_open_sqlite_databases(case, monkeypatch):
    make_database(case.manual / 'metadata_only.db')
    def forbidden_open(*args, **kwargs): raise AssertionError('listing must not scan SQLite files')
    with monkeypatch.context() as scope:
        scope.setattr(catalog.sqlite3, 'connect', forbidden_open)
        rows, warnings = catalog.list_backup_files(catalog.get_backup_sources(case.manual))
    assert not warnings and len(rows) == 1


def test_infrastructure_verifier_rejects_unused_sort_guard(monkeypatch):
    spec = importlib.util.spec_from_file_location('backup_infra_mutation_check', ROOT / 'scripts/verify_infra_fixes.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    original = module.read
    def mutated_read(path):
        source = original(path)
        if path == ROOT / 'app/routes/backup.py':
            return source.replace('key=_backup_sort_key', "key=lambda item: item.get(sort_by) or ''")
        return source
    monkeypatch.setattr(module, 'read', mutated_read)
    assert module.main() == 1


def test_infrastructure_verifier_uses_current_route():
    spec = importlib.util.spec_from_file_location('backup_catalog_infra_check', ROOT / 'scripts/verify_infra_fixes.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.main() == 0
