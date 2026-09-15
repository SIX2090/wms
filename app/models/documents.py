#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""出入库及业务单据模型（采购 / 销售 / 领料 / 调拨 / 盘点 / 调整 / 售后 / 委外 / BOM）。

ARCH-MODELS-01（2026-09-15）自 app/app.py 模型区迁入，类定义逐字保留。
统一平铺导入 ``from db import db``（与 document_evidence.py 先例一致）。
"""

from db import db
from datetime import datetime
from datetime import date

__all__ = [
    'AdjustmentOrder',
    'AdjustmentOrderItem',
    'AfterSaleOutOrder',
    'AfterSaleOutOrderItem',
    'BOM',
    'BOMItem',
    'DocumentPushLine',
    'InOrder',
    'InOrderItem',
    'InventoryCheck',
    'InventoryCheckItem',
    'InventoryCheckScan',
    'InventoryCheckScanItem',
    'OpeningStock',
    'OpeningStockDoc',
    'OperationLog',
    'OutOrder',
    'OutOrderItem',
    'ProductionRequisition',
    'ProductionRequisitionItem',
    'PurchaseOrder',
    'PurchaseOrderItem',
    'PurchaseRequest',
    'PurchaseRequestItem',
    'SalesOrder',
    'SalesOrderItem',
    'SubcontractIssue',
    'SubcontractIssueItem',
    'SubcontractItem',
    'SubcontractOrder',
    'SubcontractProgress',
    'SubcontractReceive',
    'SubcontractReceiveItem',
    'TransferOrder',
    'TransferOrderItem',
]


class OpeningStockDoc(db.Model):
    """期初库存单据头（ARCH-OS-DOC-01，2026-09-15）。

    用户需求：期初库存要能"做几张单"——一个仓库一张单 / 一批物料一张单 /
    不同仓管各建各的单，并且要能对导入进来的单据改日期 + 首/上/下/末 导航。

    改造前 OpeningStock 是"每 (物料,仓库) 一条余额"的扁平台账，没有单据概念。
    现在升级为"单据头 + 明细行"：

    - 单据头（本表）承载 doc_no / date / warehouse / remark；
    - 明细行为 OpeningStock（新增 doc_id 指向本表）；
    - 某物料在某仓库的期初总量 = 该 (material_id, warehouse_id) 下所有明细行
      quantity 之和（见 INVENTORY_TRUTH.md 的累计口径定义）。

    兼容性：opening_stock.doc_id 为 NULL 的行 = 历史直连台账（迁移前 / 未归单
    的旧写入），不参与单据导航，但仍计入累计库存。
    """
    __tablename__ = 'opening_stock_doc'
    __table_args__ = (
        db.Index('idx_opening_stock_doc_no', 'doc_no'),
        db.Index('idx_opening_stock_doc_date', 'date'),
        db.Index('idx_opening_stock_doc_warehouse', 'warehouse_id'),
        db.Index('idx_opening_stock_doc_created', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    # QS + YYMM + 4 位序号（如 QS26090001），由 generate_order_no('QS') 取号
    doc_no = db.Column(db.String(50), unique=True, nullable=False)
    # 单据建账日期：权威值；用户在单头改日期时同步覆盖该单所有明细行的 date
    date = db.Column(db.Date, default=date.today)
    # 单据仓库：明细行仓库的默认值，历史数据可能为空
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))
    # active：正常单据。预留作废流转；当前删除走物理删除 + 库存回冲
    status = db.Column(db.String(20), nullable=False, default='active')
    remark = db.Column(db.String(500))
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    warehouse = db.relationship('Warehouse', backref=db.backref('opening_stock_docs'))
    operator = db.relationship('User', backref='opening_stock_docs')
    # 明细行：删单据头时级联删明细（调用方必须先逐行回冲库存，见 _reverse_opening_stock_line）
    lines = db.relationship(
        'OpeningStock',
        backref=db.backref('doc', lazy='joined'),
        order_by='OpeningStock.id',
        cascade='all, delete-orphan',
        foreign_keys='OpeningStock.doc_id',
    )


class OpeningStock(db.Model):
    """期初库存明细行（原"每 (物料,仓库) 一条余额台账"，ARCH-OS-DOC-01 升级为单据明细行）。

    唯一性收窄：改造前 (material_id, warehouse_id) 全局唯一，现改为
    (material_id, warehouse_id, doc_id) 单据内唯一——同一张单里重复录同一物料
    仍是真错误，但不同单据可以各录一份（用户确认：允许同物料同仓多张单）。

    doc_id 为 NULL 的行不参与该唯一约束（SQLite 的 UNIQUE 视含 NULL 的元组互不相等），
    兼容历史直连台账写入。
    """
    __tablename__ = 'opening_stock'
    __table_args__ = (
        # ARCH-OS-DOC-01：单据内同物料同仓唯一（替代 AI-OS-MW-001 的全局唯一）
        db.UniqueConstraint('material_id', 'warehouse_id', 'doc_id', name='uix_opening_stock_line_doc'),
        db.Index('idx_opening_stock_material', 'material_id'),
        db.Index('idx_opening_stock_warehouse', 'warehouse_id'),
        db.Index('idx_opening_stock_created', 'created_at'),
        db.Index('idx_opening_stock_doc', 'doc_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    # ARCH-OS-DOC-01：所属单据头；NULL = 历史直连台账（迁移前 / 未归单的旧写入）
    doc_id = db.Column(db.Integer, db.ForeignKey('opening_stock_doc.id'))
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))  # AI-OS-MW-001: NULL 表示历史未指定仓库
    # AI-OS-APP-001：期初建账日期（旧记录回填为建账首日 2023-01-01）
    date = db.Column(db.Date, default=date.today)
    # BUG-2026-08-16-002：期初库位（开启库位管理时同步写入库位账；空表示未指定，
    # 落库位账时以仓库名作占位行，保证仓库级库存聚合可见）
    location = db.Column(db.String(100), nullable=False, default='')
    quantity = db.Column(db.Float, nullable=False, default=0)
    price = db.Column(db.Float, nullable=False, default=0)
    amount = db.Column(db.Float, nullable=False, default=0)
    remark = db.Column(db.String(500))
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    material = db.relationship('Material', backref=db.backref('opening_stock_records'))
    warehouse = db.relationship('Warehouse', backref=db.backref('opening_stocks'))
    operator = db.relationship('User', backref='opening_stocks')
    # doc backref 由 OpeningStockDoc.lines 定义


class InOrder(db.Model):
    """Inbound order."""
    __tablename__ = 'in_order'
    __table_args__ = (
        db.Index('idx_in_order_no', 'order_no'),
        db.Index('idx_in_order_date', 'date'),
        db.Index('idx_in_order_status', 'status'),
        db.Index('idx_in_order_created', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)  # Inbound order number
    date = db.Column(db.Date, default=date.today)  # Inbound date
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))  # Supplier ID
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))  # Other inbound / customer-supplied material owner
    business_type = db.Column(db.String(50), default='采购入库')  # Business type: purchase/product inbound
    purpose = db.Column(db.String(200))  # Inbound purpose
    warehouse = db.Column(db.String(100), nullable=False, default='')  # Warehouse name (AGENTS.md: 始终必填)
    location = db.Column(db.String(100), nullable=False, default='')  # 库位（开启库位管理时必填）
    source_purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'))
    # P1-5 销售退货入库：来源销售订单（business_type='销售退货入库' 时填写；
    # 客户退回归属原单，退货率可统计。存量单据历史归属留空不猜——INVENTORY_TRUTH §3）
    source_sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_order.id'))
    source_sales_order_no = db.Column(db.String(50))  # 冗余销售订单号（原单变更后历史单据不变）
    auto_push_requisition = db.Column(db.Boolean, nullable=False, default=False)
    remark = db.Column(db.String(200))  # Remark
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))  # 关联合同档案
    contract_no = db.Column(db.String(50))  # 冗余合同编号（合同变更后历史单据不变）
    project_name = db.Column(db.String(200))  # 冗余工程名称
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    total_amount = db.Column(db.Float, default=0)  # Amount
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    supplier = db.relationship('Supplier', backref='in_orders')  # Related supplier
    customer = db.relationship('Customer', backref='other_in_orders')
    operator = db.relationship('User', backref='in_orders')  # Operator
    source_purchase_order = db.relationship('PurchaseOrder', backref='in_orders')
    source_sales_order = db.relationship('SalesOrder', backref='sales_return_in_orders', foreign_keys=[source_sales_order_id])
    contract = db.relationship('Contract', backref='in_orders')  # 关联合同档案


class InOrderItem(db.Model):
    """Inbound order item."""
    id = db.Column(db.Integer, primary_key=True)
    in_order_id = db.Column(db.Integer, db.ForeignKey('in_order.id'), nullable=False)  # Inbound order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    source_purchase_order_item_id = db.Column(db.Integer, db.ForeignKey('purchase_order_item.id'))
    # P1-5 销售退货入库：原销售订单行（退货限额 = 行 shipped_quantity − 已退量聚合）
    source_sales_order_item_id = db.Column(db.Integer, db.ForeignKey('sales_order_item.id'))
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    price = db.Column(db.Float, nullable=False)  # Unit price
    amount = db.Column(db.Float, nullable=False)  # Amount
    remark = db.Column(db.String(500))  # Row-level remark
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    contract_no = db.Column(db.String(50))
    project_name = db.Column(db.String(200))
    is_customer_supplied = db.Column(db.Boolean, nullable=False, default=False)

    in_order = db.relationship('InOrder', backref='items')  # Related in order
    material = db.relationship('Material', backref='in_order_items')  # Related material
    source_purchase_order_item = db.relationship('PurchaseOrderItem', backref='in_order_items')
    source_sales_order_item = db.relationship('SalesOrderItem', backref='sales_return_in_items')
    contract = db.relationship('Contract', foreign_keys=[contract_id])


class OutOrder(db.Model):
    """Outbound order."""
    __tablename__ = 'out_order'
    __table_args__ = (
        db.Index('idx_out_order_no', 'order_no'),
        db.Index('idx_out_order_date', 'date'),
        db.Index('idx_out_order_status', 'status'),
        db.Index('idx_out_order_created', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)  # Outbound order number
    date = db.Column(db.Date, default=date.today)  # Out date
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))  # Department ID
    customer = db.Column(db.String(100))  # Legacy customer/department text
    business_type = db.Column(db.String(50))  # Business type
    warehouse = db.Column(db.String(100), nullable=False, default='')  # Warehouse name (AGENTS.md: 始终必填)
    location = db.Column(db.String(100), nullable=False, default='')  # 库位（开启库位管理时必填）
    purpose = db.Column(db.String(200))  # Outbound purpose
    picker = db.Column(db.String(50))  # Pick person (领料人)
    source_sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_order.id'))  # 关联销售订单ID（外键，替代 purpose 字符串解析）
    remark = db.Column(db.String(200))  # Remark
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))  # 关联合同档案
    contract_no = db.Column(db.String(50))  # 冗余合同编号（合同变更后历史单据不变）
    project_name = db.Column(db.String(200))  # 冗余工程名称
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    total_amount = db.Column(db.Float, default=0)  # Amount
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    department = db.relationship('Department', backref='out_orders')  # Related department
    operator = db.relationship('User', backref='out_orders')  # Operator
    source_sales_order = db.relationship('SalesOrder', backref='outbound_orders', foreign_keys=[source_sales_order_id])  # 关联销售订单
    contract = db.relationship('Contract', backref='out_orders')  # 关联合同档案


class OutOrderItem(db.Model):
    """Outbound order item."""
    id = db.Column(db.Integer, primary_key=True)
    out_order_id = db.Column(db.Integer, db.ForeignKey('out_order.id'), nullable=False)  # Outbound order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    source_sales_order_item_id = db.Column(db.Integer, db.ForeignKey('sales_order_item.id'))  # 来源销售订单明细
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    price = db.Column(db.Float, nullable=False)  # Unit price
    amount = db.Column(db.Float, nullable=False)  # Amount
    remark = db.Column(db.String(500))  # Row remark
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    contract_no = db.Column(db.String(50))
    project_name = db.Column(db.String(200))

    out_order = db.relationship('OutOrder', backref='items')  # Related out order
    material = db.relationship('Material', backref='out_order_items')  # Related material
    source_sales_order_item = db.relationship('SalesOrderItem', backref='sales_out_order_items')
    contract = db.relationship('Contract', foreign_keys=[contract_id])


class InventoryCheck(db.Model):
    """Inventory check order."""
    id = db.Column(db.Integer, primary_key=True)
    check_no = db.Column(db.String(50), unique=True, nullable=False)  # Order number
    date = db.Column(db.Date, default=date.today)  # Date
    # BUG-2026-08-02-012：盘点仓库，必填（AGENTS.md 规则）。
    warehouse = db.Column(db.String(100), nullable=False, default='')
    remark = db.Column(db.String(200))  # Remark
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed
    # INV-BATCH-001-A：批次账面冻结时点。首次写入盘点明细时设置，之后
    # 差异 = 实盘 − 冻结账面，不随后续出入库漂移（多人协作盘点的基础）。
    frozen_at = db.Column(db.DateTime)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    operator = db.relationship('User', backref='inventory_checks')  # Operator


class InventoryCheckItem(db.Model):
    """Inventory check item."""
    id = db.Column(db.Integer, primary_key=True)
    inventory_check_id = db.Column(db.Integer, db.ForeignKey('inventory_check.id'), nullable=False)  # Inventory check ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    system_stock = db.Column(db.Float, nullable=False)  # System inventory
    actual_stock = db.Column(db.Float, nullable=False)  # Actual inventory
    difference = db.Column(db.Float, nullable=False)  # Difference
    reason = db.Column(db.String(200))  # Difference
    # INV-BATCH-001-A：行级盘点归属——多人协作批次下谁盘的、何时盘的。
    counted_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    counted_at = db.Column(db.DateTime)
    # 盘点区域（area）：物料分处多区时按"物料+区域"分行盘点，汇总按物料净额合并。
    area = db.Column(db.String(100), nullable=False, default='')

    inventory_check = db.relationship('InventoryCheck', backref='items')  # Related check order
    material = db.relationship('Material', backref='inventory_check_items')  # Related material
    counted_by_user = db.relationship('User', foreign_keys=[counted_by])  # 盘点人（单向，无 backref）


class InventoryCheckScan(db.Model):
    """Inventory check scan order."""
    __tablename__ = 'inventory_check_scan'

    id = db.Column(db.Integer, primary_key=True)
    check_no = db.Column(db.String(50), unique=True, nullable=False)  # Order number
    date = db.Column(db.Date, default=date.today)  # Date
    warehouse = db.Column(db.String(100), nullable=False, default='')  # Warehouse name (AGENTS.md: 始终必填)
    remark = db.Column(db.String(200))  # Remark
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed/void（INV-REVERT-001 作废留痕）
    # INV-BATCH-001-A：挂钩盘点批次（PC 盘点单 InventoryCheck.id）。
    # 挂批次的扫码盘点不再独立生成调整草稿，差异由批次 complete 按
    # 冻结账面统一生成；为 NULL 时维持独立单模式（向后兼容）。
    check_id = db.Column(db.Integer, db.ForeignKey('inventory_check.id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    operator = db.relationship('User', backref='check_scans')  # Operator
    batch = db.relationship('InventoryCheck', foreign_keys=[check_id])  # 挂钩批次（单向，无 backref）


class InventoryCheckScanItem(db.Model):
    """Inventory check scan item."""
    __tablename__ = 'inventory_check_scan_item'

    id = db.Column(db.Integer, primary_key=True)
    check_scan_id = db.Column(db.Integer, db.ForeignKey('inventory_check_scan.id'))
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'))

    system_stock = db.Column(db.Float, nullable=False, default=0)
    actual_stock = db.Column(db.Float, nullable=False, default=0)
    difference = db.Column(db.Float, nullable=False, default=0)
    # 盘点区域（area）：与批次行（material_id, area）同键，扫码留痕可回溯到区。
    area = db.Column(db.String(100), nullable=False, default='')

    created_at = db.Column(db.DateTime, default=datetime.now)

    check_scan = db.relationship('InventoryCheckScan', backref='items')
    material = db.relationship('Material', backref='check_scan_items')


class SubcontractOrder(db.Model):
    """Subcontract order."""
    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)  # Order number
    date = db.Column(db.Date, default=date.today)  # Date
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))  # Processing supplierID
    contact = db.Column(db.String(50))  # Contact
    phone = db.Column(db.String(20))  # Contact phone
    deadline = db.Column(db.Date)  # Date
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    status = db.Column(db.String(20), default='pending')  # Status: pending/processing/completed
    total_amount = db.Column(db.Float, default=0)  # Amount
    warehouse = db.Column(db.String(100), nullable=False, default='')  # 仓库（AGENTS.md: 始终必填）
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    supplier = db.relationship('Supplier', backref='subcontract_orders')  # Related supplier
    operator = db.relationship('User', backref='subcontract_orders')  # Operator


class SubcontractIssue(db.Model):
    """Subcontract issue order."""
    id = db.Column(db.Integer, primary_key=True)
    issue_no = db.Column(db.String(50), unique=True, nullable=False)  # Order number
    date = db.Column(db.Date, default=date.today)  # Date
    subcontract_order_id = db.Column(db.Integer, db.ForeignKey('subcontract_order.id'))  # Related subcontract order
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))  # Processing supplier ID
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed
    warehouse = db.Column(db.String(100), nullable=False, default='')  # 仓库（AGENTS.md: 始终必填）
    location = db.Column(db.String(100), nullable=False, default='')  # 库位（BUG-2026-08-16-001：开启库位管理时写库位账）
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    subcontract_order = db.relationship('SubcontractOrder', backref='issue_orders')  # Related subcontract order
    supplier = db.relationship('Supplier', backref='subcontract_issues')  # Related supplier
    operator = db.relationship('User', backref='subcontract_issues')  # Operator


class SubcontractIssueItem(db.Model):
    """Subcontract issue item."""
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('subcontract_issue.id'), nullable=False)  # Issue order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # Unit ID
    remark = db.Column(db.String(200))  # Remark

    issue = db.relationship('SubcontractIssue', backref='items')  # Related issue order
    material = db.relationship('Material', backref='subcontract_issue_items')  # Related material
    unit = db.relationship('Unit', backref='subcontract_issue_items')  # Related unit


class SubcontractReceive(db.Model):
    """Subcontract receive order."""
    id = db.Column(db.Integer, primary_key=True)
    receive_no = db.Column(db.String(50), unique=True, nullable=False)  # Receive order number
    date = db.Column(db.Date, default=date.today)  # Receive date
    subcontract_order_id = db.Column(db.Integer, db.ForeignKey('subcontract_order.id'))  # Related subcontract order
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))  # Processing supplier ID
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed
    warehouse = db.Column(db.String(100), nullable=False, default='')  # 仓库（AGENTS.md: 始终必填）
    location = db.Column(db.String(100), nullable=False, default='')  # 库位（BUG-2026-08-16-001：开启库位管理时写库位账）
    total_quantity = db.Column(db.Float, default=0)  # Total quantity
    total_scrap = db.Column(db.Float, default=0)  # Total scrap quantity
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    subcontract_order = db.relationship('SubcontractOrder', backref='receive_orders')  # Related subcontract order
    supplier = db.relationship('Supplier', backref='subcontract_receives')  # Related supplier
    operator = db.relationship('User', backref='subcontract_receives')  # Operator


class SubcontractReceiveItem(db.Model):
    """Subcontract receive item."""
    id = db.Column(db.Integer, primary_key=True)
    receive_id = db.Column(db.Integer, db.ForeignKey('subcontract_receive.id'), nullable=False)  # Receive order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    scrap_quantity = db.Column(db.Float, default=0)  # Scrap quantity
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # Unit ID
    price = db.Column(db.Float, default=0)  # Unit price
    amount = db.Column(db.Float, default=0)  # Amount
    remark = db.Column(db.String(200))  # Remark

    receive = db.relationship('SubcontractReceive', backref='items')  # Related in order
    material = db.relationship('Material', backref='subcontract_receive_items')  # Related material
    unit = db.relationship('Unit', backref='subcontract_receive_items')  # Related unit


class SubcontractProgress(db.Model):
    """Subcontract progress record."""
    id = db.Column(db.Integer, primary_key=True)
    subcontract_order_id = db.Column(db.Integer, db.ForeignKey('subcontract_order.id'), nullable=False)  # Related subcontract order
    process_date = db.Column(db.Date, default=date.today)  # Date
    process_type = db.Column(db.String(50))  # Process type, such as issue or receive
    quantity = db.Column(db.Float, default=0)  # Quantity
    status = db.Column(db.String(50))  # Status description
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    subcontract_order = db.relationship('SubcontractOrder', backref='progress_records')  # Related subcontract order
    operator = db.relationship('User', backref='subcontract_progress')  # Operator


class SubcontractItem(db.Model):
    """Subcontract material item."""
    id = db.Column(db.Integer, primary_key=True)
    subcontract_order_id = db.Column(db.Integer, db.ForeignKey('subcontract_order.id'), nullable=False)  # Subcontract order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    returned_quantity = db.Column(db.Float, default=0)  # Returned quantity
    loss = db.Column(db.Float, default=0)  # Loss quantity
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # Unit ID

    subcontract_order = db.relationship('SubcontractOrder', backref='items')  # Related subcontract order
    material = db.relationship('Material', backref='subcontract_items')  # Related material
    unit = db.relationship('Unit', backref='subcontract_items')  # Related unit


class BOM(db.Model):
    """BOM"""
    id = db.Column(db.Integer, primary_key=True)
    bom_no = db.Column(db.String(50), unique=True, nullable=False)  # BOM code
    product_code = db.Column(db.String(50), nullable=False)  # Code
    product_name = db.Column(db.String(100), nullable=False)  # Name
    version = db.Column(db.String(20), default='1.0')  # Version
    status = db.Column(db.String(20), default='active')  # Status: active/inactive
    parent_bom_id = db.Column(db.Integer, db.ForeignKey('bom.id'), nullable=True)  # Parent BOM ID
    level = db.Column(db.Integer, default=1)  # BOM level
    total_cost = db.Column(db.Float, default=0)  # Total cost
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)  # Updated time

    # Parent-child BOM relationship
    parent_bom = db.relationship('BOM', remote_side=[id], backref='child_boms', lazy='select')


class BOMItem(db.Model):
    """BOM"""
    id = db.Column(db.Integer, primary_key=True)
    bom_id = db.Column(db.Integer, db.ForeignKey('bom.id'), nullable=False)  # BOM ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'), nullable=False)  # Unit ID
    unit_cost = db.Column(db.Float, default=0)  # Unit
    total_cost = db.Column(db.Float, default=0)  # Quantity * unit cost
    usage = db.Column(db.String(200))  # Purpose
    remark = db.Column(db.String(200))  # Remark

    bom = db.relationship('BOM', backref='items')  # BOM
    material = db.relationship('Material', backref='bom_items')  # Related material
    unit = db.relationship('Unit', backref='bom_items')  # Related unit


class ProductionRequisition(db.Model):
    """Production requisition order."""
    id = db.Column(db.Integer, primary_key=True)
    req_no = db.Column(db.String(50), unique=True, nullable=False)  # Requisition order number
    date = db.Column(db.Date, default=date.today)  # Requisition date
    bom_id = db.Column(db.Integer, db.ForeignKey('bom.id'))  # BOM ID
    production_order = db.Column(db.String(50))  # Production
    purpose = db.Column(db.String(200))  # Requisition purpose
    picker = db.Column(db.String(50))  # Pick person (领料人)
    # BUG-2026-08-05-008：工单领料仓库，必填（AGENTS.md 领料出库仓库必填规则）。
    warehouse = db.Column(db.String(100), nullable=False, default='')  # Warehouse name
    # P1-BUGFIX: 库位（开启库位管理时必填，AGENTS.md 规则二）
    location = db.Column(db.String(100), nullable=False, default='')
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    operator = db.relationship('User', backref='production_requisitions')  # Operator
    bom = db.relationship('BOM', backref='requisitions')  # BOM
    items = db.relationship('ProductionRequisitionItem', backref='requisition')  # Requisition details


class ProductionRequisitionItem(db.Model):
    """Production requisition item."""
    id = db.Column(db.Integer, primary_key=True)
    requisition_id = db.Column(db.Integer, db.ForeignKey('production_requisition.id'), nullable=False)  # Requisition ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    quantity = db.Column(db.Float, nullable=False)  # Requisition quantity
    issued_quantity = db.Column(db.Float, default=0)  # Issued quantity
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # Unit ID
    remark = db.Column(db.String(200))  # Remark

    material = db.relationship('Material', backref='requisition_items')  # Related material
    unit = db.relationship('Unit', backref='requisition_items')  # Related unit


class OperationLog(db.Model):
    """Operation log."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)  # Operator ID
    operation_type = db.Column(db.String(50), nullable=False)  # Operation type: in/out/modify/delete
    operation_content = db.Column(db.Text, nullable=False)  # Operation content
    target_type = db.Column(db.String(50))  # Target type, such as in order or out order
    target_id = db.Column(db.Integer)  # Target ID
    ip_address = db.Column(db.String(50))  # Operation IP address
    created_at = db.Column(db.DateTime, default=datetime.now)  # Operation time

    user = db.relationship('User', backref='logs')


