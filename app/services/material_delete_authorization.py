"""Require the literal admin account and its current password for archive removal."""
from flask import jsonify
from flask_login import current_user
from werkzeug.security import check_password_hash

from db import db
from rate_limit import is_rate_limited, record_failure, reset


def authorize_material_removal(password):
    from app import User

    user = db.session.get(User, current_user.id, populate_existing=True)
    if not user or user.username != 'admin' or user.role != 'admin' or user.status != 'normal':
        return jsonify(status='error', msg='仅 admin 账号可以删除物料档案（含合并删除）'), 403
    key = 'material-removal-password:' + str(user.id)
    if is_rate_limited(key, 5, 300):
        return jsonify(status='error', msg='密码验证失败次数过多，请5分钟后重试'), 429
    if not password or not check_password_hash(user.password_hash, password):
        record_failure(key, 300)
        return jsonify(status='error', msg='请输入正确的 admin 账号密码，本次未删除任何物料'), 403
    reset(key)
    return None
