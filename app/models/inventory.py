#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""库存事实模型（库位库存 / 库存事务流水）。

ARCH-MODELS-01（2026-09-15）自 app/app.py 模型区迁入，类定义逐字保留。
统一平铺导入 ``from db import db``（与 document_evidence.py 先例一致）。
"""

from db import db
from datetime import datetime

__all__ = [
    'LocationInventory',
    'StockTransaction',
]


class LocationInventory(db.Model):
    """Inventory quantity by location."""
    __tablename__ = 'location_inventory'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'), nullable=True)
    location = db.Column(db.String(100), nullable=False)  # Location code
    quantity = db.Column(db.Float, default=0)  # Inventory quantity at this location
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    material = db.relationship('Material', backref='location_inventories')
    warehouse = db.relationship('Warehouse', backref='location_inventories')

    __table_args__ = (
        # INV-AUDIT-002 修复：唯一约束从 (material_id, location) 改为
        # (material_id, warehouse_id, location)，禁止不同仓库的同名库位被
        # 强行合并到同一条库存记录。旧约束名保留在迁移历史中，新写入统一走
        # 新约束；warehouse_id 为 NULL 的历史行按 SQLite/大多数数据库语义各自
        # 视为不同值，不会与已归属仓库的行冲突。
        db.UniqueConstraint('material_id', 'warehouse_id', 'location', name='uix_material_warehouse_location'),
        db.Index('idx_location_inventory_warehouse', 'warehouse_id'),
        # AI-WMS-FILTER-003：仓库级库存聚合（get_warehouse_stock_quantities 的
        # GROUP BY material_id）走这个复合索引。material_id 单列索引已存在
        # （idx_location_inventory_material_id），不重复建。
        db.Index('idx_location_inventory_wh_material', 'warehouse_id', 'material_id'),
    )


class StockTransaction(db.Model):
    """Stock transaction record."""
    __tablename__ = 'stock_transaction'
    __table_args__ = (
        db.Index('idx_stock_txn_material', 'material_id'),
        db.Index('idx_stock_txn_type', 'transaction_type'),
        db.Index('idx_stock_txn_created', 'created_at'),
        db.Index('idx_stock_txn_ref', 'reference_type', 'reference_id'),
        # BUG-2026-08-16-021：关库位管理分支按 location 聚合仓库库存，全表扫太慢，
        # 加单列索引加速 IN (仓库名/编码) 聚合。
        db.Index('idx_stock_txn_location', 'location'),
        # BUG-2026-08-27-004 治本 B1：按仓库过滤流水的精确索引（warehouse_id 外键
        # 归属，逐步替代 location 字符串匹配——location 历史上混存仓库名/编码/库位
        # 名/空值，字符串匹配口径分散导致库存报表反复出 BUG）。
        db.Index('idx_stock_txn_warehouse_id', 'warehouse_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)  # Material ID
    transaction_type = db.Column(db.String(50), nullable=False)  # Transaction type: in/out/transfer_in/transfer_out/adjustment_in/adjustment_out
    quantity = db.Column(db.Float, nullable=False)  # Change quantity (positive for increase, negative for decrease)
    location = db.Column(db.String(100))  # Location (empty means summary)
    # BUG-2026-08-27-004 治本 B1：仓库外键归属。新流水由写入端
    # （add_stock/deduct_stock_atomic/add_stock_transaction，B2）解析写入；
    # 历史行由 backfill_stock_txn_warehouse_id() 启动幂等回填；
    # 无法唯一确定归属的行保留 NULL（不猜，AGENTS.md 不自动归入任意默认仓库）。
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))  # Warehouse ID (NULL = 历史未归属)
    reference_type = db.Column(db.String(50))  # Related document type: in_order/out_order/transfer/adjustment/check
    reference_id = db.Column(db.Integer)  # Related document ID
    remark = db.Column(db.String(500))  # Remark
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Operator ID
    created_at = db.Column(db.DateTime, default=datetime.now)

    material = db.relationship('Material', backref='stock_transactions')
    operator = db.relationship('User', backref='stock_transactions')
    # B1 治本：仓库关联（只读展示用；归属判定一律走 warehouse_id，不回退 location 猜测）
    warehouse = db.relationship('Warehouse')
