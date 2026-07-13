#!/usr/bin/env python3
"""验证 AI 审计数据模型 API 路由。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-audit-routes-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


def login_as(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        user = wms_app.User(
            username='audit-routes-user',
            password_hash='not-used',
            role='warehouse',
            status='normal',
        )
        wms_app.db.session.add(user)
        wms_app.db.session.flush()
        user_id = user.id
        wms_app.db.session.commit()

    client = app.test_client()
    login_as(client, user_id)

    print("开始测试 AI 审计 API 路由...")

    # 测试 1: 创建对话
    print("\n[1] 测试创建对话...")
    response = client.post('/api/ai/conversations',
        json={'title': '测试对话'},
        content_type='application/json')
    assert response.status_code == 200, f"status={response.status_code}, data={response.get_json()}"
    data = response.get_json()
    assert data['status'] == 'success'
    conv_id = data['conversation']['id']
    print(f"✓ 创建对话成功: id={conv_id}")

    # 测试 2: 列出对话
    print("\n[2] 测试列出对话...")
    response = client.get('/api/ai/conversations')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert len(data['conversations']) > 0
    print(f"✓ 列出对话成功: {len(data['conversations'])} 个")

    # 测试 3: 获取对话详情
    print("\n[3] 测试获取对话详情...")
    response = client.get(f'/api/ai/conversations/{conv_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    print(f"✓ 获取对话详情成功")

    # 测试 4: 更新对话标题
    print("\n[4] 测试更新对话标题...")
    response = client.put(f'/api/ai/conversations/{conv_id}',
        json={'title': '更新后的标题'},
        content_type='application/json')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    print(f"✓ 更新对话标题成功")

    # 测试 5: 创建消息
    print("\n[5] 测试创建消息...")
    response = client.post(f'/api/ai/conversations/{conv_id}/messages',
        json={'role': 'user', 'content': '你好'},
        content_type='application/json')
    assert response.status_code == 200, f"status={response.status_code}, data={response.get_json()}"
    data = response.get_json()
    assert data['status'] == 'success'
    msg_id = data['message']['id']
    print(f"✓ 创建消息成功: id={msg_id}")

    # 测试 6: 创建反馈
    print("\n[6] 测试创建反馈...")
    response = client.post('/api/ai/feedback',
        json={'rating': 'helpful', 'ai_message_id': msg_id},
        content_type='application/json')
    assert response.status_code == 200, f"status={response.status_code}, data={response.get_json()}"
    data = response.get_json()
    assert data['status'] == 'success'
    print(f"✓ 创建反馈成功")

    # 测试 7: 列出反馈
    print("\n[7] 测试列出反馈...")
    response = client.get('/api/ai/feedback')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert len(data['feedbacks']) > 0
    print(f"✓ 列出反馈成功: {len(data['feedbacks'])} 条")

    # 测试 8: 创建确认令牌
    print("\n[8] 测试创建确认令牌...")
    response = client.post('/api/ai/confirmations',
        json={'confirmation_type': 'draft_creation', 'payload': {'tool': 'in_order_draft'}},
        content_type='application/json')
    assert response.status_code == 200, f"status={response.status_code}, data={response.get_json()}"
    data = response.get_json()
    assert data['status'] == 'success'
    token = data['confirmation']['confirmation_token']
    print(f"✓ 创建确认令牌成功")

    # 测试 9: 获取确认令牌详情
    print("\n[9] 测试获取确认令牌详情...")
    response = client.get(f'/api/ai/confirmations/{token}')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['confirmation']['status'] == 'pending'
    print(f"✓ 获取确认令牌详情成功")

    # 测试 10: 确认令牌
    print("\n[10] 测试确认令牌...")
    response = client.post(f'/api/ai/confirmations/{token}/confirm')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    print(f"✓ 确认令牌成功")

    # 测试 11: 撤销令牌
    print("\n[11] 测试撤销确认令牌...")
    response = client.post('/api/ai/confirmations',
        json={'confirmation_type': 'draft_deletion', 'payload': {}},
        content_type='application/json')
    token2 = response.get_json()['confirmation']['confirmation_token']
    response = client.post(f'/api/ai/confirmations/{token2}/revoke')
    assert response.status_code == 200
    print(f"✓ 撤销确认令牌成功")

    # 测试 12: 归档对话
    print("\n[12] 测试归档对话...")
    response = client.post(f'/api/ai/conversations/{conv_id}/archive')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    print(f"✓ 归档对话成功")

    print("\n" + "=" * 50)
    print("✓ 所有 API 路由测试通过！")
    print("=" * 50)

    # 清理
    print("\n清理测试数据...")
    with app.app_context():
        from ai.models import AIConversation, AIFeedback, AIConfirmation
        AIConversation.query.filter_by(user_id=user_id).delete()
        AIFeedback.query.filter_by(user_id=user_id).delete()
        AIConfirmation.query.filter_by(user_id=user_id).delete()
        wms_app.User.query.filter_by(id=user_id).delete()
        wms_app.db.session.commit()
    print("✓ 测试数据已清理")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