class DocumentPushLine(db.Model):
    """Auditable source-line allocation created by a document push."""
    __tablename__ = 'document_push_line'
    __table_args__ = (
        db.UniqueConstraint(
            'created_by', 'source_document_type', 'source_document_id',
            'request_id', 'source_item_id', name='uix_document_push_request_line'
        ),
        db.Index('idx_push_source_item_status', 'source_document_type', 'source_document_id', 'source_item_id', 'status'),
        db.Index('idx_push_target_status', 'target_document_type', 'target_document_id', 'status'),
        db.Index('idx_push_request', 'created_by', 'source_document_type', 'source_document_id', 'request_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    source_document_type = db.Column(db.String(30), nullable=False)
    source_document_id = db.Column(db.Integer, nullable=False)
    source_document_no = db.Column(db.String(50), nullable=False)
    source_item_id = db.Column(db.Integer, nullable=False)
    target_document_type = db.Column(db.String(30), nullable=False)
    target_document_id = db.Column(db.Integer, nullable=False)
    target_document_no = db.Column(db.String(50), nullable=False)
    target_item_id = db.Column(db.Integer)
    pushed_quantity = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='active')
    request_id = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    released_at = db.Column(db.DateTime)
    release_reason = db.Column(db.String(200))

    creator = db.relationship('User', foreign_keys=[created_by])


class TransferOrder(db.Model):
    """Inventory transfer order."""
    __tablename__ = 'transfer_order'

    id = db.Column(db.Integer, primary_key=True)
    transfer_no = db.Column(db.String(50), unique=True, nullable=False)  # Transfer order number
    date = db.Column(db.Date, default=date.today)  # Transfer date
    # BUG-2026-08-02-012：from_location/to_location 原本存的是仓库名，
    # 仓库与库位概念混淆。新增 from_warehouse/to_warehouse 显式存仓库，
    # from_location/to_location 保留作为库位字段（开启库位管理时使用）。
    from_warehouse = db.Column(db.String(100), nullable=False, default='')
    to_warehouse = db.Column(db.String(100), nullable=False, default='')
    from_location = db.Column(db.String(100), nullable=False)  # Source location（未开库位时存调出仓库名，开库位时存调出库位）
    to_location = db.Column(db.String(100), nullable=False)  # Target location（同上）
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed/cancelled
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)

    operator = db.relationship('User', backref='transfer_orders')


