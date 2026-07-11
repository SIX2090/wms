from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ai.handlers import handle_chat_stream, handle_draft_check, handle_warehouse_assistant
from ai.history import clear_history
from ai.idempotency import ai_idempotent_request
from ai.tools.registry import list_ai_tools_for_role


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
