"""Shared gates for manual media uploads (AI-MOB-MEDIA-FIX-20261114-001)."""
from dataclasses import replace


def _media_actor():
    # Match _web_or_api_required: a session takes precedence over a Bearer token.
    from flask_login import current_user
    from app import get_bearer_user
    return current_user if current_user.is_authenticated else get_bearer_user()


def _media_access_error(capability, *, provider=False):
    """Check the actual actor and current policy again at the provider boundary."""
    from flask import current_app, jsonify
    from app import (db, OperationLog, _ai_global_enabled, _ai_rollout_mode,
                     _ai_allowed_user_ids, _ai_record_rollout_denied_audit)
    from ai.policies import is_ai_capability_allowed_for_role
    from ai.ops.rollout_control import evaluate_rollout_access

    actor = _media_actor()
    if actor is None:
        return jsonify(status='error', success=False, msg='请先登录'), 401
    decision = evaluate_rollout_access(
        capability=capability, role=actor.role, user_id=actor.id, risk_level='read',
        mode=_ai_rollout_mode(), allowed_user_ids=_ai_allowed_user_ids(),
        global_enabled=_ai_global_enabled())
    if decision.allowed and not is_ai_capability_allowed_for_role(capability, actor.role):
        decision = replace(decision, allowed=False, reason='当前账号没有权限使用此 AI 能力', stage='role')
    if not decision.allowed:
        try:
            _ai_record_rollout_denied_audit(decision, 'api')
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.warning('AI 媒体拒绝审计写入失败')
        return jsonify(status='error', success=False, msg=decision.reason), 403
    if provider:
        # This is an invocation audit, not a promise of provider success or stock action.
        # Do not log uploads, transcripts, credentials or provider responses.
        try:
            db.session.add(OperationLog(user_id=actor.id, operation_type='AI媒体调用',
                operation_content=capability, target_type='ai_media'))
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.warning('AI 媒体调用审计写入失败')
            return jsonify(status='error', success=False, msg='调用记录暂不可用，请稍后重试'), 503
    return None


def _media_vision_attempt(capability, denied_responses, *args, **kwargs):
    from app import _ai_call_llm_vision
    denied = _media_access_error(capability, provider=True)
    if denied is not None:
        denied_responses.append(denied)
        return None, None, 'AI 权限或功能开关已变化'
    return _ai_call_llm_vision(*args, **kwargs)
