"""Approved media policy: real identities/settings, synthetic providers only."""
from datetime import datetime, timedelta
from io import BytesIO

from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

import pytest
from flask import g
import app as w
from routes import mobile


@pytest.fixture
def media_scene(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.INFO, logger=w.app.logger.name)
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.drop_all()
        w.db.create_all()
        def fresh_request():
            g.pop('_login_user', None)
            g.pop('csrf_valid', None)
        hooks = dict(w.app.before_request_funcs)
        hooks[None] = [fresh_request, *hooks.get(None, [])]
        monkeypatch.setattr(w.app, 'before_request_funcs', hooks)
        users = {}
        for role in ('admin', 'warehouse', 'purchase', 'sales', 'production', 'viewer', 'user'):
            user = w.User(username='synthetic-media-' + role, role=role,
                          password_hash='not-a-real-credential', must_change_password=False)
            w.db.session.add(user)
            w.db.session.flush()
            w.db.session.add(w.ApiToken(token='synthetic-media-' + role, user_id=user.id,
                expires_at=datetime.now() + timedelta(hours=1), revoked=False))
            users[role] = user.id
        for key, value in {'ai_feature_global_enabled': '1', 'ai_feature_rollout_mode': 'all',
                           'ai_llm_enabled': '1', 'ai_llm_vision_enabled': '1',
                           'ai_llm_api_key': 'synthetic-provider-never-sent'}.items():
            w.set_system_setting(key, value)
        w.db.session.commit()
        calls = []
        def vision(*args, **kwargs):
            calls.append('vision')
            return '合成识物候选', {'name': '合成物料'}, None
        def fallback(*args, **kwargs):
            calls.append('fallback')
            return '查库存', None
        def tencent(*args, **kwargs):
            calls.append('tencent')
            return '查库存'
        import tencent_asr
        monkeypatch.setattr(w, '_ai_call_llm_vision', vision)
        monkeypatch.setattr(w, '_asr_call_tokenhub', fallback)
        def retry_extract(*args, **kwargs):
            calls.append('job')
            return None
        monkeypatch.setattr(w, '_ai_call_llm_document_extract', retry_extract)
        monkeypatch.setattr(tencent_asr, 'sentence_recognition', tencent)
        # Clear the real limiter's state, rather than replacing its decision.
        for name in ('_recognize_rate', '_recognize_rate_hits', '_recognize_hits'):
            value = getattr(mobile, name, None)
            if isinstance(value, dict):
                monkeypatch.setattr(mobile, name, type(value)())
        monkeypatch.delenv('TENCENTCLOUD_SECRET_ID', raising=False)
        monkeypatch.delenv('TENCENTCLOUD_SECRET_KEY', raising=False)
        yield users, calls, caplog
        w.db.session.remove()


def _post(scene, kind, role='warehouse', channel='bearer', *, valid_csrf=True, bearer_role=None, empty=False, job_owner=None):
    users, _, _ = scene
    client = w.app.test_client()
    headers = {}
    if channel == 'session':
        with client.session_transaction() as session:
            session['_user_id'], session['_fresh'] = str(users[role]), True
        # Obtain a real Flask-WTF signed token from a request bound to this session.
        with client.session_transaction() as session:
            session['csrf_token'] = 'synthetic-csrf-value'
        from itsdangerous import URLSafeTimedSerializer
        token = URLSafeTimedSerializer(w.app.secret_key, salt='wtf-csrf-token').dumps('synthetic-csrf-value')
        if valid_csrf:
            headers['X-CSRFToken'] = token
    if channel == 'bearer' or bearer_role is not None:
        headers['Authorization'] = 'Bearer synthetic-media-' + (bearer_role or role)
    if kind == 'tencent':
        import os
        os.environ['TENCENTCLOUD_SECRET_ID'] = 'synthetic-id'
        os.environ['TENCENTCLOUD_SECRET_KEY'] = 'synthetic-key'
    key, name = ('image', 'synthetic.png') if kind in ('vision', 'ocr', 'excel') else ('audio', 'synthetic.wav')
    endpoint = {'vision': '/mobile/api/recognize_material', 'ocr': '/api/ai/document_ocr',
                'excel': '/api/ai/document_ocr_excel'}.get(kind, '/mobile/api/asr')
    if kind == 'job':
        job = w.AIDocumentJob(user_id=users[job_owner or role], source='text', document_type='in_order',
                              status='failed', source_text_summary='合成可重试文本')
        w.db.session.add(job)
        w.db.session.commit()
        endpoint = f'/ai/document_jobs/{job.id}/retry'
    data = {key: (BytesIO(b'' if empty else b'RIFF-synthetic-upload'), name)}
    return client.post(endpoint, data=data, headers=headers)


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
@pytest.mark.parametrize('channel', ['bearer', 'session'])
@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'sales', 'production', 'viewer', 'user'])
def test_media_role_and_actor_policy(media_scene, kind, channel, role):
    response = _post(media_scene, kind, role, channel)
    allowed = role not in ('viewer', 'user')
    assert response.status_code == (200 if allowed else 403), response.get_json()
    assert media_scene[1] == ([kind] if allowed else [])
    if allowed:
        audits = [record for record in media_scene[2].records if hasattr(record, 'ai_capability')]
        assert len(audits) == 1
        assert audits[0].ai_user_id == media_scene[0][role] and audits[0].ai_role == role
        assert audits[0].ai_capability == ('material_recognition' if kind == 'vision' else 'audio_transcription')
        assert w.OperationLog.query.count() == 0, 'Provider attempts must not add business DB rows'
    else:
        audit = w.AIRolloutAudit.query.one()
        assert audit.user_id == media_scene[0][role] and audit.role == role
    assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
