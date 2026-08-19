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
# PRINT-ROUTING-F01-P3：Windows 本地打印代理（agent API v1，工作站令牌鉴权）：
#   - 代理端：POST /print_queue/api/v1/claim            认领本工作站下一条任务
#   - 代理端：POST /print_queue/api/v1/jobs/<id>/complete  上报打印完成
#   - 代理端：POST /print_queue/api/v1/jobs/<id>/fail       上报打印失败
#   - 代理端：POST /print_queue/api/v1/heartbeat          心跳上报在线状态 + 本地打印机列表
#   鉴权方式：Authorization: Bearer <工作站令牌>（管理页生成，免账号密码）
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
from functools import wraps

from flask import g, jsonify, render_template, request
from flask_login import current_user, login_required
from pydantic import BaseModel, field_validator

from db import db
from utils import print_token_or_login_required, require_role


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
        if v not in ('out_order', 'in_order', 'label', 'material_archive'):
            raise ValueError('job_type 必须是 out_order / in_order / label / material_archive')
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


class AgentClaimRequest(BaseModel):
    """打印代理认领任务请求体（当前无参数，保留扩展位）。"""


class AgentHeartbeatPrinter(BaseModel):
    """心跳上报的单台本地打印机。"""
    system_name: str
    status: str = 'ready'
    is_default: bool = False

    @field_validator('system_name')
    @classmethod
    def validate_system_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 200:
            raise ValueError('打印机系统名不能为空且不超过 200 字符')
        return v


class AgentHeartbeatRequest(BaseModel):
    """打印代理心跳请求体：代理版本 + 本地打印机列表。"""
    version: str | None = None
    printers: list[AgentHeartbeatPrinter] = []


# ==================== 常量 ====================

PRINTING_TIMEOUT = timedelta(minutes=5)  # printing 状态超过此时间视为僵尸任务，回收
MAX_ATTEMPTS = 5  # 同一任务最多尝试次数，超过则标记 failed
WORKSTATION_ONLINE_WINDOW = timedelta(minutes=5)  # 心跳超过此窗口视为工作站离线


def workstation_is_online(ws):
    """工作站是否可派发任务：启用 + online 且心跳未超窗。

    last_heartbeat 为 NULL 时视为兼容模式（手工置 online、无代理心跳的部署，
    如阶段 1/2 的存量数据），仍按 status 字段判定，避免存量路由失效。
    """
    if not ws or not ws.enabled or ws.status != 'online':
        return False
    if ws.last_heartbeat is None:
        return True
    return (datetime.now() - ws.last_heartbeat) <= WORKSTATION_ONLINE_WINDOW


def _recover_zombie_printing_jobs(workstation_id=None):
    """回收 printing 超时的僵尸任务（代理/守护页崩溃后任务卡 printing）。

    BUG-2026-08-19-010：
    - v1 claim 原本无任何回收 → 代理崩溃后其任务永久卡 printing；
    - legacy next 按 created_at 回收 → 队列积压 >5min 的 pending 任务一旦被
      认领（置 printing），下次轮询立即按 created_at<回收线 重置回 pending，
      无限循环永远打不出。
    统一改按 printing_started_at（认领时间）判定；存量行该字段为 NULL 时退回
    created_at 近似。未达 MAX_ATTEMPTS 重置 pending，达到则 failed。
    workstation_id 限定只回收该工作站的僵尸（各代理只管自家任务）。
    """
    from app import PrintJob
    cutoff = datetime.now() - PRINTING_TIMEOUT
    query = PrintJob.query.filter_by(status='printing')
    if workstation_id is not None:
        query = query.filter_by(workstation_id=workstation_id)
    stale_jobs = [j for j in query.all()
                  if (j.printing_started_at or j.created_at) < cutoff]
    for j in stale_jobs:
        if (j.attempts or 0) < MAX_ATTEMPTS:
            j.status = 'pending'
            j.printing_started_at = None
        else:
            j.status = 'failed'
            j.error_msg = '打印超时且尝试次数过多'
    if stale_jobs:
        db.session.commit()
    return len(stale_jobs)


def _resolve_print_route(job_type, warehouse_name):
    from app import PrintRouteRule, Warehouse
    warehouse = None
    if warehouse_name:
        warehouse = Warehouse.query.filter_by(name=warehouse_name).first()
    rules = PrintRouteRule.query.filter_by(business_event=job_type, enabled=True).order_by(
        PrintRouteRule.priority.asc(), PrintRouteRule.id.asc()).all()
    for rule in rules:
        if rule.warehouse_id is None or (warehouse and rule.warehouse_id == warehouse.id):
            if (workstation_is_online(rule.workstation)
                    and rule.printer.enabled and rule.printer.status == 'online'):
                return rule
    return None


