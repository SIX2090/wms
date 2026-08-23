#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 打印告警（print_alerts）域路由：PRINT-ROUTING-F01-P7。
#
# 无人值守打印的「可感知」层：手机扫码/手工单据自动打印失败或异常时，
# 主动产生系统内通知（铃铛 + 列表页）；微信推送见 A2（push_print_alert_wechat）。
#
# 告警来源三处：
#   - mark_job_printed(ok=False)：桌面守护页 / agent v1 / 内置代理失败统一挂点
#   - _recover_zombie_printing_jobs：僵尸任务尝试次数耗尽置 failed
#   - check_print_health 定时巡检：pending 超时无人认领、离线工作站仍有定向任务
#
# 设计要点：
#   - 告警只「增补」不「阻断」：所有告警路径独立小事务 + try/except，
#     任何告警异常只记日志，绝不影响打印任务本身的状态写入。
#   - 去重防风暴：同一告警类型 + 同一目标当日只建一条（对齐低库存通知口径）。
#   - 循环 import 规避：本模块被 print_queue 在函数内延迟 import；
#     本模块引用 app 模型/设置同样全部函数内延迟 import。
#
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from pydantic import BaseModel

from db import db
from utils import require_role


# ==================== pydantic 输入模型（A8） ====================

class MarkReadRequest(BaseModel):
    """标记告警已读请求体：ids 指定多条，或 all=True 全部已读。"""
    ids: list[int] | None = None
    all: bool = False


# 告警类型 → 中文名（模板展示用）
ALERT_TYPE_LABELS = {
    'print_failed': '打印失败',
    'print_pending_timeout': '任务滞留',
    'print_workstation_offline': '工作站离线',
}

# 打印任务类型 → 中文名（与 print_routing.BUSINESS_EVENT_LABELS 对齐）
JOB_TYPE_LABELS = {
    'out_order': '领料单/出库单',
    'in_order': '采购入库单',
    'label': '物料标签',
    'material_archive': '物料档案',
}


def _print_alert_enabled():
    from app import get_system_setting_bool
    return get_system_setting_bool('print_alert_enabled', True)


def _today_start():
    return datetime.combine(date.today(), datetime.min.time())


def _job_brief(job):
    """组装打印任务的简短中文描述（类型 + 单号，取不到单号回退 ID）。"""
    label = JOB_TYPE_LABELS.get(job.job_type, job.job_type or '打印任务')
    order_no = None
    try:
        if job.job_type == 'in_order' and job.target_id:
            from app import InOrder
            order = db.session.get(InOrder, job.target_id)
            order_no = order.order_no if order else None
        elif job.job_type == 'out_order' and job.target_id:
            from app import OutOrder
            order = db.session.get(OutOrder, job.target_id)
            order_no = order.order_no if order else None
    except Exception:
        order_no = None
    if order_no:
        return f'{label} {order_no}'
    if job.target_id:
        return f'{label}（ID {job.target_id}）'
    return label


