"""R28-F01/F02 locks: real dispatch, fresh SQLite, synthetic HTTP auth/CSRF.

No real receiver, keys, stock mutation, deletion/restoration or outbound network.
Tests deliberately retain uncertain delivery, rather than claiming exactly-once.
"""
import builtins
from datetime import date, datetime, timedelta
import io
import json
import multiprocessing
import os
from pathlib import Path
import socket
import threading

import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, event

import app as m
from tests.test_round26_input_http import http_case


def _client(ids, role='actor', csrf=True):
    client = m.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(ids[role])
        session['_fresh'] = True
        session['csrf_token'] = 'qa29-public-csrf'
    client.environ_base.update(HTTP_ACCEPT='application/json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    if csrf:
        client.environ_base['HTTP_X_CSRFTOKEN'] = URLSafeTimedSerializer(
            m.app.secret_key, salt='wtf-csrf-token').dumps('qa29-public-csrf')
    return client


def _memory_boundaries(patch, virtual, receive):
    op, size = builtins.open, os.path.getsize
    patch.setattr(builtins, 'open', lambda path, *a, **k: io.BytesIO()
                  if str(path).startswith(virtual) else op(path, *a, **k))
    patch.setattr(os.path, 'getsize', lambda path: 4 if str(path).startswith(virtual) else size(path))
    patch.setattr(os.path, 'exists', lambda path, original=os.path.exists:
                  True if str(path).startswith(virtual) else original(path))
    patch.setattr(m, '_wechat_share_output_dir', lambda: virtual)
    patch.setattr(m, '_build_order_share_image', lambda *a: (io.BytesIO(b'QA29'), 'synthetic.png'))
    patch.setattr(m, '_wechat_share_deliver', receive)
    def forbidden(*a, **k):
        raise AssertionError('No real transport/network in dispatch tests')
    patch.setattr(m.requests, 'post', forbidden)
    patch.setattr(m.requests, 'get', forbidden)
    patch.setattr(socket.socket, 'connect', forbidden)
    patch.setattr(socket, 'getaddrinfo', forbidden)


@pytest.fixture
def case(tmp_path, monkeypatch, request):
    dbfile = tmp_path / 'new-synthetic-share.db'
    assert not dbfile.exists()
    if os.environ.get('WMS_QA_TEST_DB_ROOT'):
        assert dbfile.resolve().is_relative_to(Path(os.environ['WMS_QA_TEST_DB_ROOT']).resolve())
    monkeypatch.setitem(m.app.config, 'TESTING', True)
    monkeypatch.setitem(m.app.config, 'PROPAGATE_EXCEPTIONS', False)
    monkeypatch.setitem(m.app.config, 'WTF_CSRF_ENABLED', True)
    monkeypatch.setitem(m.app.config, 'SESSION_COOKIE_SECURE', False)
    engine = create_engine('sqlite:///' + dbfile.as_posix(), connect_args={'timeout': 5, 'check_same_thread': False})
    protected = [False]
    @event.listens_for(engine, 'connect')
    def sqlite(connection, record):
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA busy_timeout=5000')
    @event.listens_for(engine, 'before_cursor_execute')
    def boundary(conn, cursor, statement, parameters, context, many):
        verb = statement.lstrip().split(None, 1)[0].upper()
        assert verb not in {'DELETE', 'DROP', 'ALTER'}, statement
        if protected[0] and verb in {'INSERT', 'UPDATE'}:
            assert not any(t in statement.lower() for t in ('stock_transaction', 'location_inventory', 'material')), statement
    with m.app.app_context():
        old_engine = m.db.engines[None]
        m.db.session.remove()
        m.db.engines[None] = engine
        if getattr(request, 'param', '') == 'legacy-no-dispatch':
            m.db.metadata.create_all(bind=engine, tables=[t for t in m.db.metadata.sorted_tables
                                                       if t.name != 'wechat_share_dispatch'])
        else:
            m.db.create_all()
        actor = m.User(username='QA29-admin', role='admin', status='normal',
                       password_hash='!unusable-synthetic', must_change_password=False)
        viewer = m.User(username='QA29-finance', role='finance', status='normal',
                        password_hash='!unusable-synthetic', must_change_password=False)
        config = m.WechatShareConfig(receiver_name='QA29-MEMORY', share_in_order=True,
                                     enabled=True, auto_send=True, helper_url='http://127.0.0.1:0/blocked')
        order = m.InOrder(order_no='QA29-SHARE', warehouse='QA29-W', business_type='purchase',
                          date=date.today(), status='completed', total_amount=0)
        material = m.Material(code='QA29-M', name='synthetic', stock=0)
        m.db.session.add_all([actor, viewer, config, order, material,
                              m.SystemSetting(key='wechat_share_enabled', value='1')])
        m.db.session.flush()
        m.db.session.add(m.InOrderItem(in_order_id=order.id, material_id=material.id, quantity=1, price=0, amount=0))
        m.db.session.commit()
        ids = {'actor': actor.id, 'viewer': viewer.id, 'config': config.id, 'order': order.id}
    protected[0] = True
    calls = []
    def receive(*a, **k):
        calls.append({'memory_ack': True, 'pid': os.getpid()})
        return 'sent', 'ok', 'pure-memory receipt'
    _memory_boundaries(monkeypatch, str(tmp_path / 'virtual-images'), receive)
    yield {'engine': engine, 'ids': ids, 'calls': calls, 'receive': receive, 'dbfile': str(dbfile),
           'client': lambda **kw: _client(ids, **kw)}
    with m.app.app_context():
        m.db.session.remove()
        m.db.engines[None] = old_engine
    engine.dispose()


def _post(case, force='0'):
    return case['client']().post('/wechat_share/run_now', data={'force': force})


def _rows():
    with m.app.app_context():
        m.db.session.expire_all()
        return [(r.id, r.status) for r in m.WechatShareLog.query.order_by(m.WechatShareLog.id).all()]


def test_execute_share(case):
    """Normal receipt, ordinary dedup and a new explicit force attempt."""
    first = _post(case)
    assert first.status_code == 200 and first.json['created'] == 1
    assert _rows() == [(1, 'sent')]
    assert _post(case).json['skipped'] == 1
    assert len(case['calls']) == 1
    forced = _post(case, '1')
    assert forced.status_code == 200 and forced.json['created'] == 1
    assert len(case['calls']) == 2 and _rows() == [(1, 'sent'), (2, 'sent')]


@pytest.mark.parametrize('commit_error', ['runtime', 'integrity'])
def test_ack_then_commit_failure_does_not_replay(case, commit_error):
    injected = [False]
    def fail(connection):
        if case['calls'] and not injected[0]:
            injected[0] = True
            if commit_error == 'integrity':
                from sqlalchemy.exc import IntegrityError
                raise IntegrityError('COMMIT', {}, RuntimeError('QA29 receipt commit ambiguity'))
            raise RuntimeError('QA29 receipt commit fault')
    event.listen(case['engine'], 'commit', fail)
    try:
        first = _post(case)
        assert first.status_code == 503 and '待确认' in first.json['msg']
        assert _rows() == [(1, 'uncertain')]
        retry = _post(case)
        assert retry.status_code == 200 and retry.json['skipped'] == 1
        assert retry.json['uncertain'] == 1 and len(case['calls']) == 1
        forced = _post(case, '1')
        assert forced.status_code == 200 and forced.json['created'] == 1
        assert len(case['calls']) == 2 and _rows() == [(1, 'uncertain'), (2, 'sent')]
    finally:
        event.remove(case['engine'], 'commit', fail)


@pytest.mark.parametrize('legacy_status', ['pending', 'sent'])
def test_unique_claim_conflict_preserves_shared_memory_connection(http_case, monkeypatch, legacy_status):
    """Expected duplicate flushes must not invalidate StaticPool's shared DBAPI connection."""
    client, ids, state = http_case
    def refuse(*args, **kwargs):
        pytest.fail('A historical pending/sent attempt must not render or deliver')
    monkeypatch.setattr(m, '_build_order_share_image', refuse)
    monkeypatch.setattr(m, '_wechat_share_deliver', refuse)
    with m.app.app_context():
        m.db.session.add(m.SystemSetting(key='wechat_share_enabled', value='1'))
        config = m.WechatShareConfig(receiver_name='QA29-NO-SEND', share_in_order=True,
                                     enabled=True, auto_send=False, immediate_on_complete=False)
        order = m.InOrder(order_no='QA29-SHARED-' + legacy_status, business_type='purchase',
                          warehouse='QA27-A', date=date.today(), status='completed', total_amount=0)
        m.db.session.add_all([config, order])
        m.db.session.flush()
        order_id = order.id
        m.db.session.add(m.WechatShareLog(config_id=config.id, module_key='in_order',
            order_id=order_id, order_no=order.order_no, share_date=date.today(), status=legacy_status))
        m.db.session.commit()
        engine = m.db.engine
    invalidations = []
    def invalidated(connection, record, exception):
        invalidations.append(type(exception).__name__)
    event.listen(engine.pool, 'invalidate', invalidated)
    try:
        c = client()
        for _ in range(3):
            response = c.post('/wechat_share/run_now', data={'force': '0'})
            assert response.status_code == 200, response.get_json()
            assert response.json['created'] == 0 and response.json['skipped'] == 1
        assert invalidations == []
        with m.app.app_context():
            assert m.WechatShareLog.query.count() == 1
            claim = m.db.session.get(m.WechatShareDispatch, ('in_order', order_id, date.today()))
            assert claim.state == legacy_status
    finally:
        event.remove(engine.pool, 'invalidate', invalidated)


@pytest.mark.parametrize('case', ['normal', 'legacy-no-dispatch'], indirect=True)
@pytest.mark.parametrize('missing_uncertain', [False, True])
def test_share_menu_accepts_legacy_counts_without_claim_schema(case, monkeypatch, missing_uncertain):
    render = m.render_template
    def old_context(template, **kwargs):
        if template == 'wechat_share.html' and missing_uncertain:
            kwargs['log_counts'].pop('uncertain', None)
            assert set(kwargs['log_counts']) == {'pending', 'failed', 'sent_today'}
        return render(template, **kwargs)
    monkeypatch.setattr(m, 'render_template', old_context)
    response = case['client']().get('/wechat_share')
    assert response.status_code == 200
    assert not case['calls']
    with m.app.app_context():
        assert m.WechatShareLog.query.count() == 0


def test_persistent_receipt_database_failure_keeps_durable_sending(case):
    from sqlalchemy.exc import OperationalError
    def fail(connection):
        if case['calls']:
            raise OperationalError('COMMIT', {}, RuntimeError('QA29 database unavailable'))
    event.listen(case['engine'], 'commit', fail)
    try:
        assert _post(case).status_code == 503
        assert len(case['calls']) == 1
    finally:
        event.remove(case['engine'], 'commit', fail)
    assert _rows() == [(1, 'sending')]
    assert _post(case).json['skipped'] == 1
    assert _post(case, '1').json['skipped'] == 1  # force cannot steal a live sender
    assert len(case['calls']) == 1


@pytest.mark.parametrize('case', ['legacy-no-dispatch'], indirect=True)
def test_missing_claim_table_fails_closed_then_explicit_schema_provision(case):
    first = _post(case)
    assert first.status_code == 503 and 'wechat_share_dispatch' in first.json['msg']
    assert not case['calls'] and not _rows()
    with m.app.app_context():
        # This fresh synthetic DB only. No startup script, existing row or ALTER.
        m.WechatShareDispatch.__table__.create(bind=case['engine'], checkfirst=True)
        m.WechatShareDispatch.__table__.create(bind=case['engine'], checkfirst=True)
    assert _post(case).json['created'] == 1 and len(case['calls']) == 1


@pytest.mark.parametrize('outcome', ['timeout', 'exception', 'malformed'])
def test_unknown_transport_never_automatically_replayed(case, monkeypatch, outcome):
    def receive(*a, **k):
        case['calls'].append({'maybe_sent': True})
        if outcome == 'exception':
            raise RuntimeError('unknown sender failure')
        if outcome == 'malformed':
            return None
        return 'failed', 'helper_timeout', 'could have been received'
    monkeypatch.setattr(m, '_wechat_share_deliver', receive)
    response = _post(case)
    assert response.status_code == (200 if outcome == 'timeout' else 503)
    assert _rows() == [(1, 'uncertain')]
    assert _post(case).json['skipped'] == 1 and len(case['calls']) == 1


@pytest.mark.parametrize('phase', ['preparing', 'sending'])
def test_expired_claim_recovery_is_phase_sensitive(case, phase):
    with m.app.app_context():
        m.db.session.add(m.WechatShareDispatch(module_key='in_order', order_id=case['ids']['order'],
            share_date=date.today(), token='a' * 32, state=phase, lease_until=datetime.now()-timedelta(seconds=1)))
        m.db.session.commit()
    result = _post(case)
    assert result.status_code == 200
    if phase == 'preparing':
        assert result.json['created'] == 1 and len(case['calls']) == 1
    else:
        assert result.json['skipped'] == 1 and len(case['calls']) == 0
        assert _post(case, '1').json['created'] == 1 and len(case['calls']) == 1


def test_stale_preparer_cannot_send_after_reclaim(case):
    from services.wechat_share_dispatch import _claim, _record, DispatchUnavailable
    key = {'module_key': 'in_order', 'order_id': case['ids']['order'], 'share_date': date.today()}
    with m.app.app_context():
        token, _ = _claim(key, False)
        row = m.db.session.get(m.WechatShareDispatch, tuple(key.values()))
        row.lease_until = datetime.now() - timedelta(seconds=1)
        m.db.session.commit()
        next_token, _ = _claim(key, False)
        assert token != next_token
        with pytest.raises(DispatchUnavailable):
            _record(key, token, 'sending', 'stale', {'config_id': case['ids']['config']})
    assert not case['calls'] and not _rows()


def test_preflight_failure_can_retry_without_force(case, monkeypatch):
    monkeypatch.setattr(m, '_wechat_share_deliver', lambda *a, **k: ('failed', 'auth_failed', 'rejected before send'))
    assert _post(case).status_code == 200 and _rows() == [(1, 'failed')]
    monkeypatch.setattr(m, '_wechat_share_deliver', case['receive'])
    assert _post(case).json['created'] == 1
    assert _rows() == [(1, 'failed'), (2, 'sent')] and len(case['calls']) == 1


def test_image_failure_retries_and_no_sender_called(case, monkeypatch):
    original = m._build_order_share_image
    def fail(*a):
        raise RuntimeError('QA image render fault')
    monkeypatch.setattr(m, '_build_order_share_image', fail)
    assert _post(case).status_code == 503 and not case['calls'] and not _rows()
    monkeypatch.setattr(m, '_build_order_share_image', original)
    assert _post(case).json['created'] == 1 and len(case['calls']) == 1


@pytest.mark.parametrize('status,message,expected', [
    ('sent', 'old receipt', 'sent'), ('pending', 'old queue', 'pending'),
    ('failed', 'old timeout（错误码：helper_timeout）', 'uncertain'),
    ('failed', 'old disconnected（错误码：helper_offline）', 'uncertain'),
    ('failed', 'unknown historical error', 'uncertain'),
])
def test_legacy_logs_without_claim_are_conservatively_imported(case, status, message, expected):
    with m.app.app_context():
        m.db.session.add(m.WechatShareLog(config_id=case['ids']['config'], module_key='in_order',
            order_id=case['ids']['order'], order_no='QA29-SHARE', share_date=date.today(), status=status, message=message))
        m.db.session.commit()
    result = _post(case)
    assert result.status_code == 200 and result.json['skipped'] == 1 and not case['calls']
    with m.app.app_context():
        assert m.WechatShareDispatch.query.one().state == expected
        assert m.WechatShareLog.query.one().status == status  # do not rewrite old receipt


@pytest.mark.parametrize('commit_number', [1, 2])
def test_failure_before_delivery_has_no_receiver_effect_and_recovers(case, commit_number):
    commits = []
    def fail(connection):
        commits.append(True)
        if len(commits) == commit_number:
            from sqlalchemy.exc import OperationalError
            raise OperationalError('COMMIT', {}, RuntimeError('pre-send fault'))
    event.listen(case['engine'], 'commit', fail)
    try:
        assert _post(case).status_code == 503 and not case['calls']
    finally:
        event.remove(case['engine'], 'commit', fail)
    with m.app.app_context():
        gate = m.WechatShareDispatch.query.first()
        if gate:
            assert gate.state == 'preparing'
            gate.lease_until = datetime.now() - timedelta(seconds=1)
            m.db.session.commit()
    assert _post(case).json['created'] == 1 and len(case['calls']) == 1


def test_later_outer_commit_failure_cannot_undo_durable_receipt(case):
    after_send = []
    def fail(connection):
        if case['calls']:
            after_send.append(True)
            if len(after_send) == 2:
                raise RuntimeError('outer commit failed after durable receipt')
    event.listen(case['engine'], 'commit', fail)
    try:
        assert _post(case).status_code == 500
    finally:
        event.remove(case['engine'], 'commit', fail)
    assert _rows() == [(1, 'sent')]
    assert _post(case).json['skipped'] == 1 and len(case['calls']) == 1


def test_same_order_different_day_has_independent_claim(case):
    with m.app.app_context():
        m.db.session.add(m.WechatShareDispatch(module_key='in_order', order_id=case['ids']['order'],
            share_date=date.today()-timedelta(days=1), token='b'*32, state='uncertain', lease_until=datetime.now()))
        m.db.session.commit()
    assert _post(case).json['created'] == 1 and len(case['calls']) == 1


def test_caller_pending_writes_are_not_committed_by_dispatch(case):
    from services.wechat_share_dispatch import DispatchUnavailable
    with m.app.app_context():
        config = m.db.session.get(m.WechatShareConfig, case['ids']['config'])
        order = m.db.session.get(m.InOrder, case['ids']['order'])
        config.receiver_name = 'unsaved change'
        with pytest.raises(DispatchUnavailable, match='先保存'):
            m._wechat_share_order(config, order)
        m.db.session.rollback()
        assert config.receiver_name == 'QA29-MEMORY'
    assert not case['calls'] and not _rows()


@pytest.mark.parametrize('path', ['/wechat_share/run_now', '/wechat_share/log/1/resend'])
@pytest.mark.parametrize('access', ['anonymous', 'csrf', 'role'])
def test_http_security_not_relaxed(case, access, path):
    if access == 'anonymous':
        client = case['client']()
        with client.session_transaction() as session:
            session.pop('_user_id')
        response = client.post(path, data={})
        assert response.status_code in (302, 401)  # valid CSRF reaches real login gate
    elif access == 'csrf':
        response = case['client'](csrf=False).post(path, data={})
        assert response.status_code == 400
    else:
        response = case['client'](role='viewer').post(path, data={})
        assert response.status_code == 403
    assert not case['calls'] and not _rows()


def test_expired_preparer_actual_http_race_cannot_send_after_new_worker(case, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    results = []
    original = m._build_order_share_image
    def prepare(*a):
        if threading.current_thread().name == 'qa29-stale-preparer':
            entered.set()
            assert release.wait(15)
        return original(*a)
    monkeypatch.setattr(m, '_build_order_share_image', prepare)
    def old_worker():
        results.append(_post(case).status_code)
    old = threading.Thread(target=old_worker, name='qa29-stale-preparer')
    old.start()
    try:
        assert entered.wait(10)
        with m.app.app_context():
            gate = m.WechatShareDispatch.query.one()
            gate.lease_until = datetime.now() - timedelta(seconds=1)
            m.db.session.commit()
        assert _post(case).json['created'] == 1
        release.set()
        old.join(10)
        assert not old.is_alive() and results == [503]
        assert len(case['calls']) == 1 and _rows() == [(1, 'sent')]
    finally:
        release.set()
        old.join(10)


def test_resend_cannot_steal_an_active_normal_worker(case, monkeypatch):
    assert _post(case).status_code == 200
    entered, release = threading.Event(), threading.Event()
    results = []
    def receiving(*a, **kw):
        case['calls'].append({'memory_ack': True})
        entered.set()
        assert release.wait(15)
        return 'sent', 'ok', 'memory receipt'
    monkeypatch.setattr(m, '_wechat_share_deliver', receiving)
    forbidden = []
    monkeypatch.setattr(m, '_wechat_share_send_image', lambda *a: forbidden.append('unexpected resend'))
    worker = threading.Thread(target=lambda: results.append(_post(case, '1').status_code))
    worker.start()
    try:
        assert entered.wait(10)
        response = case['client']().post('/wechat_share/log/1/resend')
        # BUG-2026-11-10-001：活跃轮询 worker 存在时，重复派发保护直接返回
        # action='skipped' / status='uncertain'（services/wechat_share_dispatch.py:63），
        # 语义是"结果待确认、请人工核对接收端"，不是"正在发送"。
        # 2026-11-10 用户确认该保守状态为已批准的新语义，因此只同步状态期望；
        # 业务实现与下方"不得重复发送 / 不得抢占活跃 worker"断言一律不动。
        assert response.status_code == 200 and response.json['log_status'] == 'uncertain'
        assert not forbidden and len(case['calls']) == 2  # original + one active explicit attempt
        release.set()
        worker.join(10)
        assert not worker.is_alive() and results == [200]
        assert _rows() == [(1, 'sent'), (2, 'sent')]
    finally:
        release.set()
        worker.join(10)


def test_resend_preserves_history_and_uses_same_claim(case, monkeypatch):
    assert _post(case).status_code == 200
    frozen = []
    def receive(config, path):
        frozen.append(config.receiver_name)
        return 'sent', 'ok', 'resent in memory'
    monkeypatch.setattr(m, '_wechat_share_send_image', receive)
    with m.app.app_context():
        config = m.db.session.get(m.WechatShareConfig, case['ids']['config'])
        config.receiver_name = 'QA29-NEW-CONFIG'
        m.db.session.commit()
    response = case['client']().post('/wechat_share/log/1/resend')
    assert response.status_code == 200 and response.json['log_status'] == 'sent'
    assert frozen == ['QA29-MEMORY'] and _rows() == [(1, 'sent'), (2, 'sent')]
    with m.app.app_context():
        assert [r.receiver_name for r in m.WechatShareLog.query.order_by(m.WechatShareLog.id)] == ['QA29-MEMORY'] * 2


def _worker(database, ids, barrier, release, queue, force):
    """OS spawn, complete Flask request dispatch; no test-only route."""
    engine = create_engine('sqlite:///' + Path(database).as_posix(), connect_args={'timeout': 5})
    @event.listens_for(engine, 'before_cursor_execute')
    def no_business_mutations(conn, cursor, statement, params, context, many):
        verb = statement.lstrip().split(None, 1)[0].upper()
        assert verb not in {'DELETE', 'DROP', 'ALTER'}
        if verb in {'INSERT', 'UPDATE'}:
            assert not any(t in statement.lower() for t in ('stock_transaction', 'location_inventory', 'material'))
    patch = pytest.MonkeyPatch()
    m.app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=False, WTF_CSRF_ENABLED=True, SESSION_COOKIE_SECURE=False)
    def receive(*a, **k):
        queue.put({'kind': 'memory_ack', 'pid': os.getpid()})
        assert release.wait(15), 'bounded receiver wait'
        return 'sent', 'ok', 'OS memory receipt'
    _memory_boundaries(patch, str(Path(database).parent/'virtual-os'), receive)
    with m.app.app_context():
        m.db.session.remove()
        m.db.engines[None] = engine
    try:
        barrier.wait(20)
        response = _client(ids).post('/wechat_share/run_now', data={'force': force})
        queue.put({'kind': 'http', 'pid': os.getpid(), 'status': response.status_code, 'payload': response.json})
    except Exception as exc:
        queue.put({'kind': 'error', 'type': type(exc).__name__})
        raise
    finally:
        with m.app.app_context():
            m.db.session.remove()
        patch.undo()
        engine.dispose()


@pytest.mark.parametrize('force', ['0', '1'])
def test_two_independent_os_workers_one_normal_delivery(case, force):
    ctx = multiprocessing.get_context('spawn')
    barrier, release, queue = ctx.Barrier(2), ctx.Event(), ctx.Queue()
    workers = [ctx.Process(target=_worker, args=(case['dbfile'], case['ids'], barrier, release, queue, force)) for _ in range(2)]
    events = []
    try:
        for p in workers:
            p.start()
        events = [queue.get(timeout=30), queue.get(timeout=20)]
        # Winner remains inside delivery until the losing HTTP request finishes.
        assert {x['kind'] for x in events} == {'memory_ack', 'http'}, events
        release.set()
        events.append(queue.get(timeout=20))
        for p in workers:
            p.join(15)
        assert all(p.exitcode == 0 for p in workers)
        assert len({p.pid for p in workers}) == 2
        assert sum(x['kind'] == 'memory_ack' for x in events) == 1
        results = [x for x in events if x['kind'] == 'http']
        assert len(results) == 2 and all(x['status'] == 200 for x in results), events
        assert sum(x['payload']['created'] for x in results) == 1
        assert sum(x['payload']['skipped'] for x in results) == 1
        assert _rows() == [(1, 'sent')]
        evidence = Path(os.environ.get('WMS_QA_EVIDENCE') or Path(case['dbfile']).parent)
        (evidence / f'os-workers-force-{force}.json').write_text(json.dumps({
            'events': events, 'workers': [p.pid for p in workers], 'exitcodes': [p.exitcode for p in workers],
            'database': case['dbfile'], 'fresh': True, 'real_sends': 0}, indent=2), encoding='utf-8')
    finally:
        release.set()
        for p in workers:
            if p.pid and p.is_alive():
                p.join(10)
            if p.pid and p.is_alive():
                p.terminate()
                p.join(5)
        queue.close()
        queue.join_thread()
