# -*- coding: utf-8 -*-
"""R1: real SQLite/session interleavings for print state transitions.

Run only through the repository's approved synthetic isolation launcher.
The interleavings require SQLite's current legacy SELECT transaction behavior;
they never commit session A merely to manufacture a stale snapshot.
"""
from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

from datetime import datetime, timedelta

import pytest
from flask import g
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.orm import Query, Session

import app as w
from routes import print_alerts as alerts
from routes import print_queue as queue


class _BoundSession:
    """Expose an independent real Session through Flask-SQLAlchemy's call shape."""
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session

    def __getattr__(self, name):
        return getattr(self.session, name)


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    # Keep each request's real session user independent from the outer context.
    def fresh_user():
        g.pop('_login_user', None)
    hooks = dict(w.app.before_request_funcs)
    hooks[None] = [fresh_user, *hooks.get(None, [])]
    monkeypatch.setattr(w.app, 'before_request_funcs', hooks)
    observed_alerts = []
    monkeypatch.setattr(alerts, 'notify_print_failed', lambda job: observed_alerts.append(
        (job.id, job.status, job.error_msg, job.attempts)))
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username='synthetic-print-cas', role='warehouse',
                      password_hash='synthetic-not-a-login-password',
                      must_change_password=False)
        station = w.PrintWorkstation(code='CAS-SYNTHETIC', name='合成打印站',
            device_id='cas-synthetic-device', auth_token='cas-synthetic-workstation-token',
            enabled=True, status='online', last_heartbeat=datetime.now())
        w.db.session.add_all([user, station])
        w.db.session.commit()
        client = w.app.test_client()
        raw_csrf = 'synthetic-print-cas-csrf'
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id)
            session['_fresh'] = True
            session['csrf_token'] = raw_csrf
        csrf_key = w.app.config.get('WTF_CSRF_SECRET_KEY') or w.app.secret_key
        csrf = URLSafeTimedSerializer(csrf_key, salt='wtf-csrf-token').dumps(raw_csrf)
        yield client, station.id, csrf, observed_alerts
        w.db.session.remove()


def _job(station_id=None, **overrides):
    now = datetime.now()
    values = dict(job_type='label', target_ids='1', status='printing', attempts=1,
                  workstation_id=station_id, lease_token='synthetic-old-lease',
                  printing_started_at=now - timedelta(minutes=7),
                  created_at=now - timedelta(minutes=30), source_event='scan_submit_out')
    values.update(overrides)
    job = w.PrintJob(**values)
    w.db.session.add(job)
    w.db.session.commit()
    # Load the snapshot now, before session B changes the database.
    assert job.id > 0
    return job


def _other_session(action):
    """B commits real SQL while A holds a genuine legacy SELECT-only snapshot."""
    current = w.db.session()
    assert not current.new and not current.dirty and not current.deleted
    driver = current.connection().connection.driver_connection
    assert driver.in_transaction is False, (
        'This interleaving requires the deployed SQLite legacy SELECT behavior; '
        'an explicit read transaction needs a separate concurrency fixture.')
    with Session(bind=w.db.engine) as other:
        assert other is not current
        result = action(other)
        other.commit()
        return result


def _write_other(job_id, **values):
    def change(other):
        assert other.query(w.PrintJob).filter_by(id=job_id).update(
            values, synchronize_session=False) == 1
    _other_session(change)


def _read(job_id):
    w.db.session.expire_all()
    return w.db.session.get(w.PrintJob, job_id)


def _after_job_list(monkeypatch, action):
    original = Query.all
    fired = []
    def all_with_interleaving(query):
        rows = original(query)
        entity = query.column_descriptions[0].get('entity')
        if not fired and entity is w.PrintJob and rows:
            fired.append(True)
            action(rows)
        return rows
    monkeypatch.setattr(Query, 'all', all_with_interleaving)
    return fired


@pytest.mark.parametrize('attempts', [1, queue.MAX_ATTEMPTS])
def test_recovery_does_not_revive_completed_snapshot(case, monkeypatch, attempts):
    job = _job(attempts=attempts)
    job_id = job.id
    done_at = datetime.now()
    fired = _after_job_list(monkeypatch, lambda rows: _write_other(
        job_id, status='done', printed_at=done_at))
    assert queue._recover_zombie_printing_jobs() == 0
    assert fired == [True]
    current = _read(job_id)
    assert current.status == 'done' and current.printed_at == done_at
    assert case[3] == []


