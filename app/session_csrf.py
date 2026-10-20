"""双通道接口：只要实际使用 Web 会话，写请求必须验证 CSRF。"""
from flask import current_app, jsonify, request
from flask_login import current_user


def validate_session_write():
    """返回 CSRF 错误响应或 None；Authorization 的存在不能豁免会话。"""
    from flask_wtf.csrf import ValidationError, validate_csrf
    if (not current_app.config.get('WTF_CSRF_ENABLED', True)
            or request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE')
            or not current_user.is_authenticated):
        return None
    payload = request.get_json(silent=True)
    token = (request.headers.get('X-CSRFToken')
             or request.headers.get('X-CSRF-Token')
             or request.form.get('csrf_token')
             or (payload.get('csrf_token') if isinstance(payload, dict) else None))
    try:
        validate_csrf(token)
    except (ValidationError, TypeError):
        return jsonify({'status': 'error', 'success': False,
                        'msg': 'CSRF 校验失败，请刷新页面后重试'}), 400
    return None
