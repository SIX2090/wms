"""AI 审计数据模型 CRUD 服务函数。

提供对话、消息、反馈和确认令牌的持久化操作。
所有写操作均通过 db.session 管理，确保事务一致性。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from db import db
from ai.models import AIConversation, AIMessage, AIFeedback, AIConfirmation


# ──────────────────────────────────────────────
# 对话管理
# ──────────────────────────────────────────────

def create_conversation(user_id: int, title: str | None = None) -> AIConversation:
    """创建新的 AI 对话会话。"""
    conv = AIConversation(user_id=user_id, title=title)
    db.session.add(conv)
    db.session.commit()
    return conv


def get_conversation(conversation_id: int, user_id: int | None = None) -> AIConversation | None:
    """获取对话会话，可选按用户过滤。"""
    query = AIConversation.query.filter_by(id=conversation_id)
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.first()


def list_conversations(user_id: int, limit: int = 50) -> list[AIConversation]:
    """列出用户的对话会话，按最后活动时间降序。"""
    return (
        AIConversation.query
        .filter_by(user_id=user_id)
        .order_by(AIConversation.last_activity_at.desc())
        .limit(limit)
        .all()
    )


def update_conversation_title(conversation_id: int, title: str, user_id: int | None = None) -> bool:
    """更新对话标题。"""
    conv = get_conversation(conversation_id, user_id)
    if not conv:
        return False
    conv.title = title
    conv.touch_activity()
    db.session.commit()
    return True


def archive_conversation(conversation_id: int, user_id: int | None = None) -> bool:
    """归档对话会话。"""
    conv = get_conversation(conversation_id, user_id)
    if not conv:
        return False
    conv.status = 'archived'
    db.session.commit()
    return True


# ──────────────────────────────────────────────
# 消息管理
# ──────────────────────────────────────────────

def create_message(
    conversation_id: int,
    role: str,
    content: str,
    ai_run_id: int | None = None,
    attachment_summary: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    token_count: int = 0,
) -> AIMessage:
    """创建对话消息。"""
    msg = AIMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        ai_run_id=ai_run_id,
        attachment_summary=attachment_summary,
        model=model,
        prompt_version=prompt_version,
        token_count=token_count,
    )
    db.session.add(msg)
    # 更新对话最后活动时间
    conv = AIConversation.query.get(conversation_id)
    if conv:
        conv.touch_activity()
    db.session.commit()
    return msg


def list_messages(
    conversation_id: int,
    limit: int = 100,
    user_id: int | None = None,
) -> list[AIMessage]:
    """列出对话消息，按创建时间升序。

    传入 user_id 时，会先校验对话归属当前用户，避免越权读取他人对话消息。
    """
    if user_id is not None:
        conv = AIConversation.query.filter_by(
            id=conversation_id, user_id=user_id
        ).first()
        if not conv:
            return []
    return (
        AIMessage.query
        .filter_by(conversation_id=conversation_id)
        .order_by(AIMessage.created_at.asc())
        .limit(limit)
        .all()
    )


def get_message(message_id: int, user_id: int | None = None) -> AIMessage | None:
    """获取单条消息。

    传入 user_id 时，会校验消息所属对话的 user_id 与之一致，避免越权读取。
    """
    msg = AIMessage.query.get(message_id)
    if not msg:
        return None
    if user_id is not None:
        conv = AIConversation.query.get(msg.conversation_id)
        if not conv or conv.user_id != user_id:
            return None
    return msg


# ──────────────────────────────────────────────
# 反馈管理
# ──────────────────────────────────────────────

def create_feedback(
    user_id: int,
    rating: str,
    ai_run_id: int | None = None,
    ai_message_id: int | None = None,
    error_type: str | None = None,
    note: str | None = None,
) -> AIFeedback:
    """创建 AI 运行反馈。"""
    fb = AIFeedback(
        user_id=user_id,
        rating=rating,
        ai_run_id=ai_run_id,
        ai_message_id=ai_message_id,
        error_type=error_type,
        note=note,
    )
    db.session.add(fb)
    db.session.commit()
    return fb


def list_feedbacks(user_id: int | None = None, limit: int = 50) -> list[AIFeedback]:
    """列出反馈，可选按用户过滤。"""
    query = AIFeedback.query
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    return query.order_by(AIFeedback.created_at.desc()).limit(limit).all()


# ──────────────────────────────────────────────
# 确认令牌管理
# ──────────────────────────────────────────────

def create_confirmation(
    user_id: int,
    confirmation_type: str,
    payload: dict[str, Any],
    ai_run_id: int | None = None,
    idempotency_key: str | None = None,
    expires_minutes: int = 30,
) -> AIConfirmation:
    """创建高风险操作确认令牌。"""
    import secrets
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(minutes=expires_minutes)
    
    import json
    payload_json = json.dumps(payload, ensure_ascii=False)
    
    conf = AIConfirmation(
        user_id=user_id,
        ai_run_id=ai_run_id,
        confirmation_type=confirmation_type,
        confirmation_token=token,
        payload=payload_json,
        idempotency_key=idempotency_key,
        expires_at=expires_at,
    )
    db.session.add(conf)
    db.session.commit()
    return conf


def get_confirmation(token: str) -> AIConfirmation | None:
    """通过令牌获取确认记录。"""
    return AIConfirmation.query.filter_by(confirmation_token=token).first()


def confirm_token(token: str, user_id: int) -> tuple[bool, str]:
    """确认令牌并标记为已使用。

    返回 (成功标志, 错误消息)。
    """
    conf = get_confirmation(token)
    if not conf:
        return False, '确认令牌不存在'
    if conf.user_id != user_id:
        return False, '确认令牌不属于当前用户'
    if conf.status != 'pending':
        return False, f'确认令牌已{conf.status}'
    if conf.is_expired:
        return False, '确认令牌已过期'
    
    conf.status = 'confirmed'
    conf.confirmed_at = datetime.now()
    db.session.commit()
    return True, ''


def revoke_confirmation(token: str, user_id: int) -> bool:
    """撤销确认令牌。"""
    conf = get_confirmation(token)
    if not conf or conf.user_id != user_id or conf.status != 'pending':
        return False
    conf.status = 'revoked'
    db.session.commit()
    return True
