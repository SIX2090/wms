#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信分享模型（配置 / 日志）。

ARCH-MODELS-01（2026-09-15）自 app/app.py 模型区迁入，类定义逐字保留。
统一平铺导入 ``from db import db``（与 document_evidence.py 先例一致）。
"""

from db import db
from datetime import datetime
from datetime import date

__all__ = [
    'WechatShareConfig',
    'WechatShareLog',
]


class WechatShareConfig(db.Model):
    """Personal WeChat sharing configuration."""
    __tablename__ = 'wechat_share_config'

    id = db.Column(db.Integer, primary_key=True)
    sender_name = db.Column(db.String(100), default='')
    sender_wechat_id = db.Column(db.String(100), default='')
    receiver_name = db.Column(db.String(100), default='')
    receiver_wechat_id = db.Column(db.String(100), default='')
    receiver_search_key = db.Column(db.String(100), default='')
    receiver_type = db.Column(db.String(20), default='person')
    share_time = db.Column(db.String(5), default='15:30')
    share_in_order = db.Column(db.Boolean, default=True)
    immediate_on_complete = db.Column(db.Boolean, default=False)
    enabled = db.Column(db.Boolean, default=True)
    auto_send = db.Column(db.Boolean, default=False)
    helper_url = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class WechatShareLog(db.Model):
    """Share job execution log."""
    __tablename__ = 'wechat_share_log'
    __table_args__ = (
        db.Index('idx_wechat_share_log_order', 'module_key', 'order_id'),
        db.Index('idx_wechat_share_log_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    config_id = db.Column(db.Integer, db.ForeignKey('wechat_share_config.id'))
    module_key = db.Column(db.String(50), nullable=False)
    order_id = db.Column(db.Integer, nullable=False)
    order_no = db.Column(db.String(80))
    share_date = db.Column(db.Date, default=date.today)
    trigger_type = db.Column(db.String(30), default='manual')
    status = db.Column(db.String(30), default='pending')
    message = db.Column(db.String(500))
    image_path = db.Column(db.String(500))
    image_size = db.Column(db.Integer, default=0)
    receiver_name = db.Column(db.String(100))
    receiver_wechat_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.now)
    sent_at = db.Column(db.DateTime)

    config = db.relationship('WechatShareConfig', backref='logs')