class TransferOrderItem(db.Model):
    """Inventory transfer item."""
    __tablename__ = 'transfer_order_item'

    id = db.Column(db.Integer, primary_key=True)
    transfer_order_id = db.Column(db.Integer, db.ForeignKey('transfer_order.id'), nullable=False)  # Transfer order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    quantity = db.Column(db.Float, nullable=False)  # Transfer quantity
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # Unit ID
    price = db.Column(db.Float, default=0)  # Unit price
    amount = db.Column(db.Float, default=0)  # Amount
    remark = db.Column(db.String(500))  # Row remark

    transfer_order = db.relationship('TransferOrder', backref='items')
    material = db.relationship('Material', backref='transfer_items')
    unit = db.relationship('Unit', backref='transfer_items')


class AdjustmentOrder(db.Model):
    """Inventory adjustment order."""
    __tablename__ = 'adjustment_order'

    id = db.Column(db.Integer, primary_key=True)
    adjustment_no = db.Column(db.String(50), unique=True, nullable=False)  # Adjustment order number
    date = db.Column(db.Date, default=date.today)  # Adjustment date
    adjustment_type = db.Column(db.String(20), nullable=False)  # Type: profit/surplus or loss
    # BUG-2026-08-02-012：调整仓库，必填（AGENTS.md 规则）。
    warehouse = db.Column(db.String(100), nullable=False, default='')
    source_type = db.Column(db.String(50))  # Source type: check/manual
    source_id = db.Column(db.Integer)  # Source ID
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed/cancelled
    reversed = db.Column(db.Boolean, default=False)  # Reversed flag
    reversal_order_id = db.Column(db.Integer)  # Reversal order ID
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)

    operator = db.relationship('User', backref='adjustment_orders')