def _print_url(job):
    if job.job_type == 'out_order':
        url = f'/out_order/{job.target_id}/print'
    elif job.job_type == 'in_order':
        url = f'/in_order/{job.target_id}/print'
    elif job.job_type == 'material_archive':
        url = f'/material_archive/{job.target_id}/print'
    else:
        url = f'/label/batch_print?ids={job.target_ids or ""}'
    if job.copies and job.copies > 1:
        url += ('&' if '?' in url else '?') + f'copies={job.copies}'
    return url


def enqueue_auto_print_job(job_type, target_id, warehouse_name, target_ids=None,
                           copies=1, created_by=None, source_event='auto'):
    """扫码/手工入库出库成功后自动创建打印任务，供桌面打印工作站或定向代理出纸。

    - 有匹配路由规则且目标工作站/打印机在线时：创建「定向」任务（workstation_id /
      printer_id / route_rule_id 指向指定工作站），由该工作站的打印代理或专属队列
      （/print_queue/workstations/<id>/next）认领。
    - 无匹配路由规则（未配置，或目标工作站/打印机不在线）时：回退创建「未定向」任务
      （workstation_id=None），任意桌面打印工作站（/print_queue/next）即可认领并自动
      出纸，满足「手机提交 → 本地电脑自动打印、仅需两端同时登录」的轻量场景。
    - 任务始终创建，不阻塞业务操作；由调用方同一事务提交，保证单据与打印任务原子写入。
    """
    from app import PrintJob
    route = _resolve_print_route(job_type, warehouse_name)
    job = PrintJob(
        job_type=job_type,
        target_id=target_id,
        target_ids=target_ids,
        copies=copies,
        status='pending',
        created_by=created_by,
        workstation_id=route.workstation_id if route else None,
        printer_id=route.printer_id if route else None,
        route_rule_id=route.id if route else None,
        source_event=source_event,
    )
    db.session.add(job)
    db.session.flush()
    return job


def _workstation_from_token():
    """从 Authorization: Bearer <token> 解析工作站；无效返回 None。"""
    from app import PrintWorkstation
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token_value = auth.split(' ', 1)[1].strip()
    if not token_value:
        return None
    return PrintWorkstation.query.filter_by(auth_token=token_value, enabled=True).first()


def _workstation_token_required(f):
    """打印代理 API 鉴权装饰器：工作站令牌有效时挂到 g.print_workstation。"""
    @wraps(f)
    def decorated_function(*args, **kwargs):  # no-test:reason=装饰器内部函数，能力由 print_queue_api_v1_* 路由测试覆盖
        ws = _workstation_from_token()
        if not ws:
            return jsonify({'status': 'error', 'msg': '工作站令牌无效或工作站已停用'}), 401
        g.print_workstation = ws
        return f(*args, **kwargs)
    return decorated_function


