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
        step_model = wms_app.AIAgentStep
        warehouse_steps = (step_model.query.filter_by(task_id=warehouse_task.id)
                           .order_by(step_model.step_no.asc()).all())
        purchase_steps = (step_model.query.filter_by(task_id=purchase_task.id)
                          .order_by(step_model.step_no.asc()).all())
        # 数据库内部语义（与展示语言无关）：步骤数、序号连续、tool/risk/status 结构化字段
        assert len(warehouse_steps) >= 4
        assert len(purchase_steps) >= 4
        assert [step.step_no for step in warehouse_steps] == list(range(1, len(warehouse_steps) + 1))
        assert [step.step_no for step in purchase_steps] == list(range(1, len(purchase_steps) + 1))
        assert all(step.status == 'completed' for step in warehouse_steps + purchase_steps)
        assert any(step.tool_name == 'warehouse_insights' for step in warehouse_steps)
        assert all(step.name for step in warehouse_steps + purchase_steps)
        purchase_draft_steps = [step for step in purchase_steps if step.risk_level == 'draft']
        assert len(purchase_draft_steps) == 1
        assert purchase_draft_steps[0].tool_name == 'purchase_request_draft'
        assert wms_app.AIAgentTask.query.filter_by(agent_type='warehouse_patrol').count() >= 2
        assert wms_app.AIAgentTask.query.filter_by(agent_type='purchase_followup').count() >= 2
        warehouse_id = warehouse_task.id
        purchase_id = purchase_task.id
        warehouse_step_names = [step.name for step in warehouse_steps]
        purchase_step_names = [step.name for step in purchase_steps]
        # 渲染层过滤器契约：历史英文内部文案必须经 ai_agent_text/ai_agent_label 翻译为中文
        text_filter = app.jinja_env.filters['ai_agent_text']
        label_filter = app.jinja_env.filters['ai_agent_label']
        assert text_filter('Stock risk scan') == '库存风险扫描'
        assert text_filter('Low-stock replenishment scan') == '低库存补货扫描'
        assert label_filter('draft', 'risk') == '草稿'

    # 任务详情页中文渲染契约：数据库中的中文步骤名可见，旧英文内部文案不得泄露
    warehouse_detail = client.get(f'/ai/agent_tasks/{warehouse_id}')
    assert warehouse_detail.status_code == 200
    warehouse_html = warehouse_detail.get_data(as_text=True)
    for step_name in warehouse_step_names:
        assert step_name in warehouse_html
    assert 'Stock risk scan' not in warehouse_html

    purchase_detail = client.get(f'/ai/agent_tasks/{purchase_id}')
    assert purchase_detail.status_code == 200
    purchase_html = purchase_detail.get_data(as_text=True)
    for step_name in purchase_step_names:
        assert step_name in purchase_html
    assert 'Low-stock replenishment scan' not in purchase_html
    # risk_level='draft' 经 ai_agent_label('risk') 渲染为中文「草稿」单元格
    assert '草稿</td>' in purchase_html

    print('PASS AI-AGENTS: controlled warehouse and purchase agents create auditable tasks and steps')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