@pytest.mark.parametrize('role', ['admin', 'warehouse'])
def test_global_disabled_prevents_every_provider(media_scene, kind, role):
    w.set_system_setting('ai_feature_global_enabled', '0')
    w.db.session.commit()
    assert _post(media_scene, kind, role).status_code == 403
    assert media_scene[1] == []
    audit = w.AIRolloutAudit.query.one()
    assert audit.user_id == media_scene[0][role] and audit.stage == 'global'


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
def test_failed_invocation_audit_stops_provider(media_scene, monkeypatch, kind):
    original = w.app.logger.info
    def refuse_audit(message, *args, **kwargs):
        if message.startswith('AI媒体调用'):
            raise RuntimeError('synthetic audit failure')
        return original(message, *args, **kwargs)
    monkeypatch.setattr(w.app.logger, 'info', refuse_audit)
    assert _post(media_scene, kind).status_code == 503
    assert media_scene[1] == []


@pytest.mark.parametrize('kind', ['vision', 'ocr', 'excel'])
@pytest.mark.parametrize('channel', ['session', 'bearer'])
def test_existing_vision_feature_switch_prevents_provider(media_scene, kind, channel):
    w.set_system_setting('ai_feature_vision_enabled', '0')
    w.db.session.commit()
    assert _post(media_scene, kind, channel=channel).status_code == 400
    assert media_scene[1] == []


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'sales', 'production', 'viewer', 'user'])
def test_saved_document_retry_obeys_existing_paid_ai_roles(media_scene, role):
    response = _post(media_scene, 'job', role, 'session')
    allowed = role not in ('viewer', 'user')
    assert response.status_code == (302 if allowed else 403), response.get_json()
    assert media_scene[1] == (['job'] if allowed else [])
    if allowed:
        audits = [record for record in media_scene[2].records if hasattr(record, 'ai_capability')]
        assert len(audits) == 1
        assert audits[0].ai_user_id == media_scene[0][role] and audits[0].ai_capability == 'document_retry'
        assert w.OperationLog.query.count() == 0
    assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('role,expected', [('warehouse', 404), ('admin', 302)])
def test_saved_document_retry_preserves_original_owner_boundary(media_scene, role, expected):
    response = _post(media_scene, 'job', role, 'session', job_owner='purchase')
    assert response.status_code == expected
    assert media_scene[1] == (['job'] if role == 'admin' else [])


def test_denial_rolls_back_pending_review_before_audit_commit(media_scene):
    w.set_system_setting('ai_feature_global_enabled', '0')
    w.db.session.commit()
    pending = w.AIDocumentJob(user_id=media_scene[0]['warehouse'], source='text',
                             document_type='in_order', status='processing')
    w.db.session.add(pending)
    w.db.session.flush()
    denied = _post(media_scene, 'ocr', channel='session')
    assert denied.status_code == 403
    assert w.AIDocumentJob.query.count() == 0
    assert w.AIRolloutAudit.query.one().user_id == media_scene[0]['warehouse']
    assert w.OperationLog.query.count() == 0 and media_scene[1] == []


@pytest.mark.parametrize('role', ['admin', 'warehouse'])
@pytest.mark.parametrize('global_enabled,mode,expected', [('0', 'all', 403), ('1', 'off', 403), ('1', 'allowlist', 403)])
def test_saved_document_retry_rechecks_switches_and_rollout(media_scene, role, global_enabled, mode, expected):
    w.set_system_setting('ai_feature_global_enabled', global_enabled)
    w.set_system_setting('ai_feature_rollout_mode', mode)
    w.db.session.commit()
    response = _post(media_scene, 'job', role, 'session')
    # Keep the rollout evaluator's existing admin exception; global off still denies.
    effective = 302 if role == 'admin' and global_enabled == '1' else expected
    assert response.status_code == effective
    assert media_scene[1] == (['job'] if effective == 302 else [])


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
@pytest.mark.parametrize('mode,listed,expected', [('off', False, 403), ('allowlist', False, 403),
    ('allowlist', True, 200), ('role', False, 200)])
