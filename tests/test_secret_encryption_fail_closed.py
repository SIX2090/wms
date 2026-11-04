"""Synthetic secret values and an isolated DB; never read deployment credentials."""
import logging
from unittest.mock import patch

import pytest
import app as w
from cryptography.fernet import Fernet


@pytest.fixture
def settings_case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setitem(w.app.config, 'SECRET_KEY', 'synthetic-settings-test-key')
    definitions = {
        'audit_before': {'type': 'text', 'label': '前置普通设置'},
        'audit_secret_one': {'type': 'secret', 'label': '第一敏感配置'},
        'audit_secret_two': {'type': 'secret', 'label': '第二敏感配置'},
        'audit_after': {'type': 'text', 'label': '后置普通设置'},
    }
    monkeypatch.setattr(w, 'SYSTEM_SETTING_DEFINITIONS', definitions)
    with w.app.app_context():
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='synthetic-settings-admin', password_hash='unused-session-fixture',
                      role='admin', must_change_password=False)
        w.db.session.add(user)
        for key in definitions:
            value = w._secret_encrypt('synthetic-old-value') if 'secret' in key else 'old'
            w.db.session.add(w.SystemSetting(key=key, value=value))
        w.db.session.commit()
        uid = user.id
        before = {row.key: row.value for row in w.SystemSetting.query.all()}
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(uid)
        session['_fresh'] = True
    yield client, before
    with w.app.app_context():
        w.db.session.remove()
        w.db.drop_all()


@pytest.mark.parametrize('failure_stage', ['construction', 'encryption'])
def test_secret_encrypt_rejects_failure_without_logging_plaintext(settings_case, caplog, failure_stage):
    sample = 'synthetic-private-input'
    target = 'cryptography.fernet.Fernet' if failure_stage == 'construction' else 'cryptography.fernet.Fernet.encrypt'
    with w.app.app_context(), patch(target, side_effect=RuntimeError(sample)), caplog.at_level(logging.WARNING):
        with pytest.raises(RuntimeError, match='敏感配置加密失败') as raised:
            w._secret_encrypt(sample)
    assert sample not in str(raised.value)
    assert sample not in caplog.text


def test_secret_encrypt_rejects_missing_server_key(settings_case, monkeypatch):
    monkeypatch.setitem(w.app.config, 'SECRET_KEY', '')
    with w.app.app_context(), pytest.raises(RuntimeError, match='敏感配置加密失败'):
        w._secret_encrypt('synthetic-private-input')


@pytest.mark.parametrize('failed_call', [1, 2])
def test_save_encryption_failure_rolls_back_entire_form(settings_case, caplog, failed_call):
    client, before = settings_case
    original = Fernet.encrypt
    calls = []

    def encrypt(instance, value):
        calls.append(value)
        if len(calls) == failed_call:
            raise RuntimeError('synthetic-private-input')
        return original(instance, value)

    with patch.object(Fernet, 'encrypt', encrypt), caplog.at_level(logging.WARNING):
        response = client.post('/system_settings/save', data={
            'audit_before': 'changed-before', 'audit_after': 'changed-after',
            'audit_secret_one': 'synthetic-private-input',
            'audit_secret_two': 'synthetic-second-input',
        })
    assert response.status_code == 503
    assert response.json['status'] == 'error'
    assert '加密失败' in response.json['msg'] and '未保存' in response.json['msg']
    assert 'synthetic-private-input' not in response.get_data(as_text=True)
    assert 'synthetic-private-input' not in caplog.text
    with w.app.app_context():
        assert {row.key: row.value for row in w.SystemSetting.query.all()} == before
        assert w.OperationAudit.query.filter_by(operation='保存系统设置').count() == 0


def test_save_normal_encryption_and_blank_secret_preservation(settings_case):
    client, before = settings_case
    response = client.post('/system_settings/save', data={
        'audit_before': 'new', 'audit_after': 'new',
        'audit_secret_one': 'synthetic-new-value', 'audit_secret_two': '',
    })
    assert response.status_code == 200 and response.json['status'] == 'success'
    with w.app.app_context():
        rows = {row.key: row.value for row in w.SystemSetting.query.all()}
        assert rows['audit_before'] == rows['audit_after'] == 'new'
        assert rows['audit_secret_one'].startswith('enc:')
        assert w._secret_decrypt(rows['audit_secret_one']) == 'synthetic-new-value'
        assert rows['audit_secret_two'] == before['audit_secret_two']


def test_save_still_requires_session_csrf(settings_case, monkeypatch):
    client, before = settings_case
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    with patch.object(Fernet, 'encrypt') as encrypt:
        response = client.post('/system_settings/save', data={'audit_secret_one': 'synthetic-new-value'},
                               headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 400
    encrypt.assert_not_called()
    with w.app.app_context():
        assert {row.key: row.value for row in w.SystemSetting.query.all()} == before