@pytest.mark.parametrize('changed', ['lease', 'started'])
def test_recovery_checks_both_old_lease_and_started_at(case, monkeypatch, changed):
    job = _job()
    job_id = job.id
    new_start = datetime.now()
    values = {'lease_token': 'synthetic-replacement'} if changed == 'lease' else {
        'printing_started_at': new_start}
    fired = _after_job_list(monkeypatch, lambda rows: _write_other(job_id, **values))
    assert queue._recover_zombie_printing_jobs() == 0
    assert fired == [True]
    current = _read(job_id)
    assert current.status == 'printing'
    assert all(getattr(current, key) == value for key, value in values.items())
    assert case[3] == []


@pytest.mark.parametrize('attempts', [1, queue.MAX_ATTEMPTS])
def test_two_recoverers_count_and_alert_only_actual_transition(case, monkeypatch, attempts):
    job = _job(attempts=attempts)
    job_id = job.id
    inner = []
    original = w.db.session
    def recover_in_b(rows):
        def action(other):
            # The same real helper runs with B's independent SQLAlchemy session.
            with monkeypatch.context() as patch:
                patch.setattr(w.db, 'session', _BoundSession(other))
                inner.append(queue._recover_zombie_printing_jobs())
        _other_session(action)
        assert w.db.session is original
    fired = _after_job_list(monkeypatch, recover_in_b)
    outer = queue._recover_zombie_printing_jobs()
    assert fired == [True] and inner == [1] and outer == 0
    current = _read(job_id)
    expected = 'failed' if attempts == queue.MAX_ATTEMPTS else 'pending'
    assert current.status == expected
    assert len(case[3]) == (1 if expected == 'failed' else 0)
    if expected == 'failed':
        assert case[3][0] == (job_id, 'failed', '打印超时且尝试次数过多', attempts)


@pytest.mark.parametrize('started,created,attempts,expected,count', [
    (-1, -30, 1, 'printing', 0),
    (-7, -30, 1, 'pending', 1),
    (-7, -30, queue.MAX_ATTEMPTS, 'failed', 1),
    (None, -30, 1, 'pending', 1),
    (None, -1, 1, 'printing', 0),
])
def test_recovery_preserves_timeout_and_legacy_null_rules(
        case, started, created, attempts, expected, count):
    now = datetime.now()
    job = _job(attempts=attempts,
        printing_started_at=None if started is None else now + timedelta(minutes=started),
        created_at=now + timedelta(minutes=created))
    job_id = job.id
    assert queue._recover_zombie_printing_jobs() == count
    current = _read(job_id)
    assert current.status == expected and current.attempts == attempts
    if expected == 'pending':
        assert current.lease_token is None and current.printing_started_at is None
    assert len(case[3]) == (1 if expected == 'failed' else 0)


@pytest.mark.parametrize('ok', [True, False])
@pytest.mark.parametrize('changed', ['lease', 'started', 'done'])
def test_mark_job_printed_rejects_stale_snapshot(case, ok, changed):
    job = _job()
    job_id = job.id
    values = {'lease_token': 'synthetic-new-lease'} if changed == 'lease' else (
        {'printing_started_at': datetime.now()} if changed == 'started' else {'status': 'done'})
    _write_other(job_id, **values)
    saved = queue.mark_job_printed(job, ok, 'synthetic-old-result')
    current = _read(job_id)
    assert all(getattr(current, key) == value for key, value in values.items())
    assert current.error_msg != 'synthetic-old-result'
    assert case[3] == []
    assert saved is False


