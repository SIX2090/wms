#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 定向打印管理（print_routing）域路由：PRINT-ROUTING-F01-P3。
#
# 系统管理 → 打印工作台路由：
#   - 工作站（本地电脑）增删改、启停、令牌生成/重置
#   - 打印机（工作站心跳自动注册，可手工启停/编辑/删除）
#   - 路由规则（业务事件 + 仓库 → 工作站 + 打印机，优先级）
#
# 权限：全部仅 admin。工作站令牌供 Windows 打印代理免账号密码调用
# agent API v1；令牌明文存储且管理页随时可见可复制（与 ApiToken 一致，
# 不属于用户账号密码范畴，不隐藏凭证）。
#
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import io
import json
import os
import secrets
import zipfile

from flask import jsonify, render_template, request, send_file
from flask_login import login_required
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import OperationalError

from db import db
from utils import require_role


# ==================== pydantic 输入模型（A8） ====================

BUSINESS_EVENTS = ('out_order', 'in_order', 'label', 'material_archive')
BUSINESS_EVENT_LABELS = {
    'out_order': '领料单/出库单',
    'in_order': '采购入库单',
    'label': '物料标签',
    'material_archive': '物料档案',
}


class WorkstationCreateRequest(BaseModel):
    """新增工作站。"""
    code: str
    name: str
    warehouse_id: int | None = None

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 64:
            raise ValueError('工作站编码必填且不超过 64 字符')
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError('工作站名称必填且不超过 100 字符')
        return v


class WorkstationEditRequest(BaseModel):
    """编辑工作站。"""
    name: str
    warehouse_id: int | None = None
    enabled: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError('工作站名称必填且不超过 100 字符')
        return v


class PrinterCreateRequest(BaseModel):
    """手工新增打印机。"""
    workstation_id: int
    display_name: str
    system_name: str = ''
    printer_type: str = 'mixed'
    enabled: bool = True

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError('打印机名称必填且不超过 100 字符')
        return v

    @field_validator('system_name')
    @classmethod
    def validate_system_name(cls, v: str) -> str:
        return v.strip() if v else ''

    @field_validator('printer_type')
    @classmethod
    def validate_printer_type(cls, v: str) -> str:
        if v not in ('label', 'document', 'mixed'):
            raise ValueError('打印机类型必须是 label / document / mixed')
        return v


class PrinterEditRequest(BaseModel):
    """编辑打印机。"""
    display_name: str
    printer_type: str = 'mixed'
    enabled: bool = True

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError('打印机名称必填且不超过 100 字符')
        return v

    @field_validator('printer_type')
    @classmethod
    def validate_printer_type(cls, v: str) -> str:
        if v not in ('label', 'document', 'mixed'):
            raise ValueError('打印机类型必须是 label / document / mixed')
        return v


class RuleSaveRequest(BaseModel):
    """新增/编辑路由规则。"""
    name: str
    business_event: str
    warehouse_id: int | None = None
    workstation_id: int
    printer_id: int
    priority: int = 100
    enabled: bool = True

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError('规则名称必填且不超过 100 字符')
        return v

    @field_validator('business_event')
    @classmethod
    def validate_business_event(cls, v: str) -> str:
        if v not in BUSINESS_EVENTS:
            raise ValueError('业务事件必须是 out_order / in_order / label / material_archive')
        return v

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if v < 1 or v > 9999:
            raise ValueError('优先级必须在 1-9999 之间（数字越小越优先）')
        return v


def _workstation_delete_blockers(ws):
    """删除工作站前的阻断检查：已有打印任务或路由规则时禁止删除。"""
    blockers = []
    if ws.print_jobs:
        blockers.append(f'{len(ws.print_jobs)} 条打印任务')
    if ws.print_route_rules:
        blockers.append(f'{len(ws.print_route_rules)} 条路由规则')
    return blockers


