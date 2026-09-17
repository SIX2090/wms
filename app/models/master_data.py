#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主数据模型（物料 / 供应商 / 客户 / 仓库 / 部门 / 合同 / 员工 / 单位 / 分类）。

ARCH-MODELS-01（2026-09-15）自 app/app.py 模型区迁入，类定义逐字保留。
统一平铺导入 ``from db import db``（与 document_evidence.py 先例一致）。
"""

from db import db
from datetime import datetime

__all__ = [
    'Contract',
    'Customer',
    'Department',
    'Employee',
    'Material',
    'MaterialCategory',
    'MaterialImage',
    'Supplier',
    'Unit',
    'Warehouse',
]


class Employee(db.Model):
    """Employee."""
    id = db.Column(db.Integer, primary_key=True)
    # M-04：员工编码 + 部门外键，便于按部门/编码筛选与考勤对接
    code = db.Column(db.String(64), unique=True, nullable=True)  # 员工编码（可空，向后兼容）
    name = db.Column(db.String(50), nullable=False)  # Name
    position = db.Column(db.String(50))  # Position
    phone = db.Column(db.String(20))  # Contact phone
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time
    department = db.relationship('Department', backref='employees', lazy='joined')


class MaterialCategory(db.Model):
    """Material category."""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Category code
    name = db.Column(db.String(50), unique=True, nullable=False)  # Category name
    parent_id = db.Column(db.Integer, db.ForeignKey('material_category.id'))  # Parent category
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time
    parent = db.relationship('MaterialCategory', remote_side=[id], backref='children')


class Unit(db.Model):
    """Unit of measure."""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Unit code
    name = db.Column(db.String(20), unique=True, nullable=False)  # Unit name
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time


class Supplier(db.Model):
    """Supplier."""
    # AI-WMS-FILTER-003：列表默认按 code 排序、筛选支持创建时间区间，
    # 补 created_at 索引；code/name 已有 unique 约束自带的唯一索引。
    __table_args__ = (
        db.Index('idx_supplier_created', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Supplier code
    name = db.Column(db.String(100), unique=True, nullable=False)  # Name
    contact = db.Column(db.String(50))  # Contact
    phone = db.Column(db.String(20))  # Contact phone
    address = db.Column(db.String(200))  # Address
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time


class Customer(db.Model):
    """Customer master data."""
    # AI-WMS-FILTER-003：同上，补 created_at 索引。
    __table_args__ = (
        db.Index('idx_customer_created', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Customer code
    name = db.Column(db.String(100), unique=True, nullable=False)  # Name
    contact = db.Column(db.String(50))  # Contact
    phone = db.Column(db.String(20))  # Contact phone
    address = db.Column(db.String(200))  # Address
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time


class Warehouse(db.Model):
    """Warehouse."""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Warehouse code
    name = db.Column(db.String(100), unique=True, nullable=False)  # Warehouse name
    type = db.Column(db.String(50))  # Warehouse type (raw material/finished product/semi-finished product)
    location = db.Column(db.String(200))  # Warehouse location
    status = db.Column(db.String(20), default='active')  # Status: active/inactive
    remark = db.Column(db.String(200))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time
    # M-03：默认仓标识，便于入库/出库默认带出仓库
    is_default = db.Column(db.Boolean, default=False, nullable=False)


class Department(db.Model):
    """Department."""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Department code
    name = db.Column(db.String(100), unique=True, nullable=False)  # Department name
    status = db.Column(db.String(20), default='active')  # Status: active/inactive
    remark = db.Column(db.String(200))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time


class Contract(db.Model):
    """合同/工程档案主数据（精简版）。

    用于在采购入库单、领料出库单、采购订单、销售订单头上标记所属合同与工程，
    便于按合同/工程维度归集与筛选。订单表同时冗余 contract_no/project_name 文本；
    BUG-2026-09-17-001 起，档案编辑/批量导入改名（改号）时由
    sync_contract_project_name() 同步全部历史单据的冗余值（用户拍板：跟随同步，
    不再保留原始快照）。
    """
    __tablename__ = 'contract'
    __table_args__ = (
        db.Index('idx_contract_no', 'contract_no'),
        db.Index('idx_contract_status', 'status'),
    )
    id = db.Column(db.Integer, primary_key=True)
    contract_no = db.Column(db.String(50), unique=True, nullable=False)  # 合同编号（如 HD260713）
    project_name = db.Column(db.String(200), nullable=False)  # 工程名称
    status = db.Column(db.String(20), default='active')  # active/inactive
    remark = db.Column(db.String(500))  # 备注（可记订货单位、型号等自由文本）
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time


class Material(db.Model):
    """Material master data.

    ⚠️ 库存阈值命名约定（AI-CI-GREEN-005，务必先读再改）

    对外（界面文案 / Excel 表头 / API 字段）叫「安全库存」的概念，
    在数据库里的列名是 ``reorder_point``——**两者是同一个东西**，
    历史上数据库先叫 reorder_point，界面后统一为"安全库存"，为免动存量数据故保留列名。

    对照表：

        +----------------+------------------+----------------------------+
        | 数据库列       | 对外名称         | 语义                       |
        +================+==================+============================+
        | min_stock      | 最低库存         | 低于它即不可接受（红线）   |
        | max_stock      | 最大库存         | 高于它即超储               |
        | reorder_point  | **安全库存**     | 低于它即需补货（预警线）   |
        | alert_days     | 预警天数         | 有效期预警提前天数         |
        +----------------+------------------+----------------------------+

    ``safety_stock``（不带下划线前缀的那个名字）**不是数据库列**，而是运行时
    计算值 ``max(reorder_point, min_stock)``，仅出现在 API 响应、Excel 导出列
    和报表字典里。写库只走 ``reorder_point``（全仓写入点仅 3 处：
    routes/material.py 的新增与编辑、routes/inventory_alert.py 的批量设置）。

    因此：改「安全库存」相关逻辑时，**写库用 reorder_point，读展示可用 safety_stock**，
    不要新增第四种叫法（如 safe_stock / security_stock）。
    """
    __tablename__ = 'material'
    __table_args__ = (
        db.Index('idx_material_code', 'code'),
        db.Index('idx_material_name', 'name'),
        db.Index('idx_material_category', 'category_id'),
        # AI-WMS-FILTER-003：JOIN 与排序真正会走的索引。
        # 注意 LIKE '%kw%' 的前置通配符用不上 B-tree，模糊搜索本身不靠这些索引提速。
        db.Index('idx_material_supplier', 'supplier_id'),
        db.Index('idx_material_unit', 'unit_id'),
        db.Index('idx_material_created', 'created_at'),
    )
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)  # Code
    name = db.Column(db.String(100), nullable=False)  # Name
    category_id = db.Column(db.Integer, db.ForeignKey('material_category.id'))  # CategoryID
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))  # UnitID
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))  # Supplier ID
    brand = db.Column(db.String(100))  # Brand
    spec = db.Column(db.String(100))  # Specification
    purpose = db.Column(db.String(200))  # Purpose
    image = db.Column(db.String(200))  # Image path
    stock = db.Column(db.Float, default=0)  # Inventory
    # ---- 库存阈值三兄弟：命名对照见下方「命名约定」注释 ----
    min_stock = db.Column(db.Float, default=0)  # Minimum inventory（对外：「最低库存」）
    max_stock = db.Column(db.Float, default=0)  # Maximum inventory（对外：「最大库存」）
    reorder_point = db.Column(db.Float, default=0)  # Reorder point（对外：「安全库存」）
    expiry_date = db.Column(db.Date)  # Validity period
    alert_days = db.Column(db.Integer, default=30)  # Alert
    price = db.Column(db.Float, default=0)  # Unit price
    remark = db.Column(db.String(500))  # Remark
    created_at = db.Column(db.DateTime, default=datetime.now)  # Created time

    category = db.relationship('MaterialCategory', backref=db.backref('materials', cascade='save-update, merge'))  # Related category
    unit = db.relationship('Unit', backref=db.backref('materials', cascade='save-update, merge'))  # Related unit
    supplier = db.relationship('Supplier', backref=db.backref('materials', cascade='save-update, merge'))  # Related supplier


class MaterialImage(db.Model):
    """物料档案图片（每个物料最多 MAX_MATERIAL_IMAGES=5 张）。

    与 Material.image 单图字段并存：Material.image 保留给 Web 端"主图"，
    本表承载移动端物料档案的多图归档。表由 db.create_all() 启动时自动创建。
    """
    __tablename__ = 'material_image'
    __table_args__ = (
        db.Index('idx_material_image_material', 'material_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    image = db.Column(db.String(200), nullable=False)  # 相对路径 uploads/material_images/xxx.jpg
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    material = db.relationship(
        'Material',
        backref=db.backref('archive_images', cascade='all, delete-orphan', order_by='MaterialImage.sort_order'),
    )
