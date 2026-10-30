"""BUG-2026-10-30-002: real transactions, snapshot drift and recoverable initialization."""
import json
import sqlite3

import pytest
from sqlalchemy import create_engine
from werkzeug.security import generate_password_hash

import app as wms
from db import db
from services import business_initialization as safety


@pytest.fixture
def case(monkeypatch, tmp_path):
    monkeypatch.setenv('WMS_ALLOW_BUSINESS_INIT', '1')
    monkeypatch.setenv('WMS_BACKUP_DIR', str(tmp_path / 'backups'))
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        user = wms.User(username='init-test', role='admin', must_change_password=False,
                        password_hash=generate_password_hash('isolated-fixture'))
        db.session.add(user)
        db.session.add(wms.Material(code='INIT-QA', name='初始化隔离样本', stock=7))
        db.session.flush()
        db.session.add(wms.StockTransaction(material_id=1, warehouse_id=4, quantity=7,
                                            transaction_type='in', reference_type='test', reference_id=1))
        db.session.add(wms.OperationLog(user_id=user.id, operation_type='测试', operation_content='完整备份中的日志'))
        db.session.add(wms.OperationAudit(user_id=user.id, username=user.username, operation='history', status='success'))
        wms.ensure_default_system_settings()
        db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
        yield client, tmp_path
        db.session.remove()


def preview(client, master=False):
    response = client.get('/system_settings/init_business_data/preview')
    assert response.status_code == 200, response.json
    return response.json['preview_tokens'][str(int(master))]


def execute(client, token, master=False):
    return client.post('/system_settings/init_business_data/execute', data={
        'admin_password': 'isolated-fixture', 'confirm_phrase': wms.INIT_CONFIRM_PHRASE,
        'include_master_data': str(int(master)), 'preview_token': token})


def assert_original():
    assert wms.Material.query.one().stock == 7
    assert wms.StockTransaction.query.one().quantity == 7
    assert wms.OperationLog.query.count() == 1


def test_initialization_enabled(case, monkeypatch):
    client, _ = case
    token = preview(client)
    monkeypatch.delenv('WMS_ALLOW_BUSINESS_INIT')
    assert execute(client, token).status_code == 403
    assert_original()
    assert 'id="openInitModalBtn" disabled' in client.get('/system_settings').text


@pytest.mark.parametrize('change', ['add', 'edit', 'replace'])
def test_preview_rejects_changed_rows_even_when_counts_are_identical(case, change):
    client, _ = case
    token = preview(client)
    if change == 'add':
        db.session.add(wms.Material(code='NEW-QA', name='新增测试', stock=0))
    elif change == 'edit':
        wms.Material.query.one().name = '同条数但内容已变'
    else:
        wms.OperationLog.query.delete()
        db.session.add(wms.OperationLog(user_id=1, operation_type='替换', operation_content='同条数新记录'))
    db.session.commit()
    response = execute(client, token)
    assert response.status_code == 409
    assert '数据已变化' in response.json['msg']
    assert wms.Material.query.filter_by(code='INIT-QA').one().stock == 7
    assert wms.StockTransaction.query.count() == 1


def test_prepare_preview(case):
    client, _ = case
    assert execute(client, preview(client, False), True).status_code == 409
    assert_original()


def test_unsigned_missing_and_expired_tokens_cannot_initialize(case, monkeypatch):
    client, _ = case
    for token in ('', 'forged'):
        assert execute(client, token).status_code == 409
        assert_original()
    import itsdangerous.timed
    original = itsdangerous.timed.TimestampSigner.get_timestamp
    monkeypatch.setattr(itsdangerous.timed.TimestampSigner, 'get_timestamp', lambda self: original(self) - 301)
    token = preview(client)
    monkeypatch.setattr(itsdangerous.timed.TimestampSigner, 'get_timestamp', original)
    assert execute(client, token).status_code == 409
    assert_original()


def test_token_is_bound_to_user_and_database(case):
    client, _ = case
    token = preview(client)
    with pytest.raises(safety.InitializationRefused):
        safety.execute_initialization(token, False, 999, 'other')
    original = safety._database_identity()
    assert len(original) == 64
    assert_original()


def test_backup_failure_aborts_before_any_deletion(case, monkeypatch):
    client, _ = case
    token = preview(client)
    def denied(nonce):
        raise OSError('isolated backup directory denied')
    monkeypatch.setattr(safety, '_create_verified_backup', denied)
    assert execute(client, token).status_code == 503
    assert_original()


def test_late_cleanup_failure_rolls_back_inventory_materials_and_logs(case, monkeypatch):
    client, _ = case
    token = preview(client)
    original = wms._bulk_delete_model_required
    def late_failure(model, label):
        if model is wms.OperationLog:
            raise RuntimeError('isolated late cleanup failure')
        return original(model, label)
    monkeypatch.setattr(wms, '_bulk_delete_model_required', late_failure)
    assert execute(client, token).status_code == 503
    assert_original()
    assert not wms.OperationAudit.query.filter_by(operation='init_business_data_done').first()