class AdjustmentOrderItem(db.Model):
    """Inventory adjustment item."""
    __tablename__ = 'adjustment_order_item'

    id = db.Column(db.Integer, primary_key=True)
    adjustment_order_id = db.Column(db.Integer, db.ForeignKey('adjustment_order.id'), nullable=False)  # Adjustment order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    location = db.Column(db.String(100))  # Location
    quantity = db.Column(db.Float, nullable=False)  # Adjustment quantity (positive for surplus, negative for loss)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # Unit ID
    reason = db.Column(db.String(500))  # Adjustment reason

    adjustment_order = db.relationship('AdjustmentOrder', backref='items')
    material = db.relationship('Material', backref='adjustment_items')
    unit = db.relationship('Unit', backref='adjustment_items')


class AfterSaleOutOrder(db.Model):
    """After-sales outbound order."""
    __tablename__ = 'after_sale_out_order'

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)  # After sale out order number
    date = db.Column(db.Date, default=date.today)  # Out date
    customer = db.Column(db.String(100))  # Customer name
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))
    warehouse = db.Column(db.String(100), nullable=False, default='')
    # P1-BUGFIX: 库位（开启库位管理时必填，AGENTS.md 规则二）
    location = db.Column(db.String(100), nullable=False, default='')
    contact = db.Column(db.String(50))  # Contact
    phone = db.Column(db.String(20))  # Contact phone
    reason = db.Column(db.String(200))  # After sale reason
    source_sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_order.id'))
    source_out_order_id = db.Column(db.Integer, db.ForeignKey('out_order.id'))
    responsibility = db.Column(db.String(100))
    customer_feedback = db.Column(db.String(500))
    remark = db.Column(db.String(500))  # Remark
    status = db.Column(db.String(20), default='pending')  # Status: pending/completed
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    total_amount = db.Column(db.Float, default=0)  # Amount
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    operator = db.relationship('User', backref='after_sale_out_orders')
    source_sales_order = db.relationship('SalesOrder', backref='after_sale_out_orders')
    source_out_order = db.relationship('OutOrder', backref='after_sale_out_orders')
    customer_master = db.relationship('Customer', foreign_keys=[customer_id])


