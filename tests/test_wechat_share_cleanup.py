"""History cleanup uses fresh synthetic data; never a production DB/receiver."""
from datetime import date, datetime, timedelta

import pytest

import app as m
from tests.test_round26_input_http import http_case


@pytest.fixture
def cleanup_case(http_case, tmp_path, monkeypatch):
    client, ids, business_state = http_case
    images = tmp_path / 'share-images'
    images.mkdir()
    monkeypatch.setattr(m, '_wechat_share_output_dir', lambda: str(images))
    with m.app.app_context():
        config = m.WechatShareConfig(receiver_name='synthetic')
        m.db.session.add(config)
        m.db.session.flush()
        for i, (status, days) in enumerate([
            ('sent', 100), ('failed', 100), ('skipped', 100),
            ('pending', 100), ('sending', 100), ('uncertain', 100),
            ('sent', 40), ('sent', 2),
        ], 1):
            image = images / f'{i}.png'
            image.write_bytes(b'synthetic image')
            m.db.session.add(m.WechatShareLog(config_id=config.id, module_key='in_order',
                order_id=i, share_date=date.today(), status=status, image_path=str(image),
                message='legacy outcome', created_at=datetime.now()-timedelta(days=days)))
        m.db.session.commit()
    yield client, images, business_state


def preview(client, days=90, images=False):
    response = client.get('/wechat_share/logs/cleanup_preview', query_string={
        'retention_days': days, 'delete_images': int(images)})
    assert response.status_code == 200, response.json
    return response.json['data']


def cleanup(client, plan, days=90, images=False):
    return client.post('/wechat_share/logs/cleanup', json={
        'retention_days': days, 'delete_images': images, 'preview_token': plan['preview_token']})


@pytest.mark.parametrize('days,count', [(90,3), (30,4), (0,5)])
def test_preview_share_cleanup(cleanup_case, days, count):
    clients, images, state = cleanup_case
    client = clients()
    before = state()
    plan = preview(client, days)
    assert plan['count'] == count and plan['protected_count'] == 3
    response = cleanup(client, plan, days)
    assert response.status_code == 200, response.json
    assert response.json['deleted'] == count
    assert state() == before
    assert len(list(images.glob('*.png'))) == 8  # images retained by default
    with m.app.app_context():
        assert {'pending','sending','uncertain'} <= {r.status for r in m.WechatShareLog.query.all()}
        from models.wechat import WechatShareDispatch
        assert m.db.session.get(WechatShareDispatch, ('in_order',1,date.today())).state == 'sent'
        assert m.db.session.get(WechatShareDispatch, ('in_order',2,date.today())).state == 'uncertain'


def test_cleanup_stale_preview_and_changed_options(cleanup_case):
    clients, images, _ = cleanup_case
    client = clients()
    plan = preview(client)
    assert cleanup(client, plan, 0).status_code == 409
    with m.app.app_context():
        m.db.session.get(m.WechatShareLog, 1).status = 'sending'
        m.db.session.commit()
    assert cleanup(client, plan).status_code == 409
    with m.app.app_context():
        assert m.WechatShareLog.query.count() == 8
    assert len(list(images.glob('*.png'))) == 8


def test_cleanup_images_shared_outside_and_failure(cleanup_case, monkeypatch):
    clients, images, _ = cleanup_case
    outside = images.parent / 'outside.png'
    outside.write_bytes(b'keep')
    with m.app.app_context():
        m.db.session.get(m.WechatShareLog, 2).image_path = str(outside)
        m.db.session.get(m.WechatShareLog, 3).image_path = str(images/'4.png')
        m.db.session.commit()
    client = clients()
    plan = preview(client, images=True)
    response = cleanup(client, plan, images=True)
    assert response.status_code == 200, response.json
    assert not (images/'1.png').exists()
    assert outside.exists() and (images/'4.png').exists()
    assert response.json['images_deleted'] == 1


@pytest.mark.parametrize('role,csrf,expected', [('finance',True,403), (None,True,401), ('admin',False,400)])
def test_cleanup_auth_and_csrf(cleanup_case, role, csrf, expected):
    clients, _, _ = cleanup_case
    response = clients(role, csrf).post('/wechat_share/logs/cleanup', json={})
    assert response.status_code == expected


@pytest.mark.parametrize('payload', [{}, {'retention_days': 1},
    {'retention_days':False,'delete_images':False,'preview_token':'x'},
    {'retention_days':0,'delete_images':'false','preview_token':'x'},
    {'retention_days':0,'delete_images':False,'preview_token':'forged'}])
def test_cleanup_invalid_payload_never_deletes(cleanup_case, payload):
    clients, _, _ = cleanup_case
    assert clients().post('/wechat_share/logs/cleanup', json=payload).status_code in (400,409)
    with m.app.app_context():
        assert m.WechatShareLog.query.count() == 8


def test_cleanup_preserves_active_dispatch_and_normal_dedup(cleanup_case):
    clients, _, _ = cleanup_case
    from models.wechat import WechatShareDispatch
    from services.wechat_share_dispatch import execute_share
    with m.app.app_context():
        m.db.session.add(WechatShareDispatch(module_key='in_order', order_id=3,
            share_date=date.today(), token='active', state='preparing', log_id=3,
            lease_until=datetime.now()+timedelta(minutes=5)))
        m.db.session.commit()
    client = clients()
    plan = preview(client)
    assert plan['count'] == 2
    assert cleanup(client, plan).status_code == 200
    with m.app.app_context():
        def forbidden(*a):
            raise AssertionError('Cleanup must not trigger a duplicate delivery')
        result = execute_share({'module_key':'in_order','order_id':1,'share_date':date.today()}, {}, forbidden, forbidden)
        assert result['action'] == 'skipped' and result['status'] == 'sent'
        assert m.db.session.get(m.WechatShareLog, 3)


