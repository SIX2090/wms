#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印域模型（工作站 / 设备 / 路由 / 任务 / 模板）。

ARCH-MODELS-01（2026-09-15）自 app/app.py 模型区迁入，类定义逐字保留。
统一平铺导入 ``from db import db``（与 document_evidence.py 先例一致）。
"""

from db import db
from datetime import datetime

__all__ = [
    'ExcelPrintTemplate',
    'InOrderPrintTemplate',
    'LabelTemplate',
    'OutOrderPrintTemplate',
    'PrintDevice',
    'PrintJob',
    'PrintRouteRule',
    'PrintWorkstation',
]


class PrintWorkstation(db.Model):
    """打印工作站：一台负责实际出纸的本地电脑（Windows 打印代理运行处）。

    PRINT-ROUTING-F01-P3：新增 auth_token（工作站令牌，供 Windows 打印代理
    免账号密码调用 agent API）与 last_heartbeat（最近心跳时间，超过在线窗口
    视为离线，路由解析不再向其派发任务）。
    """
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    device_id = db.Column(db.String(128), unique=True, nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))
    status = db.Column(db.String(20), default='offline', nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    auth_token = db.Column(db.String(128), unique=True)  # 工作站令牌（agent API 鉴权）
    last_heartbeat = db.Column(db.DateTime)  # Windows 打印代理最近心跳时间
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    warehouse = db.relationship('Warehouse', backref='print_workstations')


class PrintDevice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workstation_id = db.Column(db.Integer, db.ForeignKey('print_workstation.id'), nullable=False)
    system_name = db.Column(db.String(200), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    printer_type = db.Column(db.String(20), default='mixed', nullable=False)
    status = db.Column(db.String(20), default='offline', nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    workstation = db.relationship('PrintWorkstation', backref='print_devices')
    __table_args__ = (db.UniqueConstraint('workstation_id', 'system_name', name='uq_print_device_system_name'),)


class PrintRouteRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    business_event = db.Column(db.String(30), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))
    workstation_id = db.Column(db.Integer, db.ForeignKey('print_workstation.id'), nullable=False)
    printer_id = db.Column(db.Integer, db.ForeignKey('print_device.id'), nullable=False)
    priority = db.Column(db.Integer, default=100, nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    warehouse = db.relationship('Warehouse', backref='print_route_rules')
    workstation = db.relationship('PrintWorkstation', backref='print_route_rules')
    printer = db.relationship('PrintDevice', backref='print_route_rules')
    __table_args__ = (db.Index('idx_print_route_match', 'business_event', 'warehouse_id', 'priority'),)


class PrintJob(db.Model):
    """远程打印任务队列。

    用于「手机扫码出库 → 本地电脑打印机出纸」场景：
    手机端通过 POST /print_queue/jobs 写入一条任务，
    本地电脑打开 /print_queue/station 守护页面轮询拉取并自动打印。

    job_type 取值：
      - out_order : 领料单/出库单（target_id = OutOrder.id）
      - in_order  : 采购入库单（target_id = InOrder.id）
      - label     : 物料标签（target_ids = 逗号分隔的 Material.id 列表）

    状态机：
      pending  → 桌面端尚未拉取
      printing → 桌面端已拉取，正在调起浏览器打印
      done     → 打印对话框已关闭（实际是否出纸由打印机决定）
      failed   → 拉取后报错（error_msg 记录原因）
    """
    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(20), nullable=False)  # out_order / in_order / label
    target_id = db.Column(db.Integer)  # 单据 ID（label 时为空）
    target_ids = db.Column(db.String(500))  # label 场景：逗号分隔的物料 ID
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending/printing/done/failed
    copies = db.Column(db.Integer, default=1)  # 打印份数
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))  # 提交者
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    printed_at = db.Column(db.DateTime)  # 桌面端标记完成时间
    error_msg = db.Column(db.String(500))  # 失败原因
    attempts = db.Column(db.Integer, default=0)  # 尝试次数，防止死循环
    # BUG-2026-08-19-010：认领（置 printing）时间。僵尸回收按此判定；
    # 原按 created_at 近似会把积压 >5min 的 pending 任务认领后立即回收，无限循环
    printing_started_at = db.Column(db.DateTime)
    lease_token = db.Column(db.String(128))
    workstation_id = db.Column(db.Integer, db.ForeignKey('print_workstation.id'))
    printer_id = db.Column(db.Integer, db.ForeignKey('print_device.id'))
    route_rule_id = db.Column(db.Integer, db.ForeignKey('print_route_rule.id'))
    source_event = db.Column(db.String(30), default='manual', nullable=False)

    __table_args__ = (
        db.Index('idx_print_job_status', 'status'),
        db.Index('idx_print_job_created', 'created_at'),
        db.Index('idx_print_job_workstation_status', 'workstation_id', 'status'),
    )

    operator = db.relationship('User', backref='print_jobs')  # 提交者
    workstation = db.relationship('PrintWorkstation', backref='print_jobs')
    printer = db.relationship('PrintDevice', backref='print_jobs')
    route_rule = db.relationship('PrintRouteRule', backref='print_jobs')


class LabelTemplate(db.Model):
    """Label template."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Name
    width = db.Column(db.Integer, default=100)  # (mm)
    height = db.Column(db.Integer, default=60)  # (mm)
    cell_width = db.Column(db.Integer, default=20)  # Cell width (mm)
    cell_height = db.Column(db.Integer, default=10)  # Cell height (mm)
    cols = db.Column(db.Integer, default=5)  # Columns
    rows = db.Column(db.Integer, default=6)  # Rows
    layout = db.Column(db.Text)  # Layout JSON
    is_default = db.Column(db.Boolean, default=False)  # Default template flag
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class InOrderPrintTemplate(db.Model):
    """Inbound order print template."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Name
    template_type = db.Column(db.String(20), default='excel')  # Type: excel/html
    excel_template_path = db.Column(db.String(500))  # Excel template path
    html_template_content = db.Column(db.Text)  # HTML template content
    is_default = db.Column(db.Boolean, default=False)  # Default template flag
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class OutOrderPrintTemplate(db.Model):
    """Outbound order print template."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Name
    template_type = db.Column(db.String(20), default='excel')  # Type: excel/html
    excel_template_path = db.Column(db.String(500))  # Excel template path
    html_template_content = db.Column(db.Text)  # HTML template content
    is_default = db.Column(db.Boolean, default=False)  # Default template flag
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class ExcelPrintTemplate(db.Model):
    """通用单据、列表、报表 Excel 打印模板。"""
    __tablename__ = 'excel_print_template'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(30), nullable=False, index=True)
    target_code = db.Column(db.String(80), nullable=False, index=True)
    template_type = db.Column(db.String(20), nullable=False, default='excel')
    excel_template_path = db.Column(db.String(500), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