class AfterSaleOutOrderItem(db.Model):
    """After-sales outbound order item."""
    __tablename__ = 'after_sale_out_order_item'

    id = db.Column(db.Integer, primary_key=True)
    after_sale_out_order_id = db.Column(db.Integer, db.ForeignKey('after_sale_out_order.id'), nullable=False)  # After-sales outbound order ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    price = db.Column(db.Float, nullable=False)  # Unit price
    amount = db.Column(db.Float, nullable=False)  # Amount
    remark = db.Column(db.String(500))  # Row remark
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    contract_no = db.Column(db.String(50))
    project_name = db.Column(db.String(200))

    after_sale_out_order = db.relationship('AfterSaleOutOrder', backref='items')
    material = db.relationship('Material', backref='after_sale_out_order_items')
    contract = db.relationship('Contract', foreign_keys=[contract_id])


class PurchaseRequest(db.Model):
    """Purchase request."""
    __tablename__ = 'purchase_request'

    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(50), unique=True, nullable=False)  # Request order number
    date = db.Column(db.Date, default=date.today)  # Request date
    applicant = db.Column(db.String(100))  # Applicant
    department = db.Column(db.String(100))  # Request department
    urgency = db.Column(db.String(20), default='normal')  # Urgency level: normal/urgent/emergency
    expected_date = db.Column(db.Date)  # Expected delivery date
    reason = db.Column(db.String(500))  # Request reason
    remark = db.Column(db.String(500))  # Remark
    status = db.Column(db.String(20), default='pending')  # Status: pending/approved/rejected/completed
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    total_amount = db.Column(db.Float, default=0)  # Estimated total amount
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    operator = db.relationship('User', backref='purchase_requests')


