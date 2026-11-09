"""Actual route/permission/background-consumer checks against synthetic memory data."""
# 直接运行时应用导入与数据库隔离尚未证明；原有测试保留。
from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'app'))
import app as w


@pytest.fixture
def clients(monkeypatch):
    old_config = dict(w.app.config)
    state = dict(w.app.extensions.get('wms_runtime_status', {}))
    monkeypatch.setitem(w.app.extensions, 'wms_runtime_status', dict(state, paused=True))
    w.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with w.app.app_context():
        w.db.drop_all()
        w.db.create_all()
        users = [w.User(username='runtime-admin', role='admin', must_change_password=False,
                        password_hash='synthetic-unused'),
                 w.User(username='runtime-warehouse', role='warehouse', must_change_password=False,
                        password_hash='synthetic-unused')]
        w.db.session.add_all(users)
        w.db.session.commit()
        ids = [user.id for user in users]
    result = []
    for user_id in ids:
        client = w.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
        result.append(client)
    yield result
    with w.app.app_context():
        w.db.session.remove()
        w.db.drop_all()
    w.app.config.clear()
    w.app.config.update(old_config)


def test_system_runtime_status_is_readonly_and_admin_only(clients):
    admin, warehouse = clients
    anonymous = w.app.test_client().get('/system_status')
    assert anonymous.status_code == 302 and '/login' in anonymous.location
    denied = warehouse.get('/system_status', headers={'Accept': 'application/json'})
    assert denied.status_code == 403
    response = admin.get('/system_status')
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert '发布与运行状态' in text and '未登记完整发布制品' in text and '当前部署暂停' in text
    assert admin.post('/system_status').status_code == 405
    assert 'C:\\wms' not in text and 'DATABASE_URL' not in text
    assert '发布与运行状态' in admin.get('/system_settings').get_data(as_text=True)


def test_paused_share_page_neither_contacts_helper_nor_creates_config(clients, monkeypatch):
    admin, _ = clients
    monkeypatch.setattr(w.requests, 'get', lambda *a, **k: pytest.fail('must not contact helper'))
    with w.app.app_context():
        assert w.WechatShareConfig.query.count() == 0
    response = admin.get('/wechat_share')
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert 'runtimePauseNotice' in text and '<fieldset disabled>' in text
    with w.app.app_context():
        assert w.WechatShareConfig.query.count() == 0
        assert w.WechatShareLog.query.count() == 0


def test_paused_background_consumers_do_not_enqueue_send_or_cleanup(clients, monkeypatch):
    from routes import print_queue
    monkeypatch.setattr(w, 'get_system_setting', lambda *a, **k: pytest.fail('paused master needs no setting read'))
    monkeypatch.setattr(w, '_wechat_share_cleanup_old_images', lambda *a, **k: pytest.fail('no cleanup'))
    with w.app.app_context():
        assert w._wechat_share_master_enabled() is False
        assert print_queue.auto_print_on_submit_enabled() is False
        assert w._wechat_share_cleanup_old_images_daily() == 0
        w.run_due_wechat_share_jobs()
        assert w.WechatShareLog.query.count() == 0
        assert w.PrintJob.query.count() == 0


def test_paused_local_print_agent_never_starts_a_thread(clients, monkeypatch):
    import local_print_agent
    with monkeypatch.context() as changes:
        changes.setenv('WMS_LOCAL_PRINT_AGENT', '1')
        changes.setitem(w.app.config, 'TESTING', False)
        changes.setattr(local_print_agent.threading, 'Thread',
                       lambda *a, **k: pytest.fail('paused deployment must not start print agent'))
        assert local_print_agent.start_local_print_agent(w.app, 'http://synthetic.invalid') is None


@pytest.mark.parametrize('path', ['/print_routing', '/print_queue/station'])
def test_paused_device_menus_explain_actual_state(clients, path):
    admin, _ = clients
    response = admin.get(path)
    assert response.status_code == 200
    assert '当前部署暂停微信发送和设备队列' in response.get_data(as_text=True)


def test_pause_guard_preserves_existing_csrf_checks(clients, monkeypatch):
    admin, _ = clients
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', True)
    response = admin.post('/print_queue/jobs', json={'job_type': 'in_order', 'target_id': 1})
    assert response.status_code == 400
    with w.app.app_context():
        assert w.PrintJob.query.count() == 0


def test_actual_share_send_endpoint_is_paused_before_any_log_write(clients):
    admin, _ = clients
    response = admin.post('/wechat_share/run_now', json={'force': True})
    assert response.status_code == 503
    with w.app.app_context():
        assert w.WechatShareLog.query.count() == 0
        assert w.WechatShareConfig.query.count() == 0
