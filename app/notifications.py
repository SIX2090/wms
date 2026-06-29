#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
库存预警通知模块
支持邮件通知和系统内通知
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from flask import render_template_string
import json


class NotificationManager:
    """通知管理器"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """初始化应用"""
        self.app = app
        # SMTP配置
        self.smtp_host = app.config.get('SMTP_HOST', os.environ.get('SMTP_HOST', ''))
        self.smtp_port = app.config.get('SMTP_PORT', int(os.environ.get('SMTP_PORT', 587)))
        self.smtp_user = app.config.get('SMTP_USER', os.environ.get('SMTP_USER', ''))
        self.smtp_password = app.config.get('SMTP_PASSWORD', os.environ.get('SMTP_PASSWORD', ''))
        self.smtp_from = app.config.get('SMTP_FROM', os.environ.get('SMTP_FROM', self.smtp_user))
        self.notification_enabled = app.config.get('NOTIFICATION_ENABLED', True)
    
    def send_email(self, to_email, subject, html_content, text_content=None):
        """发送邮件通知"""
        if not self.notification_enabled or not self.smtp_host:
            print(f"[邮件通知已禁用] 收件人: {to_email}, 主题: {subject}")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_from
            msg['To'] = to_email
            
            # 纯文本内容
            if text_content:
                msg.attach(MIMEText(text_content, 'plain', 'utf-8'))
            
            # HTML内容
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_from, to_email, msg.as_string())
            
            print(f"[邮件发送成功] 收件人: {to_email}, 主题: {subject}")
            return True
            
        except Exception as e:
            print(f"[邮件发送失败] 错误: {e}")
            return False
    
    def check_low_stock(self, db, Material, User):
        """检查低库存物料并发送通知"""
        from app import Notification
        
        # 获取低库存物料
        low_stock_materials = Material.query.filter(
            Material.stock <= Material.min_stock,
            Material.min_stock > 0
        ).all()
        
        if not low_stock_materials:
            return []
        
        notifications = []
        
        for material in low_stock_materials:
            # 检查今天是否已经发送过通知
            # created_at 是 DateTime 列，必须与 datetime 比较（而非 date），
            # 否则 SQLite 下类型不匹配可能导致"今天已发"判断失效，重复发或漏发
            today_start = datetime.combine(date.today(), datetime.min.time())
            existing = Notification.query.filter(
                Notification.type == 'low_stock',
                Notification.target_id == material.id,
                Notification.created_at >= today_start
            ).first()
            
            if existing:
                continue
            
            # 创建系统通知
            notification = Notification(
                type='low_stock',
                target_id=material.id,
                title=f'库存预警：{material.name}',
                content=f'物料 "{material.name}" ({material.code}) 库存不足，当前库存 {material.stock}，最小库存 {material.min_stock}',
                is_read=False
            )
            db.session.add(notification)
            notifications.append(notification)
            
            # 发送邮件通知给管理员
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                if hasattr(admin, 'email') and admin.email:
                    self.send_low_stock_email(admin.email, material)

        # 后台定时任务中 commit 必须包裹 try/except + rollback，
        # 否则 session 进入脏状态后同一后台线程后续每次定时任务都会持续 PendingRollbackError
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.getLogger(__name__).error(f'check_low_stock 提交通知失败: {e}', exc_info=True)
        return notifications
    
    def send_low_stock_email(self, to_email, material):
        """发送低库存预警邮件"""
        subject = f'【库存预警】{material.name} 库存不足'
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; }}
                .content {{ background: #f8f9fa; padding: 20px; margin: 20px 0; }}
                .warning {{ color: #dc3545; font-weight: bold; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #e9ecef; }}
                .footer {{ text-align: center; color: #6c757d; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>⚠️ 库存预警通知</h2>
                </div>
                <div class="content">
                    <p>您好，</p>
                    <p>系统检测到以下物料库存不足，请及时处理：</p>
                    
                    <table>
                        <tr>
                            <th>物料编码</th>
                            <td>{material.code}</td>
                        </tr>
                        <tr>
                            <th>物料名称</th>
                            <td>{material.name}</td>
                        </tr>
                        <tr>
                            <th>规格</th>
                            <td>{material.spec or '-'}</td>
                        </tr>
                        <tr>
                            <th class="warning">当前库存</th>
                            <td class="warning">{material.stock}</td>
                        </tr>
                        <tr>
                            <th>最小库存</th>
                            <td>{material.min_stock}</td>
                        </tr>
                        <tr>
                            <th>单位</th>
                            <td>{material.unit.name if material.unit else '-'}</td>
                        </tr>
                    </table>
                    
                    <p>请及时补充库存，以免影响正常生产。</p>
                </div>
                <div class="footer">
                    <p>此邮件由仓库管理系统自动发送</p>
                    <p>发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(to_email, subject, html_content)
    
    def check_expiring_materials(self, db, Material, User):
        """检查即将过期物料"""
        from app import Notification
        from datetime import timedelta
        
        # 获取即将过期（30天内）的物料
        soon_expire_date = date.today() + timedelta(days=30)
        expiring_materials = Material.query.filter(
            Material.expiry_date <= soon_expire_date,
            Material.expiry_date >= date.today()
        ).all()
        
        notifications = []
        
        for material in expiring_materials:
            days_remaining = (material.expiry_date - date.today()).days
            
            # 检查今天是否已经发送过通知（created_at 是 DateTime，需与 datetime 比较）
            today_start = datetime.combine(date.today(), datetime.min.time())
            existing = Notification.query.filter(
                Notification.type == 'expiring',
                Notification.target_id == material.id,
                Notification.created_at >= today_start
            ).first()
            
            if existing:
                continue
            
            # 创建系统通知
            notification = Notification(
                type='expiring',
                target_id=material.id,
                title=f'即将过期：{material.name}',
                content=f'物料 "{material.name}" ({material.code}) 将在 {days_remaining} 天后过期（{material.expiry_date}）',
                is_read=False
            )
            db.session.add(notification)
            notifications.append(notification)

        # 后台定时任务中 commit 必须包裹 try/except + rollback，避免 session 脏状态持续失败
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.getLogger(__name__).error(f'check_expiring_materials 提交通知失败: {e}', exc_info=True)
        return notifications


# 全局通知管理器实例
notification_manager = NotificationManager()


def init_notification_scheduler(app, db, Material, User):
    """初始化定时通知任务"""
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    notification_manager.init_app(app)

    # 每天上午9点检查库存
    # 显式指定 id、replace_existing、max_instances，避免 init_notification_scheduler
    # 被多次调用（debug reloader、测试）时注册多个相同 job 导致重复执行
    # 注意：APScheduler 3.10.x 的 @scheduler.scheduled_job 装饰器签名不含 replace_existing，
    # 传入会被吞入 **trigger_args 再传给 add_job，与装饰器内部硬编码的 True 位置参数冲突，
    # 报 "got multiple values for argument 'replace_existing'"。因此改用 add_job 直接调用。
    def daily_stock_check():
        with app.app_context():
            logging.getLogger(__name__).info('执行每日库存检查...')
            notification_manager.check_low_stock(db, Material, User)
            notification_manager.check_expiring_materials(db, Material, User)

    scheduler.add_job(
        daily_stock_check,
        'cron',
        hour=9,
        minute=0,
        id='daily_stock_check',
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    return scheduler