class PurchaseRequestItem(db.Model):
    """Purchase request item."""
    __tablename__ = 'purchase_request_item'

    id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'), nullable=False)  # Purchase request ID
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'))  # Material ID
    material_name = db.Column(db.String(100))  # Name
    material_code = db.Column(db.String(50))  # Code
    spec = db.Column(db.String(100))  # Specification
    quantity = db.Column(db.Float, nullable=False)  # Quantity
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # Unit ID
    estimated_price = db.Column(db.Float, default=0)  # Unit price
    estimated_amount = db.Column(db.Float, default=0)  # Amount
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))  # Supplier ID
    supplier_name = db.Column(db.String(100))  # Manual supplier name
    remark = db.Column(db.String(200))  # Remark

    purchase_request = db.relationship('PurchaseRequest', backref='items')
    material = db.relationship('Material', backref='purchase_request_items')
    unit = db.relationship('Unit', backref='purchase_request_items')
    supplier = db.relationship('Supplier', backref='purchase_request_items')


class PurchaseOrder(db.Model):
    """Purchase order generated manually or from a purchase request."""
    __tablename__ = 'purchase_order'
    __table_args__ = (
        db.Index('idx_purchase_order_no', 'order_no'),
        db.Index('idx_purchase_order_date', 'date'),
        db.Index('idx_purchase_order_status', 'status'),
        db.Index('idx_purchase_order_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, default=date.today)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    expected_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='pending')  # pending/partial/completed
    remark = db.Column(db.String(500))
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))  # 关联合同档案
    contract_no = db.Column(db.String(50))  # 冗余合同编号（合同变更后历史单据不变）
    project_name = db.Column(db.String(200))  # 冗余工程名称
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    supplier = db.relationship('Supplier', backref='purchase_orders')
    purchase_request = db.relationship('PurchaseRequest', backref='purchase_orders')
    operator = db.relationship('User', backref='purchase_orders')
    contract = db.relationship('Contract', backref='purchase_orders')  # 关联合同档案


