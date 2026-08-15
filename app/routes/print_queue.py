#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 远程打印队列（print_queue）域路由。
#
# 用于「手机扫码出库 → 本地电脑打印机出纸」场景：
#   - 手机端：POST /print_queue/jobs  写入一条打印任务
#   - 桌面端：GET  /print_queue/station  打开守护页面（轮询 + 自动 window.print()）
#   - 桌面端：GET  /print_queue/next  拉取下一条 pending 任务
#   - 桌面端：POST /print_queue/jobs/<id>/complete  标记完成
#   - 桌面端：POST /print_queue/jobs/<id>/fail     标记失败
#
# 设计要点：
#   - 单台电脑方案：next 直接返回最早的 pending 任务，不做工作站路由
#   - 状态机：pending → printing → done/failed，attempts 防止死循环
#   - 拉取即占用：next 返回 pending 任务时同时将其置为 printing，避免重复拉取
#   - 超时回收：printing 超过 5 分钟未确认的任务，下次 next 时回收为 pending
#
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from datetime import datetime, timedelta

from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from pydantic import BaseModel, field_validator

from db import db


# ==================== pydantic 输入模型（A8） ====================

class CreatePrintJobRequest(BaseModel):
    """创建打印任务请求体。"""
    job_type: str  # out_order / in_order / label
    target_id: int | None = None  # 单据 ID（label 时为空）
    target_ids: str | None = None  # label 场景：逗号分隔物料 ID
    copies: int = 1

    @field_validator('job_type')
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v not in ('out_order', 'in_order', 'label'):
            raise ValueError('job_type 必须是 out_order / in_order / label')
        return v

    @field_validator('copies')
    @classmethod
    def validate_copies(cls, v: int) -> int:
        if v < 1 or v > 99:
            raise ValueError('copies 必须在 1-99 之间')
        return v

    def validate_target(self) -> str | None:
        """校验目标 ID 与 job_type 匹配，返回错误描述或 None。"""
        if self.job_type == 'label':
            if not self.target_ids:
                return 'label 类型必须提供 target_ids'
        else:
            if not self.target_id:
                return f'{self.job_type} 类型必须提供 target_id'
        return None


class JobStatusRequest(BaseModel):
    """桌面端上报打印结果请求体。"""
    error_msg: str | None = None


# ==================== 常量 ====================

PRINTING_TIMEOUT = timedelta(minutes=5)  # printing 状态超过此时间视为僵尸任务，回收
MAX_ATTEMPTS = 5  # 同一任务最多尝试次数，超过则标记 failed


# no-test:reason=路由注册辅助函数，能力由各 print_queue_* 路由测试覆盖
def register_print_queue_routes(app):
    # pydantic:reason=本模块所有 POST 路由均使用 pydantic BaseModel 校验输入

    @app.route('/print_queue/jobs', methods=['POST'])
    @login_required
    def print_queue_create_job():
        """手机端创建打印任务。"""
        from app import PrintJob
        try:
            payload = request.get_json(silent=True) or {}
            req = CreatePrintJobRequest(**payload)
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400

        err = req.validate_target()
        if err:
            return jsonify({'status': 'error', 'msg': err}), 400

        job = PrintJob(
            job_type=req.job_type,
            target_id=req.target_id,
            target_ids=req.target_ids,
            copies=req.copies,
            status='pending',
            created_by=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(job)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'msg': '已加入打印队列，请到桌面端打印工作站查看',
            'job_id': job.id,
        })

    @app.route('/print_queue/next', methods=['GET'])
    @login_required
    def print_queue_next():
        """桌面端守护页面轮询：返回最早的 pending 任务，并将其置为 printing。

        同时回收 printing 超过 5 分钟的僵尸任务。
        """
        from app import PrintJob
        now = datetime.now()
        stale_cutoff = now - PRINTING_TIMEOUT

        # 回收僵尸任务：printing 超过 5 分钟未确认 → 重置 pending（未达最大尝试次数）或 failed
        # 由于没有 printing_started_at 字段，借用 created_at 近似（5 分钟回收窗口足够覆盖正常打印流程）
        printing_jobs = PrintJob.query.filter_by(status='printing').all()
        stale_jobs = [j for j in printing_jobs if j.created_at and j.created_at < stale_cutoff]
        for j in stale_jobs:
            if (j.attempts or 0) < MAX_ATTEMPTS:
                j.status = 'pending'
            else:
                j.status = 'failed'
                j.error_msg = '打印超时且尝试次数过多'
        if stale_jobs:
            db.session.commit()

        job = PrintJob.query.filter_by(status='pending').order_by(PrintJob.created_at.asc()).first()
        if not job:
            return jsonify({'status': 'empty', 'msg': '队列为空'})

        job.status = 'printing'
        job.attempts = (job.attempts or 0) + 1
        db.session.commit()

        # 构造打印 URL（桌面端 iframe 加载该 URL 后调 window.print()）
        if job.job_type == 'out_order':
            print_url = f'/out_order/{job.target_id}/print'
        elif job.job_type == 'in_order':
            print_url = f'/in_order/{job.target_id}/print'
        else:  # label
            ids = job.target_ids or ''
            print_url = f'/label/batch_print?ids={ids}'
        # copies 通过 URL 参数透传，由桌面端 JS 控制循环打印
        if job.copies and job.copies > 1:
            print_url += f'&copies={job.copies}'

        return jsonify({
            'status': 'success',
            'job': {
                'id': job.id,
                'job_type': job.job_type,
                'target_id': job.target_id,
                'target_ids': job.target_ids,
                'copies': job.copies,
                'print_url': print_url,
                'created_at': job.created_at.strftime('%Y-%m-%d %H:%M:%S') if job.created_at else '',
            }
        })

    @app.route('/print_queue/jobs/<int:job_id>/complete', methods=['POST'])
    @login_required
    def print_queue_complete(job_id):
        """桌面端标记任务完成。"""
        from app import PrintJob
        try:
            payload = request.get_json(silent=True) or {}
            req = JobStatusRequest(**payload)
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400

        job = PrintJob.query.get_or_404(job_id)
        job.status = 'done'
        job.printed_at = datetime.now()
        if req.error_msg:
            job.error_msg = req.error_msg[:500]
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '已标记完成'})

    @app.route('/print_queue/jobs/<int:job_id>/fail', methods=['POST'])
    @login_required
    def print_queue_fail(job_id):
        """桌面端标记任务失败。"""
        from app import PrintJob
        try:
            payload = request.get_json(silent=True) or {}
            req = JobStatusRequest(**payload)
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400

        job = PrintJob.query.get_or_404(job_id)
        job.status = 'failed'
        job.error_msg = (req.error_msg or '桌面端打印失败')[:500]
        job.printed_at = datetime.now()
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '已标记失败'})

    @app.route('/print_queue/station')
    @login_required
    def print_queue_station():
        """桌面端打印工作站守护页面。"""
        return render_template('print_station.html')

    @app.route('/print_queue/stats')
    @login_required
    def print_queue_stats():
        """打印队列统计（守护页面展示用）。"""
        from app import PrintJob
        pending = PrintJob.query.filter_by(status='pending').count()
        printing = PrintJob.query.filter_by(status='printing').count()
        done = PrintJob.query.filter_by(status='done').count()
        failed = PrintJob.query.filter_by(status='failed').count()
        return jsonify({
            'status': 'success',
            'stats': {'pending': pending, 'printing': printing, 'done': done, 'failed': failed}
        })
