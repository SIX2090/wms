#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用户 / 认证 / 审计 / 系统配置模型。

ARCH-MODELS-01（2026-09-15）自 app/app.py 模型区迁入，类定义逐字保留。
统一平铺导入 ``from db import db``（与 document_evidence.py 先例一致）。
"""

from db import db
from datetime import datetime
from datetime import timedelta
from flask_login import UserMixin

__all__ = [
    'ApiToken',
    'LoginLog',
    'MobileApiRequest',
    'Notification',
    'OperationAudit',
    'SystemSetting',
    'User',
    'UserFieldConfig',
]


class User(UserMixin, db.Model):
    """System user."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)  # Username
    password_hash = db.Column(db.String(120), nullable=False)  # Password
    # Role: admin/warehouse/purchase/sales/production/finance/user
    # AI-WMS-FINANCE-ROLE：finance 为只读角色，写操作由 enforce_read_only_role 统一拦截
    role = db.Column(db.String(20), default='user')
    status = db.Column(db.String(20), default='normal')  # Status
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    # Login security fields
    login_failed_count = db.Column(db.Integer, default=0)  # Failed login count
    locked_until = db.Column(db.DateTime)  # Lock end time
    last_login_at = db.Column(db.DateTime)  # Last login time
    last_login_ip = db.Column(db.String(50))  # Last login IP
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    login_lock_ip = db.Column(db.String(50))
    login_ip_failed_count = db.Column(db.Integer, default=0)
    login_ip_locked_until = db.Column(db.DateTime)

    # BUG-F02-06 修复：普通用户/管理员自助资料字段
    # 仅限本人修改，不参与登录/权限判定；不在 edit_user 中提供
    email = db.Column(db.String(200))
    phone = db.Column(db.String(30))
    bio = db.Column(db.String(500))

    # Flask-Login integration
    @property
    def is_active(self):
        return self.status not in {'disabled', 'inactive'}

    @property
    def is_locked(self):
        """Return whether the account is currently locked."""
        if self.locked_until and self.locked_until > datetime.now():
            return True
        return False

    # no-test: reason=ARCH-MODELS-01 自 app.py 原样迁移，登录锁定行为由既有测试覆盖
    def reset_failed_count(self):
        """Clear failed login state."""
        self.login_failed_count = 0
        self.locked_until = None
        self.login_lock_ip = None
        self.login_ip_failed_count = 0
        self.login_ip_locked_until = None

    # no-test: reason=ARCH-MODELS-01 自 app.py 原样迁移，登录锁定行为由既有测试覆盖
    def is_locked_for(self, ip_address):
        """Lock failed-login attempts per account and source IP, avoiding account-wide DoS."""
        if self.is_locked:
            return True
        return bool(
            ip_address and self.login_lock_ip == ip_address
            and self.login_ip_locked_until
            and self.login_ip_locked_until > datetime.now()
        )

    # no-test: reason=ARCH-MODELS-01 自 app.py 原样迁移，登录锁定行为由既有测试覆盖
    def login_lock_remaining(self, ip_address):
        deadline = self.locked_until if self.is_locked else None
        if not deadline and self.login_lock_ip == ip_address and self.login_ip_locked_until:
            deadline = self.login_ip_locked_until
        return max(1, int((deadline - datetime.now()).total_seconds() // 60)) if deadline else 0

    # no-test: reason=ARCH-MODELS-01 自 app.py 原样迁移，登录锁定行为由既有测试覆盖
    def login_lock_remaining_seconds(self, ip_address):
        """BUG-2026-07-28-011 修复：返回精确剩余秒数，供前端做倒计时。"""
        deadline = self.locked_until if self.is_locked else None
        if not deadline and self.login_lock_ip == ip_address and self.login_ip_locked_until:
            deadline = self.login_ip_locked_until
        if not deadline:
            return 0
        return max(1, int((deadline - datetime.now()).total_seconds()))

    # no-test: reason=ARCH-MODELS-01 自 app.py 原样迁移，登录锁定行为由既有测试覆盖
    def ip_failed_count_for(self, ip_address):
        """BUG-2026-07-28-011 修复：返回当前 IP 的失败次数（同 IP 累计，跨账号不累计）。
        锁定后从 0 重置，但前端展示仍希望看到累计次数以警示用户。
        """
        if not ip_address:
            return 0
        if self.login_lock_ip != ip_address:
            return 0
        # 已锁定时仍展示累计失败次数（提示用户风险），但若锁定已自然过期则清零
        if self.login_ip_locked_until and self.login_ip_locked_until > datetime.now():
            return self.login_ip_failed_count or 0
        if self.login_ip_locked_until and self.login_ip_locked_until <= datetime.now():
            return 0
        return self.login_ip_failed_count or 0

    # no-test: reason=ARCH-MODELS-01 自 app.py 原样迁移，登录锁定行为由既有测试覆盖
    def increment_failed_count(self, ip_address=None):
        """Increase failed login count and lock account if needed."""
        # ARCH-MODELS-01：登录安全配置函数留守 app.py，运行时延迟导入避免循环依赖。
        from app import account_lock_minutes, max_login_failures
        if self.locked_until and self.locked_until <= datetime.now():
            self.login_failed_count = 0
            self.locked_until = None
        # 保留历史字段用于审计，但新失败锁定按账号+来源 IP 计算，避免任意来源锁死账号。
        self.login_failed_count = (self.login_failed_count or 0) + 1
        if ip_address:
            if self.login_lock_ip != ip_address or (
                    self.login_ip_locked_until and self.login_ip_locked_until <= datetime.now()):
                self.login_lock_ip = ip_address
                self.login_ip_failed_count = 0
                self.login_ip_locked_until = None
            self.login_ip_failed_count = (self.login_ip_failed_count or 0) + 1
            if self.login_ip_failed_count >= max_login_failures():
                self.login_ip_locked_until = datetime.now() + timedelta(minutes=account_lock_minutes())
        elif self.login_failed_count >= max_login_failures():
            self.locked_until = datetime.now() + timedelta(minutes=account_lock_minutes())


class LoginLog(db.Model):
    """Login audit log."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    username = db.Column(db.String(80))  # Username
    login_time = db.Column(db.DateTime, default=datetime.now)
    login_ip = db.Column(db.String(50))  # IP
    user_agent = db.Column(db.String(500))  # User agent
    status = db.Column(db.String(20))  # success/failed
    fail_reason = db.Column(db.String(200))  # Failure reason


class ApiToken(db.Model):
    """Bearer token for native app API access."""
    __tablename__ = 'api_token'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_used_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='api_tokens')


class MobileApiRequest(db.Model):
    """Idempotency records for native mobile warehouse submissions."""
    __tablename__ = 'mobile_api_request'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'endpoint', 'request_key', name='uix_mobile_api_request_key'),
        db.Index('idx_mobile_api_request_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.String(40), nullable=False)
    request_key = db.Column(db.String(120), nullable=False)
    status_code = db.Column(db.Integer, nullable=False, default=200)
    response_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship('User', backref='mobile_api_requests')


class OperationAudit(db.Model):
    """Operation audit record."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    username = db.Column(db.String(80))
    operation = db.Column(db.String(50))  # Operation type: delete/complete/update
    target_type = db.Column(db.String(50))  # Target type: in_order/out_order/material
    target_id = db.Column(db.Integer)
    target_name = db.Column(db.String(200))  # Target name or order number
    old_data = db.Column(db.Text)  # Previous data JSON
    new_data = db.Column(db.Text)  # New data JSON
    operation_time = db.Column(db.DateTime, default=datetime.now)
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    status = db.Column(db.String(20))  # success/failed
    reason = db.Column(db.String(200))  # Operation reason


class Notification(db.Model):
    """系统通知记录"""
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class UserFieldConfig(db.Model):
    """用户字段配置 - 用于存储用户对单据明细表格的自定义配置"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    page_type = db.Column(db.String(50), nullable=False)  # 页面类型: in_order_add, in_order_detail, out_order_add, out_order_detail, check_detail 等
    field_key = db.Column(db.String(50), nullable=False)  # 字段标识: code, name, spec, unit, quantity, price, amount 等
    field_label = db.Column(db.String(100))  # 自定义显示名称
    width = db.Column(db.Integer, default=0)  # 自定义宽度(像素), 0表示自动
    visible = db.Column(db.Boolean, default=True)  # 是否显示
    sort_order = db.Column(db.Integer, default=0)  # 排序顺序
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    user = db.relationship('User', backref='field_configs')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'page_type', 'field_key', name='uix_user_field_config'),
    )


class SystemSetting(db.Model):
    """System-level settings stored in the database."""
    __tablename__ = 'system_setting'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), default='')
    remark = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
