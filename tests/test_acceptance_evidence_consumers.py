"""Actual isolated API/ORM consumers; no production evidence or business writes.

AI_FIX_TASK: AI-R18-F01-FIX-20261108-001
"""
from datetime import datetime, timedelta
import json
from types import SimpleNamespace

import pytest
import app as m
from ai.ops.launch_acceptance import ALL_ACCEPTANCE_METRICS


@pytest.fixture
def acceptance_client(monkeypatch):
    monkeypatch.setitem(m.app.config, 'TESTING', True)
    monkeypatch.setitem(m.app.config, 'WTF_CSRF_ENABLED', False)
    with m.app.app_context():
        assert str(m.db.engine.url) == 'sqlite:///:memory:'
        m.db.session.remove(); m.db.drop_all(); m.db.create_all()
        actor = m.User(username='synthetic-evidence-reviewer', role='admin',
            password_hash='!unusable-synthetic', must_change_password=False)
        m.db.session.add(actor); m.db.session.commit()
        client = m.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(actor.id); session['_fresh'] = True
        yield client, actor.id
        m.db.session.remove(); m.db.drop_all()


def test_unknown_queries_never_turn_into_measured_zero(acceptance_client, monkeypatch):
    class Crash:
        @property
        def query(self):
            raise RuntimeError('synthetic query failure')
    monkeypatch.setattr(m, 'AIToolCall', Crash())
    def missing(*args):
        raise RuntimeError('synthetic missing register')
    monkeypatch.setattr(m, '_ai_registered_duplicate_drafts', missing)
    for counts in (m._ai_r17_acceptance_counts(), m._ai_f02_query_daily_counts('2026-11-01')):
        assert counts['unauthorized_success'] is None
        assert counts['duplicate_drafts'] is None
        assert counts['auto_submit'] is None


def test_actual_day_role_coverage_does_not_invent_configured_roles(acceptance_client):
    _, actor = acceptance_client
    assert m._ai_f02_query_rollout_info('2026-11-01') == {'user_count': 0, 'role_count': 0, 'roles': ()}
    run = m.AIRun(user_id=actor, request_id='synthetic-role-evidence', request_hash='synthetic', endpoint='synthetic')
    m.db.session.add(run); m.db.session.flush()
    for role, allowed, at in [('warehouse', True, datetime(2026,11,1,12)),
        ('purchase', False, datetime(2026,11,1,13)), ('admin', True, datetime(2026,11,2))]:
        m.db.session.add(m.AIToolCall(ai_run_id=run.id, user_id=actor, role=role, tool_name='read',
            permission_allowed=allowed, status='completed', created_at=at))
    m.db.session.commit()
    assert m._ai_f02_query_rollout_info('2026-11-01') == {'user_count': 1, 'role_count': 1, 'roles': ('warehouse',)}


def test_real_orm_receipts_keep_replays_out_of_duplicate_metric(acceptance_client):
    _, actor = acceptance_client
    start = datetime(2026,11,1)
    for i, draft, status in [(1, 10, 'completed'), (2, 10, 'replayed'), (3, None, 'replayed')]:
        m.db.session.add(m.AIDraftIdempotency(user_id=actor, capability='in_order', idempotency_key=str(i),
            document_job_id=1, draft_type='in_order', draft_id=draft, status=status, created_at=start))
    m.db.session.commit()
    assert m._ai_f02_query_daily_counts('2026-11-01')['duplicate_drafts'] == 0
    m.db.session.add(m.AIDraftIdempotency(user_id=actor, capability='in_order', idempotency_key='extra',
        document_job_id=1, draft_type='in_order', draft_id=11, status='completed', created_at=start))
    m.db.session.commit()
    assert m._ai_f02_query_daily_counts('2026-11-01')['duplicate_drafts'] == 1
    assert m._ai_f02_query_daily_counts('2026-11-02')['duplicate_drafts'] == 0


@pytest.mark.parametrize('counts', [{}, {'duplicate_drafts': 0}, dict.fromkeys(ALL_ACCEPTANCE_METRICS, False)])
def test_saved_incomplete_snapshots_never_display_four_zero(acceptance_client, counts):
    client, _ = acceptance_client
    m.db.session.add(m.AIAcceptanceDailySnapshot(snapshot_date='2026-11-01', absolute_counts=json.dumps(counts),
        quality_metrics='{}', rollout_roles='[]', filter_applied='{}'))
    m.db.session.commit()
    response = client.get('/api/ai/acceptance/daily_snapshots')
    assert response.status_code == 200
    assert response.json['snapshots'][0]['all_absolute_zero'] is False


def test_empty_audit_collection_is_diagnostic_not_role_coverage(acceptance_client):
    client, _ = acceptance_client
    response = client.post('/api/ai/acceptance/daily_snapshot', json={'date':'2026-11-01'})
    assert response.status_code == 200
    assert response.json['snapshot']['rollout_roles'] == []
    assert response.json['snapshot']['filter_applied']['time_end_exclusive'] == '2026-11-02T00:00:00'
    assert m.InOrder.query.count() == m.OutOrder.query.count() == 0


def test_quality_query_failure_does_not_manufacture_seven_measures(acceptance_client, monkeypatch):
    def unavailable(*args, **kwargs):
        assert kwargs == {'strict': True}
        raise RuntimeError('synthetic unavailable quality records')
    monkeypatch.setattr(m, '_ai_bq_query_samples', unavailable)
    assert m._ai_f02_query_daily_quality('2026-11-01') == {}


def test_confirmed_low_confidence_does_not_count_as_unconfirmed(acceptance_client):
    _, actor = acceptance_client
    job = m.AIDocumentJob(user_id=actor, source='synthetic', status='draft_created', created_at=datetime(2026,11,1,12))
    m.db.session.add(job); m.db.session.flush()
    item = m.AIDocumentItem(job_id=job.id, line_no=1, confidence=.2, confirmation_status='corrected', created_at=datetime(2026,11,1,12))
    m.db.session.add(item); m.db.session.commit()
    assert m._ai_f02_query_daily_counts('2026-11-01')['low_confidence_unconfirmed'] == 0
    item.confirmation_status = 'pending'; m.db.session.commit()
    assert m._ai_f02_query_daily_counts('2026-11-01')['low_confidence_unconfirmed'] == 1