class PurchaseOrderItem(db.Model):
    """Purchase order detail row."""
    __tablename__ = 'purchase_order_item'

    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False)
    purchase_request_item_id = db.Column(db.Integer, db.ForeignKey('purchase_request_item.id'))
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    received_quantity = db.Column(db.Float, default=0)
    price = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)
    remark = db.Column(db.String(200))
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    contract_no = db.Column(db.String(50))
    project_name = db.Column(db.String(200))

    purchase_order = db.relationship('PurchaseOrder', backref='items')
    purchase_request_item = db.relationship('PurchaseRequestItem', backref='purchase_order_items')
    material = db.relationship('Material', backref='purchase_order_items')
    contract = db.relationship('Contract', foreign_keys=[contract_id])


class SalesOrder(db.Model):
    """Sales order header; shipment completion remains a warehouse action."""
    __tablename__ = 'sales_order'
    __table_args__ = (
        db.Index('idx_sales_order_no', 'order_no'),
        db.Index('idx_sales_order_date', 'date'),
        db.Index('idx_sales_order_status', 'status'),
        db.Index('idx_sales_order_customer', 'customer_id'),
        db.Index('idx_sales_order_warehouse', 'warehouse_id'),
        db.Index('idx_sales_order_salesperson', 'salesperson_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False)
    date = db.Column(db.Date, default=date.today)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    warehouse = db.Column(db.String(100), nullable=False, default='')
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))
    delivery_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='draft')
    remark = db.Column(db.String(500))
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    total_amount = db.Column(db.Numeric(18, 2), default=0)
    # 含税金额合计 = sum(item.tax_included_amount)
    untaxed_amount = db.Column(db.Numeric(18, 2), default=0)
    tax_amount = db.Column(db.Numeric(18, 2), default=0)
    shipped_amount = db.Column(db.Numeric(18, 2), default=0)
    remaining_amount = db.Column(db.Numeric(18, 2), default=0)
    shipment_order_no = db.Column(db.String(50))
    shipment_status = db.Column(db.String(20), default='pending')  # pending/partial/shipped
    # 扩展字段：业务员、项目号、币别、结算方式
    salesperson_id = db.Column(db.Integer, db.ForeignKey('employee.id'))
    project_no = db.Column(db.String(100))
    currency = db.Column(db.String(20), default='CNY')
    settlement_method = db.Column(db.String(50))
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))  # 关联合同档案
    contract_no = db.Column(db.String(50))  # 冗余合同编号（合同变更后历史单据不变）
    project_name = db.Column(db.String(200))  # 冗余工程名称（与 project_no 自由文本字段独立）
    created_at = db.Column(db.DateTime, default=datetime.now)

    customer = db.relationship('Customer', backref='sales_orders')
    operator = db.relationship('User', backref='sales_orders')
    salesperson = db.relationship('Employee', backref='sales_orders')
    warehouse_ref = db.relationship('Warehouse', backref='sales_orders_by_warehouse', foreign_keys=[warehouse_id])
    contract = db.relationship('Contract', backref='sales_orders')  # 关联合同档案