def test_rollout_uses_actual_bearer_identity(media_scene, kind, mode, listed, expected):
    w.set_system_setting('ai_feature_rollout_mode', mode)
    w.set_system_setting('ai_feature_allowed_user_ids', str(media_scene[0]['warehouse']) if listed else '')
    w.db.session.commit()
    assert _post(media_scene, kind).status_code == expected
    assert media_scene[1] == ([kind] if expected == 200 else [])


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
def test_session_precedence_and_csrf(media_scene, kind):
    assert _post(media_scene, kind, 'viewer', 'session', bearer_role='admin').status_code == 403
    assert _post(media_scene, kind, 'admin', 'session', valid_csrf=False, bearer_role='admin').status_code == 400
    assert media_scene[1] == []


@pytest.mark.parametrize('kind', ['vision', 'fallback'])
def test_missing_identity_and_empty_upload_never_call_provider(media_scene, kind):
    assert _post(media_scene, kind, channel='none').status_code == 401
    assert _post(media_scene, kind, role='invalid').status_code == 401
    assert _post(media_scene, kind, empty=True).status_code == 400
    assert media_scene[1] == []


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
def test_existing_limiter_preserves_actor_scope(media_scene, kind):
    for _ in range(5):
        assert _post(media_scene, kind).status_code == 200
    assert _post(media_scene, kind).status_code == (429 if kind == 'vision' else 200)
    assert len(media_scene[1]) == (5 if kind == 'vision' else 6)
    assert _post(media_scene, kind, role='purchase').status_code == 200


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
def test_provider_error_can_retry_without_stock_effect(media_scene, monkeypatch, kind):
    if kind == 'vision':
        original = w._ai_call_llm_vision
        monkeypatch.setattr(w, '_ai_call_llm_vision', lambda *a, **k: (None, None, '合成提供方失败'))
        expected = 500
    elif kind == 'fallback':
        original = w._asr_call_tokenhub
        monkeypatch.setattr(w, '_asr_call_tokenhub', lambda *a, **k: (None, '合成提供方失败'))
        expected = 502
    else:
        import tencent_asr
        original = tencent_asr.sentence_recognition
        def fail(*args, **kwargs):
            raise tencent_asr.TencentAsrError('合成失败')
        monkeypatch.setattr(tencent_asr, 'sentence_recognition', fail)
        expected = 502
    assert _post(media_scene, kind).status_code == expected
    if kind == 'vision':
        monkeypatch.setattr(w, '_ai_call_llm_vision', original)
    elif kind == 'fallback':
        monkeypatch.setattr(w, '_asr_call_tokenhub', original)
    else:
        monkeypatch.setattr(tencent_asr, 'sentence_recognition', original)
    assert _post(media_scene, kind).status_code == 200
    assert w.StockTransaction.query.count() == 0


@pytest.mark.parametrize('kind', ['vision', 'fallback', 'tencent'])
def test_changed_global_during_upload_is_rechecked(media_scene, monkeypatch, kind):
    from werkzeug.datastructures import FileStorage
    def changed_read(self, *args, **kwargs):
        w.set_system_setting('ai_feature_global_enabled', '0')
        w.db.session.commit()
        return self.stream.read(*args, **kwargs)
    monkeypatch.setattr(FileStorage, 'read', changed_read, raising=False)
    assert _post(media_scene, kind).status_code == 403
    assert media_scene[1] == []


@pytest.mark.parametrize('kind', ['ocr', 'excel'])
@pytest.mark.parametrize('channel', ['bearer', 'session'])
@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase'])
def test_ocr_same_root_global_gate_keeps_existing_roles(media_scene, kind, channel, role):
    w.set_system_setting('ai_feature_global_enabled', '0')
    w.db.session.commit()
    assert _post(media_scene, kind, role, channel).status_code == 403
    assert media_scene[1] == []
    assert w.AIRolloutAudit.query.one().user_id == media_scene[0][role]


@pytest.mark.parametrize('kind', ['ocr', 'excel'])
def test_ocr_retry_boundary_rechecks_policy_before_every_attempt(media_scene, monkeypatch, kind):
    from types import SimpleNamespace
    import ai.documents.image_preprocessing as preprocessing
    monkeypatch.setattr(preprocessing, 'preprocess_image', lambda *a, **k: SimpleNamespace(
        is_usable=True, processed_bytes=b'synthetic-processed-image', processed_mime='image/png',
        metrics=None, to_dict=lambda: {}))
    def fail_and_disable(*args, **kwargs):
        media_scene[1].append('vision')
        w.set_system_setting('ai_feature_global_enabled', '0')
        w.db.session.commit()
        return None, None, 'synthetic 503 unavailable'
    monkeypatch.setattr(w, '_ai_call_llm_vision', fail_and_disable)
    response = _post(media_scene, kind)
    if kind == 'ocr':
        assert response.status_code == 403, response.get_json()
    else:
        assert response.status_code == 500, response.get_json()
    assert media_scene[1] == ['vision'], 'Retry/fallback must not call a disabled provider again'
