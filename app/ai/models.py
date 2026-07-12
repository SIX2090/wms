"""AI 审计数据模型定义。

提供 AI 助手运行、工具调用、反馈、确认和文档识别的持久化记录。
所有表均通过 db.create_all() 在应用启动时自动创建。
"""
from __future__ import annotations

from datetime import datetime

from db import db


class AIConversation(db.Model):
    """AI 对话会话。"""
    __tablename__ = 'ai_conversation'
    __table_args__ = (
        db.Index('idx_ai_conversation_user_created', 'user_id', 'created_at'),
        db.Index('idx_ai_conversation_status', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200))
    status = db.Column(db.String(20), nullable=False, default='active')
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    last_activity_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship('User', backref='ai_conversations')

    def touch_activity(self):
        """更新最后活动时间。"""
        self.last_activity_at = datetime.now()


class AIMessage(db.Model):
    """AI 对话消息。"""
    __tablename__ = 'ai_message'
    __table_args__ = (
        db.Index('idx_ai_message_conversation_created', 'conversation_id', 'created_at'),
        db.Index('idx_ai_message_role', 'role'),
    )

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('ai_conversation.id'), nullable=False)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    attachment_summary = db.Column(db.String(500))
    model = db.Column(db.String(100))
    prompt_version = db.Column(db.String(50))
    token_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    conversation = db.relationship('AIConversation', backref=db.backref('messages', cascade='all, delete-orphan'))
    ai_run = db.relationship('AIRun', backref='messages')


class AIFeedback(db.Model):
    """AI 运行反馈。"""
    __tablename__ = 'ai_feedback'
    __table_args__ = (
        db.Index('idx_ai_feedback_run', 'ai_run_id'),
        db.Index('idx_ai_feedback_user_created', 'user_id', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    ai_message_id = db.Column(db.Integer, db.ForeignKey('ai_message.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.String(20), nullable=False)
    error_type = db.Column(db.String(50))
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    ai_run = db.relationship('AIRun', backref='feedbacks')
    ai_message = db.relationship('AIMessage', backref='feedbacks')
    user = db.relationship('User', backref='ai_feedbacks')


class AIConfirmation(db.Model):
    """AI 高风险操作确认令牌。"""
    __tablename__ = 'ai_confirmation'
    __table_args__ = (
        db.Index('idx_ai_confirmation_user_created', 'user_id', 'created_at'),
        db.Index('idx_ai_confirmation_token', 'confirmation_token'),
        db.Index('idx_ai_confirmation_status', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    confirmation_type = db.Column(db.String(50), nullable=False)
    confirmation_token = db.Column(db.String(64), unique=True, nullable=False)
    payload = db.Column(db.Text, nullable=False)
    idempotency_key = db.Column(db.String(80))
    status = db.Column(db.String(20), nullable=False, default='pending')
    expires_at = db.Column(db.DateTime, nullable=False)
    confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    ai_run = db.relationship('AIRun', backref='confirmations')
    user = db.relationship('User', backref='ai_confirmations')

    @property
    def is_expired(self):
        """判断令牌是否已过期。"""
        return self.expires_at and self.expires_at < datetime.now()