def test_cleanup_file_error_reports_partial_success(cleanup_case, monkeypatch):
    clients, images, _ = cleanup_case
    from pathlib import Path
    original = Path.unlink
    def fail_one(path, *a, **kw):
        if path == images/'1.png':
            raise PermissionError('synthetic locked image')
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, 'unlink', fail_one)
    client = clients()
    response = cleanup(client, preview(client, images=True), images=True)
    assert response.status_code == 200
    assert response.json['deleted'] == 3 and response.json['images_failed'] == 1
    assert (images/'1.png').exists()
    assert '清理失败 1 张' in response.json['msg']


def test_cleanup_commit_failure_keeps_records_and_files(cleanup_case):
    clients, images, _ = cleanup_case
    from sqlalchemy import event
    client = clients()
    plan = preview(client, images=True)
    with m.app.app_context():
        engine = m.db.engine
    def fail_commit(connection):
        raise RuntimeError('synthetic cleanup commit rejection')
    event.listen(engine, 'commit', fail_commit)
    try:
        response = cleanup(client, plan, images=True)
        assert response.status_code == 503
    finally:
        event.remove(engine, 'commit', fail_commit)
    with m.app.app_context():
        assert m.WechatShareLog.query.count() == 8
    assert len(list(images.glob('*.png'))) == 8


def test_cleanup_failed_claim_retains_legacy_success_guard(cleanup_case):
    clients, _, _ = cleanup_case
    from models.wechat import WechatShareDispatch
    with m.app.app_context():
        m.db.session.add(WechatShareDispatch(module_key='in_order', order_id=1,
            share_date=date.today(), token='failed-force', state='failed', log_id=1,
            lease_until=datetime.now()))
        m.db.session.commit()
    client = clients()
    assert cleanup(client, preview(client)).status_code == 200
    with m.app.app_context():
        claim = m.db.session.get(WechatShareDispatch, ('in_order',1,date.today()))
        assert claim.state == 'sent' and claim.log_id is None


def test_legacy_clear_uses_same_guards(cleanup_case):
    clients, images, _ = cleanup_case
    response = clients().post('/wechat_share/logs/clear', data={'status':'failed'})
    assert response.status_code == 200 and response.json['deleted'] == 1
    from models.wechat import WechatShareDispatch
    with m.app.app_context():
        assert m.db.session.get(WechatShareDispatch, ('in_order',2,date.today())).state == 'uncertain'
    assert len(list(images.glob('*.png'))) == 8


def test_cleanup_missing_dispatch_table_fails_closed(cleanup_case):
    clients, images, _ = cleanup_case
    from models.wechat import WechatShareDispatch
    with m.app.app_context():
        WechatShareDispatch.__table__.drop(m.db.engine)
    response = clients().get('/wechat_share/logs/cleanup_preview')
    assert response.status_code == 503
    with m.app.app_context():
        assert m.WechatShareLog.query.count() == 8
    assert len(list(images.glob('*.png'))) == 8


def test_cleanup_date_boundary_and_full_set_not_page(cleanup_case):
    clients, _, _ = cleanup_case
    from datetime import time
    cutoff = datetime.combine(date.today()-timedelta(days=90), time.min)
    with m.app.app_context():
        for i in range(30):
            m.db.session.add(m.WechatShareLog(module_key='in_order',order_id=100+i,
                share_date=date.today(),status='skipped',created_at=cutoff-timedelta(seconds=1)))
        m.db.session.get(m.WechatShareLog, 1).created_at = cutoff
        m.db.session.commit()
    client = clients()
    plan = preview(client)
    assert plan['count'] == 32
    assert cleanup(client, plan).json['deleted'] == 32
    with m.app.app_context():
        assert m.db.session.get(m.WechatShareLog, 1)


def test_cleanup_referenced_alias_and_non_png_stay(cleanup_case):
    clients, images, _ = cleanup_case
    other = images/'not-an-image.db'
    other.write_bytes(b'keep')
    with m.app.app_context():
        m.db.session.get(m.WechatShareLog, 2).image_path = str(other)
        # Same file expressed with a parent segment must remain referenced.
        m.db.session.get(m.WechatShareLog, 8).image_path = str(images/'..'/'share-images'/'1.png')
        m.db.session.commit()
    client = clients()
    response = cleanup(client, preview(client, images=True), images=True)
    assert response.status_code == 200
    assert (images/'1.png').exists() and other.exists()


def test_cleanup_expired_preview_rejected(cleanup_case, monkeypatch):
    clients, _, _ = cleanup_case
    client = clients()
    plan = preview(client)
    from services.wechat_share_cleanup import _signer
    with m.app.app_context():
        signer = _signer()
        data = signer.loads(plan['preview_token'])
        # Age only the cleanup token; HTTP session and CSRF remain valid.
        import itsdangerous.timed
        with monkeypatch.context() as patch:
            patch.setattr(itsdangerous.timed.TimestampSigner, 'get_timestamp', lambda _: 1)
            plan['preview_token'] = signer.dumps(data)
    assert cleanup(client, plan).status_code == 409


def test_cleanup_share_history(cleanup_case):
    _, images, state = cleanup_case
    from services.wechat_share_cleanup import preview_share_cleanup, cleanup_share_history
    before = state()
    with m.app.app_context():
        actor = m.User.query.filter_by(username='QA27-admin').one().id
        plan = preview_share_cleanup(90, False, actor)
        assert plan['count'] == 3
        result = cleanup_share_history(90, False, actor, plan['preview_token'])
        assert result['deleted'] == 3
        assert m.WechatShareLog.query.count() == 5
    assert state() == before
    assert len(list(images.glob('*.png'))) == 8
