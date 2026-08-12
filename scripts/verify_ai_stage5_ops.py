from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage5-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


def _set_setting(key: str, value: str) -> None:
    row = wms_app.SystemSetting.query.filter_by(key=key).first()
    if not row:
        row = wms_app.SystemSetting(key=key)
        wms_app.db.session.add(row)
    row.value = value


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        for username in ('stage5-admin', 'stage5-warehouse'):
            wms_app.User.query.filter_by(username=username).delete()
        wms_app.db.session.commit()
        admin = wms_app.User(username='stage5-admin', password_hash='not-used', role='admin', status='normal')
        warehouse = wms_app.User(username='stage5-warehouse', password_hash='not-used', role='warehouse', status='normal')
        wms_app.db.session.add_all([admin, warehouse])
        _set_setting('ai_feature_global_enabled', '1')
        _set_setting('ai_feature_rollout_mode', 'all')
        _set_setting('ai_feature_drafts_enabled', '1')
        _set_setting('ai_feature_agents_enabled', '1')
        _set_setting('ai_feature_vision_enabled', '1')
        _set_setting('ai_degrade_local_only', '0')
        wms_app.db.session.commit()
        admin_id = admin.id
        warehouse_id = warehouse.id

        run = wms_app.AIRun(
            user_id=admin_id,
            request_id='stage5-run-1',
            request_hash='hash-stage5-run-1',
            endpoint='/api/ai/warehouse_assistant',
            status='completed',
            model='verify-model',
            duration_ms=120,
            started_at=wms_app.datetime.now(),
            completed_at=wms_app.datetime.now(),
        )
        wms_app.db.session.add(run)
        wms_app.db.session.flush()
        wms_app.db.session.add(wms_app.AIToolCall(
            ai_run_id=run.id,
            tool_name='warehouse_insights',
            capability='warehouse_insights',
            risk_level='read',
            status='authorized',
            permission_allowed=True,
            duration_ms=12,
        ))
        wms_app.db.session.commit()

    client = app.test_client()
    _login(client, admin_id)

    ops = client.get('/ai/ops')
    assert ops.status_code == 200
    ops_html = ops.get_data(as_text=True)
    assert 'AI运维看板' in ops_html
    assert 'verify-model' in ops_html
    # 内部 key 与中文标签分离验证：
    # 1) 数据库 AIToolCall.tool_name 保存内部 key warehouse_insights
    with app.app_context():
        tool_call = wms_app.AIToolCall.query.filter_by(tool_name='warehouse_insights').first()
        assert tool_call is not None
        assert tool_call.capability == 'warehouse_insights'
    # 2) 模板使用 ai_agent_label('tool') 过滤器，页面渲染中文标签而非内部 key
    template_path = ROOT / 'app' / 'templates' / 'ai_ops_dashboard.html'
    template_source = template_path.read_text(encoding='utf-8')
    assert "ai_agent_label('tool')" in template_source
    assert '仓库洞察' in ops_html
    assert 'warehouse_insights' not in ops_html

    _login(client, warehouse_id)
    forbidden = client.get('/ai/ops')
    assert forbidden.status_code in (302, 403)

    with app.app_context():
        _set_setting('ai_degrade_local_only', '1')
        wms_app.db.session.commit()
        assert not wms_app._ai_llm_enabled()

        _set_setting('ai_degrade_local_only', '0')
        _set_setting('ai_feature_drafts_enabled', '0')
        wms_app.db.session.commit()
        with app.test_request_context('/_verify/stage5'):
            wms_app.login_user(wms_app.db.session.get(wms_app.User, warehouse_id))
            assert not wms_app._ai_capability_allowed('out_order_draft')
            assert wms_app._ai_capability_allowed('warehouse_insights')

        _set_setting('ai_feature_drafts_enabled', '1')
        _set_setting('ai_feature_agents_enabled', '0')
        wms_app.db.session.commit()
        with app.test_request_context('/_verify/stage5-agent'):
            wms_app.login_user(wms_app.db.session.get(wms_app.User, warehouse_id))
            assert not wms_app._ai_capability_allowed('warehouse_patrol_agent')

        _set_setting('ai_feature_agents_enabled', '1')
        _set_setting('ai_feature_rollout_mode', 'admin_only')
        wms_app.db.session.commit()
        with app.test_request_context('/_verify/stage5-rollout'):
            wms_app.login_user(wms_app.db.session.get(wms_app.User, warehouse_id))
            assert not wms_app._ai_capability_allowed('warehouse_insights')

        _set_setting('ai_feature_rollout_mode', 'all')
        _set_setting('ai_feature_global_enabled', '0')
        wms_app.db.session.commit()

    _login(client, admin_id)
    disabled = client.post(
        '/api/ai/warehouse_assistant',
        json={'message': 'hello', 'request_id': 'stage5-global-disabled'},
    )
    assert disabled.status_code == 200
    disabled_data = disabled.get_json()
    assert disabled_data['status'] == 'success'
    assert '管理员关闭' in disabled_data['reply']

    print('PASS AI-STAGE5-OPS: production flags, degradation, metrics dashboard, and rollout controls are stable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
