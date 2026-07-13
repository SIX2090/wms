from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ai.handlers import handle_chat_stream, handle_draft_check, handle_warehouse_assistant
from ai.history import clear_history
from ai.idempotency import ai_idempotent_request
from ai.tools.registry import list_ai_tools_for_role
from ai.audit import (
    create_conversation,
    get_conversation,
    list_conversations,
    update_conversation_title,
    archive_conversation,
    create_message,
    list_messages,
    create_feedback,
    list_feedbacks,
    create_confirmation,
    get_confirmation,
    confirm_token,
    revoke_confirmation,
)


ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')


@ai_bp.get('/tools')
@login_required
def tools():
    """Return AI tool metadata available to the current user's role."""
    return jsonify({
        'status': 'success',
        'role': current_user.role,
        'tools': list_ai_tools_for_role(current_user.role),
    })


@ai_bp.post('/chat/clear')
@login_required
def chat_clear():
    """Clear the current user's AI chat history."""
    user_id = current_user.id if current_user.is_authenticated else 0
    clear_history(user_id)
    return jsonify({'status': 'success', 'msg': '已清空对话历史'})


@ai_bp.post('/draft_check')
@login_required
def draft_check():
    """Run the current page draft pre-submit check."""
    payload = request.get_json(silent=True) or {}
    return handle_draft_check(payload)


@ai_bp.post('/warehouse_assistant')
@login_required
@ai_idempotent_request
def warehouse_assistant():
    """Handle the main AI assistant request."""
    payload = request.get_json(silent=True) or {}
    return handle_warehouse_assistant(payload)


@ai_bp.post('/chat/stream')
@login_required
@ai_idempotent_request
def chat_stream():
    """Handle the SSE AI chat request."""
    payload = request.get_json(silent=True) or {}
    return handle_chat_stream(payload)


# ──────────────────────────────────────────────
# 对话历史管理 API
# ──────────────────────────────────────────────