@pytest.mark.parametrize('channel', ['desktop', 'v1'])
@pytest.mark.parametrize('outcome', ['complete', 'fail'])
def test_result_validation_then_reclaim_cannot_overwrite_new_lease(
        case, monkeypatch, channel, outcome):
    client, station_id, csrf, seen = case
    job = _job(station_id if channel == 'v1' else None)
    job_id = job.id
    old_lease = job.lease_token
    second_client = w.app.test_client()
    with client.session_transaction() as session:
        user_id = session['_user_id']
    with second_client.session_transaction() as session:
        session['_user_id'] = user_id
        session['_fresh'] = True
    original = queue._claim_result_matches
    fired = []
    next_claim = []
    def validate_then_reclaim(snapshot, lease):
        accepted = original(snapshot, lease)
        if accepted and not fired:
            fired.append(True)
            first_session = w.db.session()
            driver = first_session.connection().connection.driver_connection
            assert not first_session.new and not first_session.dirty
            assert driver.in_transaction is False, 'Expected the deployed legacy SQLite SELECT window'
            # A second real request owns a separate app-context scoped session.
            with w.app.app_context():
                assert w.db.session() is not first_session
                if channel == 'v1':
                    response = second_client.post('/print_queue/api/v1/claim', json={}, headers={
                        'Authorization': 'Bearer cas-synthetic-workstation-token'})
                else:
                    response = second_client.get('/print_queue/next')
                assert response.status_code == 200, response.get_data(as_text=True)
                body = response.get_json()
                assert body['status'] == 'success' and body['job']['id'] == job_id
                replacement = w.db.session.get(w.PrintJob, job_id)
                next_claim.append((body['job']['lease_token'], replacement.printing_started_at))
        return accepted
    monkeypatch.setattr(queue, '_claim_result_matches', validate_then_reclaim)
    prefix = '/print_queue/api/v1' if channel == 'v1' else '/print_queue'
    headers = {'Authorization': 'Bearer cas-synthetic-workstation-token'} if channel == 'v1' else {
        'X-CSRFToken': csrf}
    response = client.post(f'{prefix}/jobs/{job_id}/{outcome}',
                           json={'lease_token': old_lease, 'error_msg': 'stale result'}, headers=headers)
    assert fired == [True] and len(next_claim) == 1
    assert response.status_code == 409, response.get_data(as_text=True)
    assert response.get_json()['msg'] == '任务已重新认领或租约失效'
    current = _read(job_id)
    assert current.status == 'printing'
    assert (current.lease_token, current.printing_started_at) == next_claim[0]
    assert current.attempts == 2 and current.error_msg != 'stale result'
    assert seen == []


@pytest.mark.parametrize('change', ['claim', 'manual', 'recent'])
def test_health_cancellation_rechecks_current_conditions(case, monkeypatch, change):
    job = _job(status='pending', lease_token=None, printing_started_at=None)
    job_id = job.id
    values = {'status': 'printing', 'lease_token': 'synthetic-claimed',
              'printing_started_at': datetime.now()} if change == 'claim' else (
              {'source_event': 'manual'} if change == 'manual' else {'created_at': datetime.now()})
    monkeypatch.setattr(queue, 'auto_print_on_submit_enabled', lambda: False)
    monkeypatch.setattr(alerts, '_print_alert_enabled', lambda: False)
    fired = _after_job_list(monkeypatch, lambda rows: _write_other(job_id, **values))
    assert alerts.check_print_health()['auto_cancelled'] == 0
    assert fired == [True]
    current = _read(job_id)
    assert current.status == values.get('status', 'pending')
    assert all(getattr(current, key) == value for key, value in values.items())


