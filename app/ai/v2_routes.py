"""阶段1：AI v2 兼容层路由。

提供 /api/ai/v2/* 端点，使用新的 Provider 和工具模块，
同时保持与 v1 (/api/ai/*) 的 API 兼容。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ai.providers import (
    OpenAICompatibleConfig,
    call_llm_chat,
    call_llm_intent,
    call_llm_vision,
    get_all_breakers_status,
    reset_breakers,
)
from ai.tools.inventory import (
    inventory_health,
    low_stock_report,
    material_query,
    stock_transactions,
    stock_value_analysis,
)
from ai.tools.purchase import (
    pending_purchase_orders,
    purchase_insights,
    supplier_analysis,
)
from ai.tools.navigation import (
    skill_catalog,
    system_api_catalog,
    usage_help,
)

logger = logging.getLogger(__name__)

v2_bp = Blueprint('ai_v2', __name__, url_prefix='/api/ai/v2')


def _safe_int(value, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    """安全解析整型参数。

    系统设置或 query string 中的数字字段可能传入空串、非数字字符串或 None，
    直接 ``int()`` 会抛 ``ValueError``/``TypeError`` 导致 500。这里统一兜底，
    解析失败或越界时回落到 ``default``，并对 ``minimum``/``maximum`` 做夹紧。
    """
    try:
        if value is None or value == '':
            parsed = default
        else:
            parsed = int(str(value))
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None and parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _get_llm_config() -> OpenAICompatibleConfig:
    """从系统设置构建 LLM 配置。"""
    from app import SystemSetting

    def _get(key, default=''):
        s = SystemSetting.query.filter_by(key=key).first()
        return s.value if s and s.value else default

    return OpenAICompatibleConfig(
        enabled=_get('ai_llm_enabled', '0') == '1',
        endpoint=_get('ai_llm_base_url', ''),
        model=_get('ai_llm_model', ''),
        api_key=_get('ai_llm_api_key', ''),
        # 系统设置中可能填入非数字字符串（如 "abc"），用 _safe_int 兜底避免 500
        timeout_seconds=_safe_int(_get('ai_llm_timeout', '30'), 30, minimum=1, maximum=600),
        max_tokens=_safe_int(_get('ai_llm_max_tokens', '512'), 512, minimum=1, maximum=8192),
        vision_enabled=_get('ai_llm_vision_enabled', '0') == '1',
    )


# ---- 工具查询 ----

@v2_bp.get('/tools/inventory/material')
@login_required
def v2_material_query():
    """物料库存查询。"""
    keyword = request.args.get('keyword', '')
    limit = _safe_int(request.args.get('limit', '8'), 8, minimum=1, maximum=50)
    if not keyword:
        return jsonify({'status': 'error', 'msg': 'keyword is required'}), 400
    results = material_query(keyword, limit)
    return jsonify({'status': 'success', 'data': results, 'count': len(results)})


@v2_bp.get('/tools/inventory/transactions')
@login_required
def v2_stock_transactions():
    """物料流水查询。"""
    material_id = request.args.get('material_id', type=int)
    limit = _safe_int(request.args.get('limit', '8'), 8, minimum=1, maximum=50)
    if not material_id:
        return jsonify({'status': 'error', 'msg': 'material_id is required'}), 400
    results = stock_transactions(material_id, limit)
    return jsonify({'status': 'success', 'data': results, 'count': len(results)})


@v2_bp.get('/tools/inventory/health')
@login_required
def v2_inventory_health():
    """库存健康分析。"""
    days = _safe_int(request.args.get('days', '30'), 30, minimum=1, maximum=365)
    limit = _safe_int(request.args.get('limit', '200'), 200, minimum=1, maximum=1000)
    result = inventory_health(days, limit)
    return jsonify({'status': 'success', 'data': result})


@v2_bp.get('/tools/inventory/low-stock')
@login_required
def v2_low_stock():
    """低库存报告。"""
    results = low_stock_report()
    return jsonify({'status': 'success', 'data': results, 'count': len(results)})


@v2_bp.get('/tools/inventory/value')
@login_required
def v2_stock_value():
    """库存价值分析。"""
    category = request.args.get('category', '')
    result = stock_value_analysis(category or None)
    return jsonify({'status': 'success', 'data': result})


@v2_bp.get('/tools/purchase/insights')
@login_required
def v2_purchase_insights():
    """采购工作台概览。"""
    days = _safe_int(request.args.get('days', '30'), 30, minimum=1, maximum=365)
    result = purchase_insights(days)
    return jsonify({'status': 'success', 'data': result})


@v2_bp.get('/tools/purchase/suppliers')
@login_required
def v2_supplier_analysis():
    """供应商分析。"""
    days = _safe_int(request.args.get('days', '90'), 90, minimum=1, maximum=365)
    limit = _safe_int(request.args.get('limit', '12'), 12, minimum=1, maximum=50)
    results = supplier_analysis(days, limit)
    return jsonify({'status': 'success', 'data': results, 'count': len(results)})


@v2_bp.get('/tools/purchase/pending')
@login_required
def v2_pending_purchase_orders():
    """待处理采购单。"""
    limit = _safe_int(request.args.get('limit', '12'), 12, minimum=1, maximum=50)
    results = pending_purchase_orders(limit)
    return jsonify({'status': 'success', 'data': results, 'count': len(results)})


@v2_bp.get('/tools/navigation/skills')
@login_required
def v2_skill_catalog():
    """AI技能清单。"""
    results = skill_catalog()
    return jsonify({'status': 'success', 'data': results, 'count': len(results)})


@v2_bp.get('/tools/navigation/apis')
@login_required
def v2_system_api_catalog():
    """系统API清单。"""
    results = system_api_catalog()
    return jsonify({'status': 'success', 'data': results, 'count': len(results)})


@v2_bp.get('/tools/navigation/help')
@login_required
def v2_usage_help():
    """使用帮助。"""
    topic = request.args.get('topic', '')
    result = usage_help(topic)
    return jsonify({'status': 'success', 'data': result})


# ---- LLM 直接调用（调试/测试用） ----

@v2_bp.post('/llm/chat')
@login_required
def v2_llm_chat():
    """直接调用 LLM 对话（调试用）。"""
    payload = request.get_json(silent=True) or {}
    message = payload.get('message', '')
    if not message:
        return jsonify({'status': 'error', 'msg': 'message is required'}), 400

    config = _get_llm_config()
    if not config.configured:
        return jsonify({'status': 'error', 'msg': 'LLM not configured'}), 503

    system_prompt = payload.get('system_prompt', '你是仓库管理系统的AI助手。')
    reply = call_llm_chat(config, system_prompt, message)
    if not reply:
        return jsonify({'status': 'error', 'msg': 'LLM call failed'}), 502

    return jsonify({'status': 'success', 'data': {'reply': reply}})


@v2_bp.post('/llm/intent')
@login_required
def v2_llm_intent():
    """直接调用 LLM 意图解析（调试用）。"""
    payload = request.get_json(silent=True) or {}
    message = payload.get('message', '')
    if not message:
        return jsonify({'status': 'error', 'msg': 'message is required'}), 400

    config = _get_llm_config()
    if not config.configured:
        return jsonify({'status': 'error', 'msg': 'LLM not configured'}), 503

    system_prompt = payload.get('system_prompt', '你是意图解析器，输出JSON。')
    result = call_llm_intent(config, system_prompt, message)
    if not result:
        return jsonify({'status': 'error', 'msg': 'LLM intent call failed'}), 502

    return jsonify({'status': 'success', 'data': result})


# ---- 熔断器管理 ----

@v2_bp.get('/circuit-breakers')
@login_required
def v2_circuit_breakers():
    """查看熔断器状态（admin only）。"""
    if current_user.role != 'admin':
        return jsonify({'status': 'error', 'msg': 'admin only'}), 403
    return jsonify({'status': 'success', 'data': get_all_breakers_status()})


@v2_bp.post('/circuit-breakers/reset')
@login_required
def v2_reset_circuit_breakers():
    """重置熔断器（admin only）。"""
    if current_user.role != 'admin':
        return jsonify({'status': 'error', 'msg': 'admin only'}), 403
    reset_breakers()
    return jsonify({'status': 'success', 'msg': 'Circuit breakers reset'})


# ---- 反馈 ----

@v2_bp.post('/feedback')
@login_required
def v2_feedback():
    """提交AI回复反馈。"""
    payload = request.get_json(silent=True) or {}
    rating = payload.get('rating', '')
    if rating not in ('thumbs_up', 'thumbs_down'):
        return jsonify({'status': 'error', 'msg': 'rating must be thumbs_up or thumbs_down'}), 400

    from app import db, AIFeedback
    feedback = AIFeedback(
        ai_run_id=payload.get('ai_run_id'),
        user_id=current_user.id,
        rating=rating,
        reason=payload.get('reason', '')[:500],
        reply_snapshot=payload.get('reply_snapshot', '')[:5000],
    )
    db.session.add(feedback)
    db.session.commit()
    return jsonify({'status': 'success', 'data': {'id': feedback.id}})


# ---- 对话历史（持久化） ----

@v2_bp.get('/conversations')
@login_required
def v2_conversations():
    """获取当前用户的对话历史。"""
    from app import db, AIConversation

    session_id = request.args.get('session_id', '')
    limit = _safe_int(request.args.get('limit', '50'), 50, minimum=1, maximum=200)

    query = AIConversation.query.filter_by(user_id=current_user.id)
    if session_id:
        query = query.filter_by(session_id=session_id)

    conversations = query.order_by(AIConversation.created_at.desc()).limit(limit).all()
    data = [
        {
            'id': c.id,
            'session_id': c.session_id,
            'role': c.role,
            'content': c.content,
            'intent': c.intent,
            'created_at': c.created_at.isoformat() if c.created_at else None,
        }
        for c in conversations
    ]
    return jsonify({'status': 'success', 'data': data, 'count': len(data)})


@v2_bp.post('/conversations')
@login_required
def v2_save_conversation():
    """保存对话记录。"""
    from app import db, AIConversation

    payload = request.get_json(silent=True) or {}
    session_id = payload.get('session_id', f'session-{current_user.id}-{datetime.now().strftime("%Y%m%d%H%M%S")}')
    role = payload.get('role', 'user')
    content = payload.get('content', '')

    if role not in ('user', 'assistant', 'system'):
        return jsonify({'status': 'error', 'msg': 'role must be user/assistant/system'}), 400
    if not content:
        return jsonify({'status': 'error', 'msg': 'content is required'}), 400

    conv = AIConversation(
        user_id=current_user.id,
        session_id=session_id,
        role=role,
        content=content[:10000],
        intent=payload.get('intent', '')[:100],
        tool_calls_json=json.dumps(payload['tool_calls'], ensure_ascii=False)[:5000] if payload.get('tool_calls') else None,
    )
    db.session.add(conv)
    db.session.commit()
    return jsonify({'status': 'success', 'data': {'id': conv.id}})