@ai_bp.get('/conversations')
@login_required
def conversations_list():
    """列出当前用户的所有对话会话。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    limit = request.args.get('limit', 50, type=int)
    convs = list_conversations(user_id, limit=limit)
    return jsonify({
        'status': 'success',
        'conversations': [
            {
                'id': c.id,
                'title': c.title,
                'status': c.status,
                'created_at': c.created_at.isoformat() if c.created_at else None,
                'last_activity_at': c.last_activity_at.isoformat() if c.last_activity_at else None,
            }
            for c in convs
        ],
    })


@ai_bp.get('/conversations/<int:conversation_id>')
@login_required
def conversation_detail(conversation_id):
    """获取单个对话的详细信息和消息列表。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    conv = get_conversation(conversation_id, user_id=user_id)
    if not conv:
        return jsonify({'status': 'error', 'msg': '对话不存在'}), 404

    limit = request.args.get('limit', 100, type=int)
    messages = list_messages(conversation_id, limit=limit)

    return jsonify({
        'status': 'success',
        'conversation': {
            'id': conv.id,
            'title': conv.title,
            'status': conv.status,
            'created_at': conv.created_at.isoformat() if conv.created_at else None,
            'last_activity_at': conv.last_activity_at.isoformat() if conv.last_activity_at else None,
        },
        'messages': [
            {
                'id': m.id,
                'role': m.role,
                'content': m.content,
                'attachment_summary': m.attachment_summary,
                'model': m.model,
                'prompt_version': m.prompt_version,
                'token_count': m.token_count,
                'created_at': m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    })


@ai_bp.post('/conversations')
@login_required
def conversation_create():
    """创建新的对话会话。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    payload = request.get_json(silent=True) or {}
    title = payload.get('title', '').strip() or None

    conv = create_conversation(user_id, title=title)
    return jsonify({
        'status': 'success',
        'conversation': {
            'id': conv.id,
            'title': conv.title,
            'status': conv.status,
            'created_at': conv.created_at.isoformat() if conv.created_at else None,
        },
    })


@ai_bp.put('/conversations/<int:conversation_id>')
@login_required
def conversation_update(conversation_id):
    """更新对话标题。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    payload = request.get_json(silent=True) or {}
    title = payload.get('title', '').strip()

    if not title:
        return jsonify({'status': 'error', 'msg': '标题不能为空'}), 400

    success = update_conversation_title(conversation_id, title, user_id=user_id)
    if not success:
        return jsonify({'status': 'error', 'msg': '对话不存在'}), 404

    return jsonify({'status': 'success', 'msg': '标题已更新'})


@ai_bp.post('/conversations/<int:conversation_id>/archive')
@login_required
def conversation_archive(conversation_id):
    """归档对话会话。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    success = archive_conversation(conversation_id, user_id=user_id)
    if not success:
        return jsonify({'status': 'error', 'msg': '对话不存在'}), 404

    return jsonify({'status': 'success', 'msg': '对话已归档'})


@ai_bp.post('/conversations/<int:conversation_id>/messages')
@login_required
def message_create(conversation_id):
    """在对话中创建新消息。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    conv = get_conversation(conversation_id, user_id=user_id)
    if not conv:
        return jsonify({'status': 'error', 'msg': '对话不存在'}), 404

    payload = request.get_json(silent=True) or {}
    role = payload.get('role', '').strip()
    content = payload.get('content', '').strip()

    if not role or not content:
        return jsonify({'status': 'error', 'msg': '角色和内容不能为空'}), 400

    msg = create_message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        ai_run_id=payload.get('ai_run_id'),
        attachment_summary=payload.get('attachment_summary'),
        model=payload.get('model'),
        prompt_version=payload.get('prompt_version'),
        token_count=payload.get('token_count', 0),
    )

    return jsonify({
        'status': 'success',
        'message': {
            'id': msg.id,
            'role': msg.role,
            'content': msg.content,
            'created_at': msg.created_at.isoformat() if msg.created_at else None,
        },
    })


# ──────────────────────────────────────────────
# 反馈收集 API
# ──────────────────────────────────────────────

@ai_bp.post('/feedback')
@login_required
def feedback_create():
    """创建 AI 运行反馈。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    payload = request.get_json(silent=True) or {}

    rating = payload.get('rating', '').strip()
    if not rating:
        return jsonify({'status': 'error', 'msg': '评价不能为空'}), 400

    fb = create_feedback(
        user_id=user_id,
        rating=rating,
        ai_run_id=payload.get('ai_run_id'),
        ai_message_id=payload.get('ai_message_id'),
        error_type=payload.get('error_type'),
        note=payload.get('note'),
    )

    return jsonify({
        'status': 'success',
        'feedback': {
            'id': fb.id,
            'rating': fb.rating,
            'error_type': fb.error_type,
            'created_at': fb.created_at.isoformat() if fb.created_at else None,
        },
    })


@ai_bp.get('/feedback')
@login_required
def feedback_list():
    """列出当前用户的反馈记录。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    limit = request.args.get('limit', 50, type=int)
    feedbacks = list_feedbacks(user_id=user_id, limit=limit)

    return jsonify({
        'status': 'success',
        'feedbacks': [
            {
                'id': f.id,
                'rating': f.rating,
                'error_type': f.error_type,
                'note': f.note,
                'ai_run_id': f.ai_run_id,
                'ai_message_id': f.ai_message_id,
                'created_at': f.created_at.isoformat() if f.created_at else None,
            }
            for f in feedbacks
        ],
    })


# ──────────────────────────────────────────────
# 确认令牌 API
# ──────────────────────────────────────────────

@ai_bp.post('/confirmations')
@login_required
def confirmation_create():
    """创建高风险操作确认令牌。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    payload = request.get_json(silent=True) or {}

    confirmation_type = payload.get('confirmation_type', '').strip()
    confirmation_payload = payload.get('payload', {})

    if not confirmation_type:
        return jsonify({'status': 'error', 'msg': '确认类型不能为空'}), 400

    if not isinstance(confirmation_payload, dict):
        return jsonify({'status': 'error', 'msg': 'payload 必须是对象'}), 400

    conf = create_confirmation(
        user_id=user_id,
        confirmation_type=confirmation_type,
        payload=confirmation_payload,
        ai_run_id=payload.get('ai_run_id'),
        idempotency_key=payload.get('idempotency_key'),
        expires_minutes=payload.get('expires_minutes', 30),
    )

    return jsonify({
        'status': 'success',
        'confirmation': {
            'id': conf.id,
            'confirmation_token': conf.confirmation_token,
            'confirmation_type': conf.confirmation_type,
            'status': conf.status,
            'expires_at': conf.expires_at.isoformat() if conf.expires_at else None,
            'created_at': conf.created_at.isoformat() if conf.created_at else None,
        },
    })


@ai_bp.get('/confirmations/<token>')
@login_required
def confirmation_detail(token):
    """获取确认令牌的详细信息。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    conf = get_confirmation(token)

    if not conf or conf.user_id != user_id:
        return jsonify({'status': 'error', 'msg': '确认令牌不存在'}), 404

    return jsonify({
        'status': 'success',
        'confirmation': {
            'id': conf.id,
            'confirmation_token': conf.confirmation_token,
            'confirmation_type': conf.confirmation_type,
            'payload': conf.payload,
            'idempotency_key': conf.idempotency_key,
            'status': conf.status,
            'is_expired': conf.is_expired,
            'expires_at': conf.expires_at.isoformat() if conf.expires_at else None,
            'confirmed_at': conf.confirmed_at.isoformat() if conf.confirmed_at else None,
            'created_at': conf.created_at.isoformat() if conf.created_at else None,
        },
    })


@ai_bp.post('/confirmations/<token>/confirm')
@login_required
def confirmation_confirm(token):
    """确认令牌并标记为已使用。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    success, error = confirm_token(token, user_id)

    if not success:
        return jsonify({'status': 'error', 'msg': error}), 400

    return jsonify({'status': 'success', 'msg': '确认成功'})


@ai_bp.post('/confirmations/<token>/revoke')
@login_required
def confirmation_revoke(token):
    """撤销确认令牌。"""
    user_id = current_user.id if current_user.is_authenticated else 0
    success = revoke_confirmation(token, user_id)

    if not success:
        return jsonify({'status': 'error', 'msg': '撤销失败，令牌不存在或已使用'}), 400

    return jsonify({'status': 'success', 'msg': '令牌已撤销'})