class SalesOrderItem(db.Model):
    """Sales order detail row."""
    __tablename__ = 'sales_order_item'

    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey('sales_order.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    shipped_quantity = db.Column(db.Float, default=0)
    price = db.Column(db.Float, default=0)  # 含税单价
    amount = db.Column(db.Numeric(18, 2), default=0)  # 含税金额（兼容旧逻辑）
    # 税务字段
    tax_rate = db.Column(db.Float, default=0.13)  # 税率，默认 13%
    untaxed_price = db.Column(db.Float, default=0)  # 未税单价
    untaxed_amount = db.Column(db.Numeric(18, 2), default=0)  # 未税金额
    tax_amount = db.Column(db.Numeric(18, 2), default=0)  # 税额
    tax_included_amount = db.Column(db.Numeric(18, 2), default=0)  # 含税金额
    # 扩展字段：批次号、序列号
    batch_no = db.Column(db.String(100))
    serial_no = db.Column(db.String(200))
    remark = db.Column(db.String(200))
    contract_id = db.Column(db.Integer, db.ForeignKey('contract.id'))
    contract_no = db.Column(db.String(50))
    project_name = db.Column(db.String(200))

    sales_order = db.relationship('SalesOrder', backref='items')
    material = db.relationship('Material', backref='sales_order_items')
    contract = db.relationship('Contract', foreign_keys=[contract_id])
