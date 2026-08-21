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
    system_name: str | None = ''
    printer_type: str = 'mixed'
    enabled: bool = True

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError('打印机名称必填且不超过 100 字符')
        return v

    @field_validator('system_name', mode='before')
    @classmethod
    def validate_system_name(cls, v: str | None) -> str:
        return v.strip() if v else ''

    @field_validator('printer_type')
    @classmethod
    def validate_printer_type(cls, v: str) -> str:
        if v not in ('label', 'document', 'mixed'):
            raise ValueError('打印机类型必须是 label / document / mixed')
        return v


class PrinterEditRequest(BaseModel):
    """编辑打印机。

    BUG-2026-08-19-011：原编辑不能改 system_name，手填错系统名的打印机
    只能删除重建（还会被路由规则引用挡住）。system_name 留空 = 保持不变。
    """
    display_name: str
    system_name: str | None = ''
    printer_type: str = 'mixed'
    enabled: bool = True

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError('打印机名称必填且不超过 100 字符')
        return v

    @field_validator('system_name', mode='before')
    @classmethod
    def validate_system_name(cls, v: str | None) -> str:
        v = v.strip() if v else ''
        if len(v) > 200:
            raise ValueError('系统名称不超过 200 字符')
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
        """下载打印代理部署包（zip）：含 wms_print_agent.py + 预填配置的 agent_config.json。

        ?ws=<工作站编码> 指定工作站预填其令牌；未指定且仅有一个工作站时自动用它。"""
        from app import PrintWorkstation
        agent_src = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                 'tools', 'print_agent', 'wms_print_agent.py')
        if not os.path.isfile(agent_src):
            return jsonify({'status': 'error', 'msg': '代理脚本不存在'}), 500
        ws = None
        ws_code = (request.args.get('ws') or '').strip()
        if ws_code:
            ws = PrintWorkstation.query.filter_by(code=ws_code).first()
        elif PrintWorkstation.query.count() == 1:
            ws = PrintWorkstation.query.first()
        token = ws.auth_token if ws else '在此粘贴工作站令牌（从 /print_routing 页面复制）'
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(agent_src, 'wms_print_agent.py')
            cfg = {
                'server_url': request.host_url.rstrip('/'),
                'token': token,
                'poll_interval': 3,
                'heartbeat_interval': 60,
                'print_timeout': 120,
            }
            zf.writestr('agent_config.json', json.dumps(cfg, ensure_ascii=False, indent=2))
            token_note = (f"（工作站 {ws.code} 的令牌已预填）" if ws
                          else "（需替换为 /print_routing 页面复制的令牌）")
            readme = (
                "WMS 打印代理部署包\n"
                "====================\n"
                f"agent_config.json 的 token {token_note}\n\n"
                "1. 解压到任意目录（如 C:\\wms_agent\\）\n"
                "2. 双击 run.bat 启动代理（bat 会自动查找 Python：PATH → 常见安装目录 →\n"
                "   py 启动器；找不到会提示先安装 Python 3.8+ 并勾选 Add Python to PATH）。\n"
                "   首次建议用 run.bat，稳定后改用 start.bat 后台运行\n"
                "3. 验证：打开 /print_routing 页面，工作站状态应变为「在线」\n\n"
                "开机自启（推荐）：\n"
                "  schtasks /Create /TN \"WMS Print Agent\" /SC ONSTART /RU SYSTEM ^\n"
                "    /TR \"\\\"C:\\Path\\To\\pythonw.exe\\\" C:\\wms_agent\\wms_print_agent.py --config C:\\wms_agent\\agent_config.json\"\n"
                "  更省事：双击包内 install-service.bat 即可一键注册开机自启（自动提权、\n"
                "  自动定位 pythonw、自动带配置路径），上面的命令可省略。\n"
            )
            zf.writestr('README.txt', readme)
            # BUG-2026-08-19-012：原 bat 裸调 python/pythonw，Python 未加入 PATH 的电脑
            # （如 Win7 手动装 3.8 没勾 Add to PATH）双击即报「'python' 不是内部或外部
            # 命令」。改为自动定位：PATH（排除 WindowsApps 商店假 python）→ 常见安装
            # 目录 → py 启动器；仍找不到则给中文指引。bat 用 GBK 编码（zh-CN 默认
            # cp936 下中文可读），CRLF 行尾。
            py_detect = [
                '@echo off',
                'setlocal',
                'cd /d "%~dp0"',
                'set "PY="',
                'for /f "delims=" %%i in (\'where python.exe 2^>nul ^| findstr /v /i "WindowsApps"\') do if not defined PY set "PY=%%i"',
                # BUG-2026-08-20-002：这三行必须用「非 raw」字符串。raw 字符串里 \' 不会被
                # 折叠成 '，生成到 run.bat/start.bat 后变成 in (\'dir ...\')，cmd 无法识别
                # for /f 的单引号命令形式，把它当作文件执行 → 报「系统找不到文件 'dir」。
                # 非 raw 字符串里 \' → '、路径里的 \\ → \，生成的行才是 in ('dir ...')。
                'if not defined PY for /f "delims=" %%i in (\'dir /b /s "%LocalAppData%\\Programs\\Python\\Python3*\\python.exe" 2^>nul\') do if not defined PY set "PY=%%i"',
                'if not defined PY for /f "delims=" %%i in (\'dir /b /s "%ProgramFiles%\\Python3*\\python.exe" 2^>nul\') do if not defined PY set "PY=%%i"',
                'if not defined PY for /f "delims=" %%i in (\'dir /b /s "C:\\Python3*\\python.exe" 2^>nul\') do if not defined PY set "PY=%%i"',
                'if not defined PY (',
                '  where py.exe >nul 2>nul && set "PY=py"',
                ')',
                'if not defined PY (',
                '  echo [错误] 未找到 Python（python.exe）。',
                '  echo 请安装 Python 3.8+ 时勾选 "Add Python to PATH"，',
                '  echo 或把 python.exe 所在目录加入环境变量 PATH 后重新双击本文件。',
                '  pause',
                '  exit /b 1',
                ')',
            ]
            run_bat = "\r\n".join(
                py_detect + [
                    'echo 使用 Python：%PY%',
                    '"%PY%" wms_print_agent.py --config agent_config.json',
                    'pause',
                ]) + "\r\n"
            zf.writestr('run.bat', run_bat.encode('gbk'))
            start_bat = "\r\n".join(
                py_detect + [
                    'set "PYW=%PY:python.exe=pythonw.exe%"',
                    'if not exist "%PYW%" set "PYW=%PY%"',
                    'start "" /min "%PYW%" wms_print_agent.py --config agent_config.json',
                ]) + "\r\n"
            zf.writestr('start.bat', start_bat.encode('gbk'))
            # PRINT-ROUTING-F01-P5 / 85-C2：一键注册开机自启的 install-service.bat。
            # 复用 py_detect 自动定位 Python（排除 WindowsApps 假 python → 常见安装
            # 目录 → py 启动器）；自动提权（schtasks 注册需管理员）；python.exe 推导
            # pythonw.exe 后台运行；自动带 --config agent_config.json。GBK + CRLF。
            install_service = [
                '@echo off',
                'setlocal',
                'rem --- 管理员权限自检与提权（schtasks 注册需要管理员） ---',
                'net session >nul 2>&1',
                'if %errorlevel% neq 0 (',
                '  echo 需要管理员权限注册开机自启，正在申请提权...',
                "  powershell -NoProfile -Command \"Start-Process -FilePath \'%~f0\' -Verb RunAs\"",
                '  exit /b',
                ')',
            ] + py_detect[2:] + [
                'rem --- 定位 pythonw.exe（后台运行，取不到回退 python） ---',
                'set "PYW=%PY:python.exe=pythonw.exe%"',
                'if not exist "%PYW%" set "PYW=%PY%"',
                'echo 使用 PythonW：%PYW%',
                'rem --- 注册开机自启任务（已存在则覆盖，/F） ---',
                'schtasks /Create /F /TN "WMS Print Agent" /SC ONSTART /RU SYSTEM /TR ""%PYW%" "%~dp0wms_print_agent.py" --config "%~dp0agent_config.json""',
                'if %errorlevel% equ 0 (',
                '  echo.',
                '  echo [成功] 已注册开机自启任务 WMS Print Agent。',
                '  echo        开机后代理将自动在后台运行。',
                '  pause',
                '  exit /b 0',
                ') else (',
                '  echo.',
                '  echo [失败] 注册失败，请查看上方报错。',
                '  echo        如需手动注册，可参考 README.txt 的 schtasks 命令。',
                '  pause',
                '  exit /b 1',
                ')',
            ]
            zf.writestr('install-service.bat', ("\r\n".join(install_service)).encode('gbk'))
        buf.seek(0)
        suffix = f"_{ws.code}" if ws else ""
        return send_file(buf, mimetype='application/zip',
                         as_attachment=True,
                         download_name=f'wms_print_agent{suffix}.zip')

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

    @app.route('/print_routing/workstations/<int:ws_id>/printers/known', methods=['GET'])
    @login_required
    @require_role('admin')
    def print_routing_workstation_known_printers(ws_id):
        """返回指定工作站已知的本机系统打印机名列表（代理心跳上报/历史登记过）。

        供「新增打印机」弹窗「系统名称」下拉选择，避免手填晦涩的 Windows 系统名。
        """
        from app import PrintDevice, PrintWorkstation
        ws = db.session.get(PrintWorkstation, ws_id)
        if not ws:
            return jsonify({'status': 'error', 'msg': '工作站不存在'}), 404
        names = sorted({d.system_name for d in PrintDevice.query
                        .filter_by(workstation_id=ws.id).all() if d.system_name})
        return jsonify({
            'status': 'success',
            'data': {
                'workstation_id': ws_id,
                'known_printers': names,
                'proxy_seen': bool(ws.last_heartbeat),
            },
        })

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
        new_system_name = req.system_name or ''
        if new_system_name and new_system_name != printer.system_name:
            dup = PrintDevice.query.filter(
                PrintDevice.workstation_id == printer.workstation_id,
                PrintDevice.system_name == new_system_name,
                PrintDevice.id != printer.id,
            ).first()
            if dup:
                return jsonify({'status': 'error',
                                'msg': '该工作站下同名系统名称的打印机已存在'}), 400
            printer.system_name = new_system_name
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