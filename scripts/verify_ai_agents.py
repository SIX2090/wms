from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-agents-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        username = 'agent-verifier-admin'
        wms_app.User.query.filter_by(username=username).delete()
        wms_app.db.session.commit()
        user = wms_app.User(
            username=username,
            password_hash='not-used',
            role='admin',
            status='normal',
        )
        wms_app.db.session.add(user)
        wms_app.db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True

    list_page = client.get('/ai/agent_tasks')
    assert list_page.status_code == 200
    assert 'AI Agent' in list_page.get_data(as_text=True)

    warehouse = client.post('/ai/agent_tasks/run/warehouse_patrol', follow_redirects=False)
    assert warehouse.status_code == 302
    purchase = client.post('/ai/agent_tasks/run/purchase_followup', follow_redirects=False)
    assert purchase.status_code == 302
    chat_warehouse = client.post('/api/ai/warehouse_assistant', json={'message': 'Agent巡检仓库', 'request_id': 'agent-chat-warehouse'}, follow_redirects=False)
    assert chat_warehouse.status_code == 200
    chat_warehouse_data = chat_warehouse.get_json()
    assert chat_warehouse_data['status'] == 'success'
    assert any(action.get('url', '').startswith('/ai/agent_tasks/') for action in chat_warehouse_data.get('actions', []))
    chat_purchase = client.post('/api/ai/warehouse_assistant', json={'message': '采购Agent到货跟进', 'request_id': 'agent-chat-purchase'}, follow_redirects=False)
    assert chat_purchase.status_code == 200
    chat_purchase_data = chat_purchase.get_json()
    assert chat_purchase_data['status'] == 'success'
    assert any(action.get('url', '').startswith('/ai/agent_tasks/') for action in chat_purchase_data.get('actions', []))

    with app.app_context():
        tasks = wms_app.AIAgentTask.query.order_by(wms_app.AIAgentTask.id.asc()).all()
        assert any(task.agent_type == 'warehouse_patrol' and task.status == 'completed' for task in tasks)
        assert any(task.agent_type == 'purchase_followup' and task.status == 'completed' for task in tasks)
        warehouse_task = next(task for task in tasks if task.agent_type == 'warehouse_patrol')
        purchase_task = next(task for task in tasks if task.agent_type == 'purchase_followup')
        assert wms_app.AIAgentStep.query.filter_by(task_id=warehouse_task.id).count() >= 4
        assert wms_app.AIAgentStep.query.filter_by(task_id=purchase_task.id).count() >= 4
        assert wms_app.AIAgentStep.query.filter_by(task_id=purchase_task.id, risk_level='draft').count() == 1
        assert wms_app.AIAgentTask.query.filter_by(agent_type='warehouse_patrol').count() >= 2
        assert wms_app.AIAgentTask.query.filter_by(agent_type='purchase_followup').count() >= 2
        warehouse_id = warehouse_task.id
        purchase_id = purchase_task.id

    warehouse_detail = client.get(f'/ai/agent_tasks/{warehouse_id}')
    assert warehouse_detail.status_code == 200
    assert 'Stock risk scan' in warehouse_detail.get_data(as_text=True)
    purchase_detail = client.get(f'/ai/agent_tasks/{purchase_id}')
    assert purchase_detail.status_code == 200
    purchase_html = purchase_detail.get_data(as_text=True)
    assert 'Low-stock replenishment scan' in purchase_html
    assert 'draft' in purchase_html

    print('PASS AI-AGENTS: controlled warehouse and purchase agents create auditable tasks and steps')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