# no-test:reason=路由注册辅助函数，能力由 print_routing_* 路由测试覆盖
def register_print_routing_routes(app):
    # pydantic:reason=本模块所有 POST 路由均使用 pydantic BaseModel 校验输入

    @app.route('/print_routing')
    @login_required
    @require_role('admin')
    def print_routing_page():
        from app import PrintRouteRule, PrintWorkstation, Warehouse
        # BUG-2026-08-19-003：老库若缺 print 系列表（启动时 create_all 未跑，
        # 如 WMS_SKIP_STARTUP_DB_UPGRADE / WMS_NO_DB_TOUCH），首条查询抛
        # "no such table" 直接 500，页面显示"服务器内部错误"。按代码库既有模式
        # （缺失表交给 db.create_all() 处理）惰性补齐缺表后重试，杜绝进入报错。
        try:
            workstations = PrintWorkstation.query.order_by(PrintWorkstation.code).all()
            rules = PrintRouteRule.query.order_by(
                PrintRouteRule.business_event, PrintRouteRule.priority).all()
            warehouses = Warehouse.query.filter_by(status='active').order_by(Warehouse.code).all()
        except OperationalError:
            db.create_all()
            workstations = PrintWorkstation.query.order_by(PrintWorkstation.code).all()
            rules = PrintRouteRule.query.order_by(
                PrintRouteRule.business_event, PrintRouteRule.priority).all()
            warehouses = Warehouse.query.filter_by(status='active').order_by(Warehouse.code).all()
        return render_template(
            'print_routing.html', workstations=workstations, rules=rules,
            warehouses=warehouses, event_labels=BUSINESS_EVENT_LABELS)

    @app.route('/print_routing/download_agent')
    @login_required
    @require_role('admin')
    def print_routing_download_agent():
        """下载打印代理部署包（zip）：含 wms_print_agent.py + 预填配置的 agent_config.json。"""
        agent_src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                 'tools', 'print_agent', 'wms_print_agent.py')
        if not os.path.isfile(agent_src):
            return jsonify({'status': 'error', 'msg': '代理脚本不存在'}), 500
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(agent_src, 'wms_print_agent.py')
            cfg = {
                'server_url': request.host_url.rstrip('/'),
                'token': '在此粘贴工作站令牌（从 /print_routing 页面复制）',
                'poll_interval': 3,
                'heartbeat_interval': 60,
                'print_timeout': 120,
            }
            zf.writestr('agent_config.json', json.dumps(cfg, ensure_ascii=False, indent=2))
            readme = (
                "WMS 打印代理部署包\n"
                "====================\n"
                "1. 解压到任意目录（如 C:\\wms_agent\\）\n"
                "2. 编辑 agent_config.json，把 token 替换为 /print_routing 页面复制的令牌\n"
                "3. 双击 run.bat 启动代理（首次建议用 run.bat，稳定后改用 start.bat 后台运行）\n"
                "4. 验证：打开 /print_routing 页面，工作站状态应变为「在线」\n\n"
                "开机自启（推荐）：\n"
                "  schtasks /Create /TN \"WMS Print Agent\" /SC ONSTART /RU SYSTEM ^\n"
                "    /TR \"\\\"C:\\Path\\To\\pythonw.exe\\\" C:\\wms_agent\\wms_print_agent.py --config C:\\wms_agent\\agent_config.json\"\n"
            )
            zf.writestr('README.txt', readme)
            run_bat = "@echo off\r\npython wms_print_agent.py --config agent_config.json\r\npause\r\n"
            zf.writestr('run.bat', run_bat)
            start_bat = "@echo off\r\nstart /min pythonw wms_print_agent.py --config agent_config.json\r\n"
            zf.writestr('start.bat', start_bat)
        buf.seek(0)
        return send_file(buf, mimetype='application/zip',
                         as_attachment=True, download_name='wms_print_agent.zip')

    @app.route('/print_routing/workstations', methods=['POST'])
    # pydantic:reason=请求体经 WorkstationCreateRequest（BaseModel）校验
    @login_required
    @require_role('admin')
    def print_routing_workstation_add():
        from app import PrintWorkstation
        try:
            req = WorkstationCreateRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        if PrintWorkstation.query.filter_by(code=req.code).first():
            return jsonify({'status': 'error', 'msg': '工作站编码已存在'}), 400
        ws = PrintWorkstation(
            code=req.code, name=req.name, warehouse_id=req.warehouse_id,
            device_id=f'ws-{req.code}',
            status='offline', enabled=True,
            auth_token=secrets.token_urlsafe(32),
        )
        db.session.add(ws)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '新增成功', 'token': ws.auth_token})

    @app.route('/print_routing/workstations/<int:ws_id>/edit', methods=['POST'])
    # pydantic:reason=请求体经 WorkstationEditRequest（BaseModel）校验
    @login_required
    @require_role('admin')
    def print_routing_workstation_edit(ws_id):
        from app import PrintWorkstation
        try:
            req = WorkstationEditRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        ws = db.session.get(PrintWorkstation, ws_id)
        if not ws:
            return jsonify({'status': 'error', 'msg': '工作站不存在'}), 404
        ws.name = req.name
        ws.warehouse_id = req.warehouse_id
        ws.enabled = req.enabled
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '保存成功'})

    @app.route('/print_routing/workstations/<int:ws_id>/reset_token', methods=['POST'])
    # pydantic:reason=无请求体，令牌由服务端 secrets.token_urlsafe 生成
    @login_required
    @require_role('admin')
    def print_routing_workstation_reset_token(ws_id):
        from app import PrintWorkstation
        ws = db.session.get(PrintWorkstation, ws_id)
        if not ws:
            return jsonify({'status': 'error', 'msg': '工作站不存在'}), 404
        ws.auth_token = secrets.token_urlsafe(32)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '令牌已重置，请更新打印代理配置',
                        'token': ws.auth_token})

    @app.route('/print_routing/workstations/<int:ws_id>/delete', methods=['POST'])
    # pydantic:reason=无请求体，仅路径参数 ws_id（int）执行删除
    @login_required
    @require_role('admin')
    def print_routing_workstation_delete(ws_id):
        from app import PrintWorkstation
        ws = db.session.get(PrintWorkstation, ws_id)
        if not ws:
            return jsonify({'status': 'error', 'msg': '工作站不存在'}), 404
        blockers = _workstation_delete_blockers(ws)
        if blockers:
            return jsonify({'status': 'error',
                            'msg': '该工作站已有业务数据，不能删除：' + '、'.join(blockers)}), 400
        db.session.delete(ws)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '删除成功'})

    @app.route('/print_routing/printers', methods=['POST'])
    # pydantic:reason=请求体经 PrinterCreateRequest（BaseModel）校验
    @login_required
    @require_role('admin')
    def print_routing_printer_add():
        from app import PrintDevice, PrintWorkstation
        try:
            req = PrinterCreateRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        ws = db.session.get(PrintWorkstation, req.workstation_id)
        if not ws:
            return jsonify({'status': 'error', 'msg': '工作站不存在'}), 404
        system_name = req.system_name or req.display_name
        if PrintDevice.query.filter_by(workstation_id=ws.id, system_name=system_name).first():
            return jsonify({'status': 'error', 'msg': '该工作站下同名打印机已存在'}), 400
        printer = PrintDevice(
            workstation_id=ws.id, system_name=system_name,
            display_name=req.display_name, printer_type=req.printer_type,
            status='offline', enabled=req.enabled,
        )
        db.session.add(printer)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '新增成功'})

    @app.route('/print_routing/printers/<int:printer_id>/edit', methods=['POST'])
    # pydantic:reason=请求体经 PrinterEditRequest（BaseModel）校验
    @login_required
    @require_role('admin')
    def print_routing_printer_edit(printer_id):
        from app import PrintDevice
        try:
            req = PrinterEditRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        printer = db.session.get(PrintDevice, printer_id)
        if not printer:
            return jsonify({'status': 'error', 'msg': '打印机不存在'}), 404
        printer.display_name = req.display_name
        printer.printer_type = req.printer_type
        printer.enabled = req.enabled
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '保存成功'})

    @app.route('/print_routing/printers/<int:printer_id>/delete', methods=['POST'])
    # pydantic:reason=无请求体，仅路径参数 printer_id（int）执行删除
    @login_required
    @require_role('admin')
    def print_routing_printer_delete(printer_id):
        from app import PrintDevice
        printer = db.session.get(PrintDevice, printer_id)
        if not printer:
            return jsonify({'status': 'error', 'msg': '打印机不存在'}), 404
        if printer.print_route_rules:
            return jsonify({'status': 'error',
                            'msg': f'该打印机已被 {len(printer.print_route_rules)} 条路由规则引用，请先删除规则'}), 400
        db.session.delete(printer)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '删除成功'})

    @app.route('/print_routing/rules', methods=['POST'])
    # pydantic:reason=请求体经 RuleSaveRequest（BaseModel）校验
    @login_required
    @require_role('admin')
    def print_routing_rule_add():
        from app import PrintDevice, PrintRouteRule, PrintWorkstation
        try:
            req = RuleSaveRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        printer = db.session.get(PrintDevice, req.printer_id)
        if not printer or printer.workstation_id != req.workstation_id:
            return jsonify({'status': 'error', 'msg': '打印机不存在或不属于所选工作站'}), 400
        if not db.session.get(PrintWorkstation, req.workstation_id):
            return jsonify({'status': 'error', 'msg': '工作站不存在'}), 404
        rule = PrintRouteRule(
            name=req.name, business_event=req.business_event,
            warehouse_id=req.warehouse_id, workstation_id=req.workstation_id,
            printer_id=req.printer_id, priority=req.priority, enabled=req.enabled)
        db.session.add(rule)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '新增成功'})

    @app.route('/print_routing/rules/<int:rule_id>/edit', methods=['POST'])
    # pydantic:reason=请求体经 RuleSaveRequest（BaseModel）校验
    @login_required
    @require_role('admin')
    def print_routing_rule_edit(rule_id):
        from app import PrintDevice, PrintRouteRule
        try:
            req = RuleSaveRequest(**(request.get_json(silent=True) or {}))
        except Exception as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        rule = db.session.get(PrintRouteRule, rule_id)
        if not rule:
            return jsonify({'status': 'error', 'msg': '规则不存在'}), 404
        printer = db.session.get(PrintDevice, req.printer_id)
        if not printer or printer.workstation_id != req.workstation_id:
            return jsonify({'status': 'error', 'msg': '打印机不存在或不属于所选工作站'}), 400
        rule.name = req.name
        rule.business_event = req.business_event
        rule.warehouse_id = req.warehouse_id
        rule.workstation_id = req.workstation_id
        rule.printer_id = req.printer_id
        rule.priority = req.priority
        rule.enabled = req.enabled
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '保存成功'})

    @app.route('/print_routing/rules/<int:rule_id>/delete', methods=['POST'])
    # pydantic:reason=无请求体，仅路径参数 rule_id（int）执行删除
    @login_required
    @require_role('admin')
    def print_routing_rule_delete(rule_id):
        from app import PrintRouteRule
        rule = db.session.get(PrintRouteRule, rule_id)
        if not rule:
            return jsonify({'status': 'error', 'msg': '规则不存在'}), 404
        db.session.delete(rule)
        db.session.commit()
        return jsonify({'status': 'success', 'msg': '删除成功'})