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
from flask import render_template_string, current_app
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
        # SMTP 连接/读写超时（秒）。未配置时默认 30 秒，避免后台定时任务
        # 因 SMTP 服务器无响应而永久阻塞线程。
        self.smtp_timeout = app.config.get(
            'SMTP_TIMEOUT',
            int(os.environ.get('SMTP_TIMEOUT', '30') or '30'),
        )
    
    def send_email(self, to_email, subject, html_content, text_content=None):
        """发送邮件通知"""
        if not self.notification_enabled or not self.smtp_host:
            self._log('邮件通知已禁用', subject=subject)
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
            # 显式传入 timeout，避免 SMTP 服务器无响应时后台定时任务线程永久阻塞
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.smtp_timeout) as server:
                # starttls/login/sendmail 同样受 timeout 保护
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_from, to_email, msg.as_string())

            self._log('邮件发送成功', subject=subject)
            return True

        except Exception as e:
            self._log('邮件发送失败', error=str(e))
            return False

    def _log(self, message, *, subject=None, error=None):
        """Log notification events via the Flask app logger (no email addresses in logs)."""
        parts = [f'[通知] {message}']
        if subject:
            parts.append(f'主题={subject}')
        if error:
            parts.append(f'错误={error}')
        try:
            current_app.logger.info(' '.join(parts))
        except Exception:
            logging.getLogger('app').warning(' '.join(parts))

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
        # BUG-2026-08-30-007：物料名/编码/规格来自导入等外部输入，拼 HTML 前转义防注入
        import html as _html
        _code = _html.escape(str(material.code or ''))
        _name = _html.escape(str(material.name or ''))
        _spec = _html.escape(str(material.spec or '-'))
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
                            <td>{_code}</td>
                        </tr>
                        <tr>
                            <th>物料名称</th>
                            <td>{_name}</td>
                        </tr>
                        <tr>
                            <th>规格</th>
                            <td>{_spec}</td>
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

    # AI-R14-F01: 每日凌晨2点执行数据保留清理预览（默认只预览，不自动删除）
    def daily_data_retention_cleanup():
        with app.app_context():
            logging.getLogger(__name__).info('AI-R14-F01: 执行每日数据保留清理预览...')
            try:
                from ai.ops.data_retention import default_retention_config, preview_cleanup
                from datetime import datetime
                
                # 使用默认配置
                config = default_retention_config(dry_run=True)
                
                # 依赖注入函数（从app.py导入）
                # 注意：这里需要延迟导入避免循环依赖
                try:
                    from app import (
                        _ai_dr_query_expired,
                        _ai_dr_resolve_system_executor_id,
                        _ai_dr_save_log,
                    )
                    
                    # 执行预览
                    preview_result = preview_cleanup(
                        config=config,
                        query_expired=_ai_dr_query_expired,
                    )
                    
                    logging.getLogger(__name__).info(
                        f'AI-R14-F01 清理预览完成: '
                        f'待删除={preview_result.to_delete_count}, '
                        f'受保护={preview_result.protected_count}, '
                        f'豁免={preview_result.exempt_count}, '
                        f'保留={preview_result.to_keep_count}'
                    )
                    
                    # 保存预览日志（dry_run=True）
                    # BUG-2026-09-04-001：历史写 executed_by=0（无对应用户，外键必失败，
                    # 每日 02:00 日志复现）。改为解析真实系统归属账号，无账号可归时跳过落库。
                    executor_id = _ai_dr_resolve_system_executor_id()
                    if executor_id is None:
                        logging.getLogger(__name__).warning(
                            'AI-R14-F01: 库中无可用账号，跳过保存自动预览日志（不影响清理预览）')
                    else:
                        from ai.ops.data_retention import CleanupLogEntry
                        log_entry = CleanupLogEntry(
                            log_id=f'auto-preview-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
                            executed_by=executor_id,  # 系统自动执行 → 归属系统管理账号
                            categories=list(set(item.record.category for item in preview_result.items)),
                            dry_run=True,
                            deleted_count=0,  # 预览模式不删除
                            kept_count=preview_result.to_keep_count,
                            exempt_count=preview_result.exempt_count,
                            protected_count=preview_result.protected_count,
                            failed_count=0,
                            cutoff_date=preview_result.generated_at,
                            executed_at=datetime.now().isoformat(),
                            notes='系统自动预览（未实际删除）',
                        )
                        _ai_dr_save_log(log_entry)
                    
                except ImportError as e:
                    logging.getLogger(__name__).warning(f'AI-R14-F01: 依赖注入函数未找到，跳过清理预览: {e}')
                    
            except Exception as e:
                logging.getLogger(__name__).error(f'AI-R14-F01: 清理预览失败: {e}')

    scheduler.add_job(
        daily_data_retention_cleanup,
        'cron',
        hour=2,
        minute=0,
        id='daily_data_retention_cleanup',
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    return scheduler