@pytest.mark.parametrize('channel,send_lease,empty_old_lease', [
    ('desktop', False, False), ('desktop', True, False),
    ('v1', True, False), ('v1', False, True),
])
@pytest.mark.parametrize('outcome', ['complete', 'fail'])
def test_normal_result_and_existing_lease_compatibility(
        case, channel, send_lease, empty_old_lease, outcome):
    client, station_id, csrf, seen = case
    job = _job(station_id if channel == 'v1' else None,
               lease_token=None if empty_old_lease else 'synthetic-old-lease')
    job_id = job.id
    prefix = '/print_queue/api/v1' if channel == 'v1' else '/print_queue'
    payload = {'error_msg': '合成打印结果'}
    if send_lease:
        payload['lease_token'] = job.lease_token
    headers = {'Authorization': 'Bearer cas-synthetic-workstation-token'} if channel == 'v1' else {
        'X-CSRFToken': csrf}
    response = client.post(f'{prefix}/jobs/{job_id}/{outcome}', json=payload, headers=headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    current = _read(job_id)
    assert current.status == ('done' if outcome == 'complete' else 'failed')
    assert (current.printed_at is not None) == (outcome == 'complete')
    assert current.error_msg == '合成打印结果'
    # Existing desktop callbacks do not create failure notifications.
    assert len(seen) == (1 if channel == 'v1' and outcome == 'fail' else 0)


@pytest.mark.parametrize('channel', ['desktop', 'v1'])
@pytest.mark.parametrize('outcome', ['complete', 'fail'])
def test_result_database_lock_is_chinese_and_retryable(case, monkeypatch, channel, outcome):
    from sqlalchemy.exc import OperationalError
    client, station_id, csrf, seen = case
    job = _job(station_id if channel == 'v1' else None)
    job_id, lease = job.id, job.lease_token
    def locked_commit():
        raise OperationalError('UPDATE print_job', {}, Exception('database is locked'))
    monkeypatch.setattr(w.db.session, 'commit', locked_commit)
    prefix = '/print_queue/api/v1' if channel == 'v1' else '/print_queue'
    headers = {'Authorization': 'Bearer cas-synthetic-workstation-token'} if channel == 'v1' else {
        'X-CSRFToken': csrf}
    response = client.post(f'{prefix}/jobs/{job_id}/{outcome}', json={'lease_token': lease}, headers=headers)
    assert response.status_code == 503
    assert '打印队列忙' in response.get_json()['msg'] and '稍后重试' in response.get_json()['msg']
    current = _read(job_id)
    assert current.status == 'printing' and current.lease_token == lease
    assert seen == []


def test_claim_uses_current_database_attempts_after_pending_aba(case, monkeypatch):
    job = _job(status='pending', attempts=1, lease_token=None, printing_started_at=None)
    job_id = job.id
    # Another legitimate claim/recovery cycle has returned the task to pending.
    def intervening_cycle(rows):
        def cycle(other):
            with monkeypatch.context() as patch:
                patch.setattr(w.db, 'session', _BoundSession(other))
                claimed = queue._claim_pending_job(w.PrintJob)
                assert claimed is not None and claimed.attempts == 2
                claimed.printing_started_at = datetime.now() - timedelta(minutes=7)
                other.commit()
                assert queue._recover_zombie_printing_jobs() == 1
        _other_session(cycle)
    fired = _after_job_list(monkeypatch, intervening_cycle)
    claimed = queue._claim_pending_job(w.PrintJob)
    assert fired == [True] and claimed is not None
    current = _read(job_id)
    assert current.status == 'printing' and current.attempts == 3
    assert current.lease_token and current.printing_started_at is not None


def test_failure_alert_reads_saved_fields_with_session_expiration_disabled(case, monkeypatch):
    job = _job()
    job_id = job.id
    monkeypatch.setattr(w.db.session(), 'expire_on_commit', False)
    assert queue.mark_job_printed(job, False, '合成缺纸') is True
    assert case[3] == [(job_id, 'failed', '合成缺纸', 1)]


@pytest.mark.parametrize('replacement', [False, True])
def test_builtin_agent_stays_serial_and_reports_result_conflict(case, monkeypatch, replacement):
    import local_print_agent as agent
    station = w.db.session.get(w.PrintWorkstation, case[1])
    station.code = agent.BUILTIN_WS_CODE
    w.db.session.commit()
    job = _job(station.id, status='pending', lease_token=None, printing_started_at=None)
    job_id = job.id
    printing_calls = []
    def simulated_browser(browser, url, timeout):
        printing_calls.append((browser, url, timeout))
        current = w.db.session.get(w.PrintJob, job_id)
        assert current.status == 'printing'
        if replacement:
            _write_other(job_id, lease_token='synthetic-other-agent', printing_started_at=datetime.now())
        return True
    monkeypatch.setattr(agent, 'print_url_via_browser', simulated_browser)
    # No printer_id means no operating-system printer enumeration/switching.
    result = agent._claim_and_print('http://synthetic.invalid', 'synthetic-browser')
    assert len(printing_calls) == 1
    current = _read(job_id)
    assert current.status == ('printing' if replacement else 'done')
    assert result['ok'] is (not replacement)
    if replacement:
        assert result['result_saved'] is False
    else:
        assert result == {'job_id': job_id, 'ok': True}
    assert case[3] == []


@pytest.mark.parametrize('channel,lease', [('desktop', 'wrong-synthetic-lease'), ('v1', None)])
@pytest.mark.parametrize('outcome', ['complete', 'fail'])
def test_result_rejects_wrong_or_missing_required_lease(case, channel, lease, outcome):
    client, station_id, csrf, seen = case
    job = _job(station_id if channel == 'v1' else None)
    job_id, expected_lease = job.id, job.lease_token
    prefix = '/print_queue/api/v1' if channel == 'v1' else '/print_queue'
    headers = {'Authorization': 'Bearer cas-synthetic-workstation-token'} if channel == 'v1' else {
        'X-CSRFToken': csrf}
    response = client.post(f'{prefix}/jobs/{job_id}/{outcome}', json={'lease_token': lease}, headers=headers)
    assert response.status_code == 409
    current = _read(job_id)
    assert current.status == 'printing' and current.lease_token == expected_lease
    assert seen == []
