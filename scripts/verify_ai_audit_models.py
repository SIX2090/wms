#!/usr/bin/env python3
"""验证 AI 审计数据模型是否正确创建和工作。"""
import os
import sys

# 添加 app 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app import app, db, initialize_database
from ai.models import AIConversation, AIMessage, AIFeedback, AIConfirmation
from ai.audit import (
    create_conversation,
    get_conversation,
    list_conversations,
    create_message,
    list_messages,
    create_feedback,
    list_feedbacks,
    create_confirmation,
    get_confirmation,
    confirm_token,
    revoke_confirmation,
)


def test_models():
    """测试 AI 审计数据模型。"""
    print("开始测试 AI 审计数据模型...")
    
    with app.app_context():
        # 初始化数据库（创建表）
        print("初始化数据库...")
        initialize_database()
        print("数据库初始化完成\n")
        # 测试 1: 创建对话
        print("\n[1] 测试创建对话...")
        conv = create_conversation(user_id=1, title="测试对话")
        print(f"✓ 创建对话成功: id={conv.id}, title={conv.title}")
        
        # 测试 2: 获取对话
        print("\n[2] 测试获取对话...")
        fetched_conv = get_conversation(conv.id)
        assert fetched_conv is not None, "对话不存在"
        assert fetched_conv.id == conv.id, "对话 ID 不匹配"
        print(f"✓ 获取对话成功: id={fetched_conv.id}")
        
        # 测试 3: 列出对话
        print("\n[3] 测试列出对话...")
        convs = list_conversations(user_id=1)
        assert len(convs) > 0, "对话列表为空"
        print(f"✓ 列出对话成功: 共 {len(convs)} 个对话")
        
        # 测试 4: 创建消息
        print("\n[4] 测试创建消息...")
        msg1 = create_message(
            conversation_id=conv.id,
            role="user",
            content="你好，我想查询库存",
        )
        msg2 = create_message(
            conversation_id=conv.id,
            role="assistant",
            content="好的，我来帮您查询库存信息。",
            model="gpt-4",
            prompt_version="legacy-v1",
        )
        print(f"✓ 创建消息成功: user_msg_id={msg1.id}, assistant_msg_id={msg2.id}")
        
        # 测试 5: 列出消息
        print("\n[5] 测试列出消息...")
        messages = list_messages(conv.id)
        assert len(messages) == 2, f"消息数量不正确: 期望 2，实际 {len(messages)}"
        assert messages[0].role == "user", "第一条消息角色不正确"
        assert messages[1].role == "assistant", "第二条消息角色不正确"
        print(f"✓ 列出消息成功: 共 {len(messages)} 条消息")
        
        # 测试 6: 创建反馈
        print("\n[6] 测试创建反馈...")
        feedback = create_feedback(
            user_id=1,
            rating="helpful",
            ai_message_id=msg2.id,
            note="回答很准确",
        )
        print(f"✓ 创建反馈成功: id={feedback.id}, rating={feedback.rating}")
        
        # 测试 7: 列出反馈
        print("\n[7] 测试列出反馈...")
        feedbacks = list_feedbacks(user_id=1)
        assert len(feedbacks) > 0, "反馈列表为空"
        print(f"✓ 列出反馈成功: 共 {len(feedbacks)} 条反馈")
        
        # 测试 8: 创建确认令牌
        print("\n[8] 测试创建确认令牌...")
        confirmation = create_confirmation(
            user_id=1,
            confirmation_type="draft_creation",
            payload={"tool": "in_order_draft", "material_id": 1, "quantity": 100},
            expires_minutes=30,
        )
        print(f"✓ 创建确认令牌成功: token={confirmation.confirmation_token[:16]}...")
        
        # 测试 9: 获取确认令牌
        print("\n[9] 测试获取确认令牌...")
        fetched_conf = get_confirmation(confirmation.confirmation_token)
        assert fetched_conf is not None, "确认令牌不存在"
        assert fetched_conf.status == "pending", "确认令牌状态不正确"
        print(f"✓ 获取确认令牌成功: status={fetched_conf.status}")
        
        # 测试 10: 确认令牌
        print("\n[10] 测试确认令牌...")
        success, error = confirm_token(confirmation.confirmation_token, user_id=1)
        assert success, f"确认令牌失败: {error}"
        print(f"✓ 确认令牌成功: status={confirmation.status}")
        
        # 测试 11: 创建并撤销另一个令牌
        print("\n[11] 测试撤销确认令牌...")
        conf2 = create_confirmation(
            user_id=1,
            confirmation_type="draft_deletion",
            payload={"tool": "out_order_draft", "order_id": 1},
        )
        revoked = revoke_confirmation(conf2.confirmation_token, user_id=1)
        assert revoked, "撤销确认令牌失败"
        print(f"✓ 撤销确认令牌成功: status={conf2.status}")
        
        # 测试 12: 验证对话活动时间更新
        print("\n[12] 测试对话活动时间更新...")
        updated_conv = get_conversation(conv.id)
        assert updated_conv.last_activity_at >= conv.created_at, "活动时间未更新"
        print(f"✓ 对话活动时间已更新: {updated_conv.last_activity_at}")
        
        print("\n" + "=" * 50)
        print("✓ 所有测试通过！")
        print("=" * 50)
        
        # 清理测试数据
        print("\n清理测试数据...")
        db.session.delete(conv)
        db.session.delete(feedback)
        db.session.delete(confirmation)
        db.session.delete(conf2)
        db.session.commit()
        print("✓ 测试数据已清理")


if __name__ == "__main__":
    try:
        test_models()
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