# no-test:reason=路由注册辅助函数，能力由各 print_queue_* 路由测试覆盖
def register_print_queue_routes(app):
    # pydantic:reason=本模块所有 POST 路由均使用 pydantic BaseModel 校验输入
    from app import csrf  # agent API v1 走工作站令牌鉴权，豁免 CSRF（无 Web 会话）

    @app.route('/print_queue/jobs', methods=['POST'])
    # pydantic:reason=请求体经 CreatePrintJobRequest（BaseModel）校验
    @csrf.exempt
    def print_queue_create_job():
        """手机端创建打印任务（Web 会话或移动端 Bearer 令牌均可）。

        手机端提交入库/出库后点"打印单据"、或物料档案详情页点"打印"时调用。
        桌面端 Web 走会话鉴权；移动端走 Bearer 令牌（无 Web 会话，故豁免 CSRF，
        与 native_api 各移动写接口 @csrf.exempt 一致）。
        """
        from app import PrintJob, get_bearer_user
        user = current_user if current_user.is_authenticated else get_bearer_user()
        if user is None:
            return jsonify({'status': 'error', 'success': False, 'msg': '未登录或 Bearer Token 无效'}), 401
        if user.role != 'admin' and user.role != 'warehouse':
            return jsonify({'status': 'error', 'success': False, 'msg': '当前账号没有权限执行该操作'}), 403
        try:
            payload = request.get_json(silent=True) or {}
            req = CreatePrintJobRequest(**payload)
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400

        err = req.validate_target()
        if err:
            return jsonify({'status': 'error', 'msg': err}), 400

        warehouse_name = ''
        if req.job_type == 'out_order':
            from app import OutOrder
            target = db.session.get(OutOrder, req.target_id)
            if not target:
                return jsonify({'status': 'error', 'msg': '领料单不存在'}), 404
            warehouse_name = target.warehouse or ''
        elif req.job_type == 'in_order':
            from app import InOrder
            target = db.session.get(InOrder, req.target_id)
            if not target:
                return jsonify({'status': 'error', 'msg': '采购入库单不存在'}), 404
            warehouse_name = target.warehouse or ''
        elif req.job_type == 'material_archive':
            from app import Material
            target = db.session.get(Material, req.target_id)
            if not target:
                return jsonify({'status': 'error', 'msg': '物料不存在'}), 404
        else:
            from app import Material
            ids = [int(value) for value in req.target_ids.split(',') if value.strip().isdigit()]
            if not ids or Material.query.filter(Material.id.in_(ids)).count() != len(set(ids)):
                return jsonify({'status': 'error', 'msg': '标签物料不存在或格式无效'}), 400

        route = _resolve_print_route(req.job_type, warehouse_name)
        job = PrintJob(
            job_type=req.job_type,
            target_id=req.target_id,
            target_ids=req.target_ids,
            copies=req.copies,
            status='pending',
            created_by=user.id,
            workstation_id=route.workstation_id if route else None,
            printer_id=route.printer_id if route else None,
            route_rule_id=route.id if route else None,
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
    @require_role('warehouse')
    def print_queue_next():
        """桌面端守护页面轮询：返回最早的 pending 任务，并将其置为 printing。

        同时回收 printing 超过 5 分钟的僵尸任务（BUG-2026-08-19-010：
        按 printing_started_at 判定，不再按 created_at 误回收积压任务）。
        """
        from app import PrintJob
        _recover_zombie_printing_jobs()

        job = PrintJob.query.filter_by(status='pending', workstation_id=None).order_by(PrintJob.created_at.asc()).first()
        if not job:
            return jsonify({'status': 'empty', 'msg': '队列为空'})

        job.status = 'printing'
        job.attempts = (job.attempts or 0) + 1
        job.printing_started_at = datetime.now()
        db.session.commit()

        print_url = _print_url(job)

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

    @app.route('/print_queue/workstations/<int:workstation_id>/next', methods=['GET'])
    @login_required
    @require_role('admin')
    def print_queue_workstation_next(workstation_id):
        from app import PrintJob, PrintWorkstation
        workstation = db.session.get(PrintWorkstation, workstation_id)
        if not workstation or not workstation.enabled or workstation.status != 'online':
            return jsonify({'status': 'empty', 'msg': '工作站不可用'})
        _recover_zombie_printing_jobs(workstation_id=workstation_id)
        job = PrintJob.query.filter_by(
            status='pending', workstation_id=workstation_id).order_by(PrintJob.created_at.asc()).first()
        if not job:
            return jsonify({'status': 'empty', 'msg': '队列为空'})
        job.status = 'printing'
        job.attempts = (job.attempts or 0) + 1
        job.printing_started_at = datetime.now()
        db.session.commit()
        return jsonify({'status': 'success', 'job': {
            'id': job.id, 'job_type': job.job_type, 'target_id': job.target_id,
            'target_ids': job.target_ids, 'copies': job.copies, 'print_url': _print_url(job),
            'printer_id': job.printer_id,
            'printer_system_name': job.printer.system_name if job.printer else '',
        }})

    @app.route('/print_queue/jobs/<int:job_id>/complete', methods=['POST'])
    @login_required
    @require_role('warehouse')
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
    @require_role('warehouse')
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
    @require_role('warehouse')
    def print_queue_station():
        """桌面端打印工作站守护页面。"""
        return render_template('print_station.html')

    @app.route('/material_archive/<int:material_id>/print')
    @print_token_or_login_required  # PRINT-ROUTING-F01-P3：支持 ptoken 免登录（Windows 打印代理）
    def print_material_archive(material_id):
        """物料档案打印页：展示物料基础信息 + 全部档案图片。

        供手机端物料档案"打印"按钮生成的打印队列任务（job_type=material_archive）
        在桌面打印工作站渲染出纸，同时支持 Web 端直接访问。
        """
        from datetime import datetime
        from sqlalchemy.orm import joinedload
        from app import Material, MaterialImage
        material = Material.query.options(
            joinedload(Material.unit),
            joinedload(Material.category),
            joinedload(Material.supplier),
        ).get_or_404(material_id)
        try:
            images = (
                MaterialImage.query.filter_by(material_id=material_id)
                .order_by(MaterialImage.sort_order.asc(), MaterialImage.id.asc())
                .all()
            )
        except Exception:
            images = []
        return render_template(
            'material_archive_print.html',
            material=material,
            images=images,
            now=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        )

    @app.route('/print_queue/stats')
    @login_required
    @require_role('warehouse')
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

    # ==================== agent API v1（Windows 打印代理，工作站令牌鉴权） ====================

    @app.route('/print_queue/api/v1/claim', methods=['POST'])
    # pydantic:reason=请求体经 AgentClaimRequest（BaseModel）校验
    @csrf.exempt
    @_workstation_token_required
    def print_queue_api_v1_claim():
        """打印代理认领本工作站最早的 pending 任务（认领即置 printing）。"""
        from app import PrintJob
        try:
            AgentClaimRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        ws = g.print_workstation
        if not workstation_is_online(ws):
            return jsonify({'status': 'empty', 'msg': '工作站离线或心跳超时，请先上报心跳'})
        # BUG-2026-08-19-010：认领前回收本工作站僵尸任务（代理崩溃后卡 printing）
        _recover_zombie_printing_jobs(workstation_id=ws.id)
        job = PrintJob.query.filter_by(
            status='pending', workstation_id=ws.id).order_by(PrintJob.created_at.asc()).first()
        if not job:
            return jsonify({'status': 'empty', 'msg': '队列为空'})
        job.status = 'printing'
        job.attempts = (job.attempts or 0) + 1
        job.printing_started_at = datetime.now()
        db.session.commit()
        # 打印 URL 附短时效 ptoken（免登录渲染）与 autoprint=1（页面加载后自动打印）
        from utils import generate_print_token
        print_url = _print_url(job)
        sep = '&' if '?' in print_url else '?'
        print_url += f'{sep}ptoken={generate_print_token(job.id, ws.id)}&autoprint=1'
        return jsonify({'status': 'success', 'job': {
            'id': job.id,
            'job_type': job.job_type,
            'target_id': job.target_id,
            'target_ids': job.target_ids,
            'copies': job.copies,
            'print_url': print_url,
            'printer_id': job.printer_id,
            'printer_system_name': job.printer.system_name if job.printer else '',
        }})

    @app.route('/print_queue/api/v1/jobs/<int:job_id>/complete', methods=['POST'])
    # pydantic:reason=请求体经 JobStatusRequest（BaseModel）校验
    @csrf.exempt
    @_workstation_token_required
    def print_queue_api_v1_complete(job_id):
        """打印代理上报打印完成（仅允许本工作站的任务）。"""
        from app import PrintJob
        try:
            req = JobStatusRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        job = db.session.get(PrintJob, job_id)
        if not job or job.workstation_id != g.print_workstation.id:
            return jsonify({'status': 'error', 'msg': '任务不存在或不属于本工作站'}), 404
        job.status = 'done'
        job.printed_at = datetime.now()
        if req.error_msg:
            job.error_msg = req.error_msg[:500]
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '已标记完成'})

    @app.route('/print_queue/api/v1/jobs/<int:job_id>/fail', methods=['POST'])
    # pydantic:reason=请求体经 JobStatusRequest（BaseModel）校验
    @csrf.exempt
    @_workstation_token_required
    def print_queue_api_v1_fail(job_id):
        """打印代理上报打印失败（仅允许本工作站的任务）。"""
        from app import PrintJob
        try:
            req = JobStatusRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        job = db.session.get(PrintJob, job_id)
        if not job or job.workstation_id != g.print_workstation.id:
            return jsonify({'status': 'error', 'msg': '任务不存在或不属于本工作站'}), 404
        job.status = 'failed'
        job.error_msg = (req.error_msg or '打印代理上报失败')[:500]
        job.printed_at = datetime.now()
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '已标记失败'})

    @app.route('/print_queue/api/v1/heartbeat', methods=['POST'])
    # pydantic:reason=请求体经 AgentHeartbeatRequest（BaseModel）校验
    @csrf.exempt
    @_workstation_token_required
    def print_queue_api_v1_heartbeat():
        """打印代理心跳：刷新在线状态并同步本地打印机列表。

        - 上报的打印机 upsert 到 PrintDevice（按 workstation_id + system_name 匹配）
        - 本次未上报的本工作站打印机置 offline（已停用 enabled=False 的不动）
        """
        from app import PrintDevice
        try:
            req = AgentHeartbeatRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        ws = g.print_workstation
        now = datetime.now()
        ws.status = 'online'
        ws.last_heartbeat = now
        reported = {p.system_name: p for p in req.printers}
        existing = {d.system_name: d for d in PrintDevice.query.filter_by(workstation_id=ws.id).all()}
        created, online = 0, 0
        for name, p in reported.items():
            device = existing.get(name)
            if not device:
                device = PrintDevice(
                    workstation_id=ws.id, system_name=name, display_name=name,
                    printer_type='mixed', enabled=True,
                )
                db.session.add(device)
                created += 1
            device.status = 'online' if p.status != 'error' else 'error'
            device.is_default = bool(p.is_default)
            online += 1
        for name, device in existing.items():
            if name not in reported and device.enabled:
                device.status = 'offline'
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': '心跳处理失败，请稍后重试'}), 500
        return jsonify({
            'status': 'success',
            'msg': '心跳已记录',
            'data': {'workstation': ws.code, 'printers_online': online, 'printers_created': created},
        })