def test_cleanup_helper_cannot_commit_behind_orchestrators_back(case):
    wms._init_business_data_keep_users_and_settings(include_master_data=False)
    assert wms.Material.query.one().stock == 0
    assert wms.StockTransaction.query.count() == 0
    db.session.rollback()
    assert_original()


def test_audit_write_failure_rolls_back_the_entire_clear(case):
    from sqlalchemy import event
    client, _ = case
    token = preview(client)
    def refuse(mapper, connection, target):
        raise RuntimeError('isolated audit write failure')
    event.listen(wms.OperationAudit, 'before_insert', refuse)
    try:
        assert execute(client, token).status_code == 503
    finally:
        event.remove(wms.OperationAudit, 'before_insert', refuse)
    assert_original()
    assert wms.OperationAudit.query.filter_by(operation='history').count() == 1


def test_default_settings_failure_rolls_back_the_entire_clear(case, monkeypatch):
    client, _ = case
    token = preview(client)
    class BrokenDefaults(dict):
        def items(self):
            raise RuntimeError('isolated default settings failure')
    monkeypatch.setattr(wms, 'SYSTEM_SETTING_DEFINITIONS', BrokenDefaults())
    assert execute(client, token).status_code == 503
    assert_original()


def test_preview_query_failure_never_issues_a_token(case, monkeypatch):
    client, _ = case
    monkeypatch.setattr(wms, '_init_business_data_preview_stats',
                        lambda: {'business': [{'label': 'failed', 'count': 0, 'error': 'fixture'}]})
    response = client.get('/system_settings/init_business_data/preview')
    assert response.status_code == 503
    assert 'preview_tokens' not in response.json
    assert_original()


@pytest.mark.parametrize('master', [False, True])
def test_execute_initialization(case, master):
    client, _ = case
    token = preview(client, master)
    response = execute(client, token, master)
    assert response.status_code == 200, response.json
    with sqlite3.connect(response.json['backup']) as backup:
        assert backup.execute('pragma integrity_check').fetchall() == [('ok',)]
        assert backup.execute('select stock from material').fetchone() == (7,)
        assert backup.execute('select quantity from stock_transaction').fetchone() == (7,)
        assert backup.execute('select count(*) from operation_log').fetchone() == (1,)
        assert backup.execute('select count(*) from operation_audit').fetchone() == (1,)
    assert wms.Material.query.count() == (0 if master else 1)
    if not master:
        assert wms.Material.query.one().stock == 0
    assert wms.StockTransaction.query.count() == 0
    assert wms.OperationLog.query.count() == 0
    assert wms.User.query.one().username == 'init-test'
    assert wms.OperationAudit.query.filter_by(operation='history').count() == 1
    done = wms.OperationAudit.query.filter_by(operation='init_business_data_done').one()
    assert json.loads(done.new_data)['backup'] == response.json['backup']
    assert wms.SystemSetting.query.count() == len(wms.SYSTEM_SETTING_DEFINITIONS)
    assert execute(client, token, master).status_code == 409


def test_file_database_backup_holds_write_lock_and_does_not_touch_another_database(case, monkeypatch):
    client, folder = case
    db.session.remove()
    engine = create_engine('sqlite:///' + str(folder / 'isolated.db'))
    monkeypatch.setitem(db.engines, None, engine)
    db.create_all()
    # Use only a disposable file database; no source or target defaults are consulted.
    db.session.add(wms.User(id=1, username='file-fixture', role='admin', password_hash='unused-fixture'))
    db.session.add(wms.Material(code='FILE-QA', name='file', stock=3))
    db.session.commit()
    original = safety._create_verified_backup
    def verify_lock(nonce):
        other = sqlite3.connect(folder / 'isolated.db', timeout=0.05)
        try:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                other.execute("INSERT INTO material (code,name,stock) VALUES ('RACE','race',4)")
        finally:
            other.close()
        return original(nonce)
    monkeypatch.setattr(safety, '_create_verified_backup', verify_lock)
    try:
        stats, tokens = safety.prepare_preview(1)
        assert stats['user_count'] == 1
        with monkeypatch.context() as patch:
            from pathlib import Path
            patch.setattr(wms, 'create_sqlite_online_backup',
                          lambda source, target: Path(target).write_bytes(b'corrupt fixture'))
            with pytest.raises(sqlite3.DatabaseError):
                safety.execute_initialization(tokens['0'], False, 1, 'file-fixture')
        assert wms.Material.query.one().stock == 3
        assert wms.OperationAudit.query.count() == 0
        # A failed attempt retains its artifact; a new preview issues a fresh recovery name.
        _, tokens = safety.prepare_preview(1)
        result, backup = safety.execute_initialization(tokens['0'], False, 1, 'file-fixture')
        assert result['zeroed_materials'] == 1
        with sqlite3.connect(backup) as saved:
            assert saved.execute('select stock from material').fetchone() == (3,)
    finally:
        db.session.remove()
        engine.dispose()
