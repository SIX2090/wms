"""Shared gates for manual media uploads (AI-MOB-MEDIA-FIX-20261114-001)."""
from dataclasses import replace


def _media_actor():
    # Match _web_or_api_required: a session takes precedence over a Bearer token.
    from flask_login import current_user
    from app import get_bearer_user
    return current_user if current_user.is_authenticated else get_bearer_user()


def _media_access_error(capability, *, provider=False):
    """Check actual identity without committing the caller's review transaction."""
    from flask import current_app, jsonify
    from app import (db, _ai_global_enabled, _ai_rollout_mode,
                     _ai_allowed_user_ids, _ai_record_rollout_denied_audit)
    from ai.policies import is_ai_capability_allowed_for_role
    from ai.ops.rollout_control import evaluate_rollout_access

    actor = _media_actor()
    if actor is None:
        return jsonify(status='error', success=False, msg='请先登录'), 401
    actor_id, role = actor.id, actor.role
    decision = evaluate_rollout_access(
        capability=capability, role=role, user_id=actor_id, risk_level='read',
        mode=_ai_rollout_mode(), allowed_user_ids=_ai_allowed_user_ids(),
        global_enabled=_ai_global_enabled())
    if decision.allowed and not is_ai_capability_allowed_for_role(capability, role):
        decision = replace(decision, allowed=False, reason='当前账号没有权限使用此 AI 能力', stage='role')
    if not decision.allowed:
        # A late flag change can reject OCR after its review job was staged.
        # Roll back that business work before committing only the denied audit.
        db.session.rollback()
        try:
            _ai_record_rollout_denied_audit(decision, 'api')
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.warning('AI 媒体拒绝审计写入失败')
        return jsonify(status='error', success=False, msg=decision.reason), 403
    if provider:
        # Provider attempts belong in operational logs, outside the business
        # transaction. A DB commit here would persist a partially built OCR job.
        # No uploads, transcripts, credentials or provider responses are logged.
        try:
            current_app.logger.info(
                'AI媒体调用 user_id=%s role=%s capability=%s', actor_id, role, capability,
                extra={'ai_user_id': actor_id, 'ai_role': role, 'ai_capability': capability})
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