def create_print_alert(alert_type, target_id, title, content):
    """创建一条打印告警系统通知（当日同类型同目标去重）。

    返回 Notification 或 None（开关关闭 / 当日已存在 / 异常）。
    任何异常只记日志并 rollback，绝不影响调用方（打印链路）业务。
    """
    try:
        if not _print_alert_enabled():
            return None
        from app import Notification
        existing = Notification.query.filter(
            Notification.type == alert_type,
            Notification.target_id == (target_id or 0),
            Notification.created_at >= _today_start(),
        ).first()
        if existing:
            return None
        notification = Notification(
            type=alert_type,
            target_id=target_id or 0,
            title=(title or '')[:200],
            content=content or '',
            is_read=False,
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    except Exception:
        db.session.rollback()
        try:
            from flask import current_app
            current_app.logger.exception('Create print alert failed')
        except Exception:
            pass
        return None


def notify_print_failed(job):
    """打印任务最终失败时建告警（mark_job_printed / 僵尸回收共用挂点）。"""
    brief = _job_brief(job)
    error = (job.error_msg or '未知原因').strip()
    create_print_alert(
        'print_failed',
        job.id,
        f'打印失败：{brief}',
        f'{brief} 打印失败。原因：{error}。'
        f'任务 ID {job.id}，已尝试 {job.attempts or 0} 次。'
        '请到「系统管理 → 打印告警」查看，或到打印工作台检查后重新打印。',
    )


def check_print_health():
    """打印链路健康巡检（APScheduler 每分钟调用）。

    - pending 滞留：任务滞留超过 print_alert_pending_timeout_min（默认 10 分钟）
      无人认领 → 按任务当日去重告警（无人接单的信号）。
    - 工作站离线：启用中的工作站离线（心跳超窗）且仍有定向到它的 pending
      任务 → 按工作站当日去重告警。
    返回 {'pending_timeout': n, 'workstation_offline': m} 供测试断言。
    """
    from app import PrintJob, PrintWorkstation, get_system_setting_int

    stats = {'pending_timeout': 0, 'workstation_offline': 0}
    if not _print_alert_enabled():
        return stats

    timeout_min = get_system_setting_int('print_alert_pending_timeout_min', 10)
    cutoff = datetime.now() - timedelta(minutes=max(1, timeout_min))
    stale_jobs = PrintJob.query.filter(
        PrintJob.status == 'pending',
        PrintJob.created_at < cutoff,
    ).order_by(PrintJob.created_at.asc()).limit(50).all()
    for job in stale_jobs:
        brief = _job_brief(job)
        if create_print_alert(
            'print_pending_timeout',
            job.id,
            f'打印任务滞留：{brief}',
            f'{brief} 已等待超过 {timeout_min} 分钟仍未被任何工作站认领打印。'
            f'任务 ID {job.id}。请检查本地打印代理是否在线、路由规则是否配置正确。',
        ):
            stats['pending_timeout'] += 1

    # 离线工作站仍有定向 pending 任务（心跳超窗即离线，与派发判定同口径）
    from routes.print_queue import workstation_is_online
    directed = db.session.query(PrintJob.workstation_id).filter(
        PrintJob.status == 'pending',
        PrintJob.workstation_id.isnot(None),
    ).distinct().all()
    ws_ids = {row[0] for row in directed if row[0]}
    if ws_ids:
        workstations = PrintWorkstation.query.filter(
            PrintWorkstation.id.in_(ws_ids),
            PrintWorkstation.enabled.is_(True),
        ).all()
        for ws in workstations:
            if workstation_is_online(ws):
                continue
            last = ws.last_heartbeat.strftime('%Y-%m-%d %H:%M') if ws.last_heartbeat else '从未'
            if create_print_alert(
                'print_workstation_offline',
                ws.id,
                f'打印工作站离线：{ws.name or ws.code}',
                f'工作站 {ws.code}（{ws.name}）当前离线（最近心跳：{last}），'
                '仍有定向到它的打印任务在等待。请确认该电脑的打印代理已启动 '
                '（或已注册开机自启的「WMS Print Agent」服务）。',
            ):
                stats['workstation_offline'] += 1
    return stats


# ==================== 路由注册 ====================

# no-test:reason=路由注册辅助函数，能力由 tests/test_print_alerts.py 各路由测试覆盖
def register_print_alert_routes(app):
    """打印告警列表页 + 标记已读 + 铃铛未读数（context processor）。"""

    @app.context_processor
    # no-test:reason=模板注入辅助，已由 test_print_alerts.py 页面渲染断言（铃铛/未读徽标）覆盖
    def inject_print_alert_unread():
        # 未登录（含 ptoken 免登录打印页）不查询，避免无意义开销
        try:
            if not current_user.is_authenticated:
                return {}
            if current_user.role not in ('admin', 'warehouse'):
                return {}
            from app import Notification
            window = datetime.now() - timedelta(days=30)
            count = Notification.query.filter(
                Notification.is_read.is_(False),
                Notification.created_at >= window,
            ).count()
            return {'print_alert_unread_count': count}
        except Exception:
            return {}

    @app.route('/print_alerts')
    @login_required
    @require_role('admin', 'warehouse')
    def print_alerts_page():
        from app import Notification
        show_all = request.args.get('all') == '1'
        query = Notification.query.filter(
            Notification.created_at >= datetime.now() - timedelta(days=30),
        )
        if not show_all:
            query = query.filter(Notification.is_read.is_(False))
        notifications = query.order_by(Notification.created_at.desc()).limit(200).all()
        return render_template(
            'print_alerts.html',
            notifications=notifications,
            show_all=show_all,
            type_labels=ALERT_TYPE_LABELS,
        )

    @app.route('/print_alerts/mark_read', methods=['POST'])
    # pydantic:reason=请求体经 MarkReadRequest（BaseModel）校验
    @login_required
    @require_role('admin', 'warehouse')
    def print_alerts_mark_read():
        from app import Notification
        payload = request.get_json(silent=True) or {}
        try:
            req = MarkReadRequest.model_validate(payload)
        except Exception:
            return jsonify({'status': 'error', 'msg': '参数格式不正确'}), 422
        query = Notification.query.filter(Notification.is_read.is_(False))
        if not req.all:
            if not req.ids:
                return jsonify({'status': 'error', 'msg': '请指定要标记的告警'}), 422
            query = query.filter(Notification.id.in_(req.ids[:200]))
        updated = query.update({'is_read': True}, synchronize_session=False)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': f'已标记 {updated} 条为已读'})
