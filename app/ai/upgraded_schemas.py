"""数据模型升级：批次/批号/序列号统一Schema。

对应计划第9节"业务数据模型升级建议"：
1. 单据明细统一支持批次/批号
2. 序列号物料建立序列号台账
3. 单据表头和明细按业务需要支持项目号
4. 库存量分离：现存量、可用量、占用量、在途量
5. 状态机规范化
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---- 1. 规范化状态机 ----

class DocumentStatus(str, Enum):
    """统一单据状态。"""
    DRAFT = 'draft'              # 草稿
    SUBMITTED = 'submitted'      # 已提交
    APPROVED = 'approved'        # 已审核
    PROCESSING = 'processing'    # 执行中
    COMPLETED = 'completed'      # 已完成
    CLOSED = 'closed'            # 已关闭
    VOIDED = 'voided'            # 已作废


# 合法状态转换
VALID_STATUS_TRANSITIONS = {
    DocumentStatus.DRAFT: [DocumentStatus.SUBMITTED, DocumentStatus.VOIDED],
    DocumentStatus.SUBMITTED: [DocumentStatus.APPROVED, DocumentStatus.VOIDED],
    DocumentStatus.APPROVED: [DocumentStatus.PROCESSING, DocumentStatus.VOIDED],
    DocumentStatus.PROCESSING: [DocumentStatus.COMPLETED, DocumentStatus.CLOSED],
    DocumentStatus.COMPLETED: [DocumentStatus.CLOSED],
    DocumentStatus.CLOSED: [],
    DocumentStatus.VOIDED: [],
}


def validate_status_transition(
    from_status: DocumentStatus,
    to_status: DocumentStatus,
) -> tuple[bool, str]:
    """验证状态转换是否合法。"""
    allowed = VALID_STATUS_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        return False, f'不允许从 {from_status.value} 转换到 {to_status.value}'
    return True, ''


# ---- 2. 批次/批号Schema ----

@dataclass
class BatchInfo:
    """批次信息。"""
    batch_no: str = ''           # 批号
    production_date: Optional[datetime] = None  # 生产日期
    expiry_date: Optional[datetime] = None      # 有效期
    supplier_batch_no: str = ''  # 供应商批号
    remark: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'batch_no': self.batch_no,
            'production_date': self.production_date.isoformat() if self.production_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'supplier_batch_no': self.supplier_batch_no,
            'remark': self.remark,
        }

    @property
    def is_expired(self) -> bool:
        if self.expiry_date is None:
            return False
        return datetime.now() > self.expiry_date

    @property
    def days_until_expiry(self) -> Optional[int]:
        if self.expiry_date is None:
            return None
        delta = self.expiry_date - datetime.now()
        return delta.days


# ---- 3. 序列号台账 ----

@dataclass
class SerialNumber:
    """序列号台账。"""
    serial_no: str
    material_id: int
    material_code: str = ''
    material_name: str = ''
    batch_no: str = ''
    status: str = 'in_stock'  # in_stock / issued / scrapped / returned
    warehouse_id: Optional[int] = None
    location_id: Optional[int] = None
    inbound_order_id: Optional[int] = None
    outbound_order_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'serial_no': self.serial_no,
            'material_id': self.material_id,
            'material_code': self.material_code,
            'material_name': self.material_name,
            'batch_no': self.batch_no,
            'status': self.status,
            'warehouse_id': self.warehouse_id,
            'location_id': self.location_id,
            'inbound_order_id': self.inbound_order_id,
            'outbound_order_id': self.outbound_order_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


class SerialNumberLedger:
    """序列号台账管理（内存版）。"""

    def __init__(self):
        self._records: dict[str, SerialNumber] = {}

    def register(
        self,
        serial_no: str,
        material_id: int,
        material_code: str = '',
        material_name: str = '',
        batch_no: str = '',
        warehouse_id: Optional[int] = None,
        location_id: Optional[int] = None,
        inbound_order_id: Optional[int] = None,
    ) -> SerialNumber:
        """注册序列号（入库时）。"""
        if serial_no in self._records:
            raise ValueError(f'序列号 {serial_no} 已存在')

        record = SerialNumber(
            serial_no=serial_no,
            material_id=material_id,
            material_code=material_code,
            material_name=material_name,
            batch_no=batch_no,
            status='in_stock',
            warehouse_id=warehouse_id,
            location_id=location_id,
            inbound_order_id=inbound_order_id,
        )
        self._records[serial_no] = record
        return record

    def issue(self, serial_no: str, outbound_order_id: int) -> bool:
        """出库序列号。"""
        record = self._records.get(serial_no)
        if not record:
            return False
        if record.status != 'in_stock':
            return False

        record.status = 'issued'
        record.outbound_order_id = outbound_order_id
        record.updated_at = datetime.now()
        return True

    def scrap(self, serial_no: str) -> bool:
        """报废序列号。"""
        record = self._records.get(serial_no)
        if not record:
            return False
        if record.status not in ('in_stock', 'issued'):
            return False

        record.status = 'scrapped'
        record.updated_at = datetime.now()
        return True

    def query(
        self,
        material_id: Optional[int] = None,
        status: Optional[str] = None,
        warehouse_id: Optional[int] = None,
    ) -> list[SerialNumber]:
        """查询序列号。"""
        results = []
        for record in self._records.values():
            if material_id is not None and record.material_id != material_id:
                continue
            if status is not None and record.status != status:
                continue
            if warehouse_id is not None and record.warehouse_id != warehouse_id:
                continue
            results.append(record)
        return results

    def get(self, serial_no: str) -> Optional[SerialNumber]:
        """获取单个序列号。"""
        return self._records.get(serial_no)


# ---- 4. 库存量分离 ----

@dataclass
class StockQuantity:
    """库存量分离：现存量、可用量、占用量、在途量。

    可用量 = 现存量 - 占用量
    在途量 = 已下单未到货的采购量
    """
    material_id: int
    current_qty: float = 0.0    # 现存量
    reserved_qty: float = 0.0   # 占用量（已分配给出库单但未出库）
    in_transit_qty: float = 0.0 # 在途量（采购未到货）

    @property
    def available_qty(self) -> float:
        """可用量 = 现存量 - 占用量。"""
        return max(0, self.current_qty - self.reserved_qty)

    @property
    def projected_qty(self) -> float:
        """预计可用量 = 可用量 + 在途量。"""
        return self.available_qty + self.in_transit_qty

    def to_dict(self) -> dict[str, Any]:
        return {
            'material_id': self.material_id,
            'current_qty': self.current_qty,
            'available_qty': self.available_qty,
            'reserved_qty': self.reserved_qty,
            'in_transit_qty': self.in_transit_qty,
            'projected_qty': self.projected_qty,
        }


# ---- 5. 单据明细扩展Schema ----

@dataclass
class DocumentItemSchema:
    """单据明细统一Schema（支持批次/批号/序列号/项目号/库位）。"""
    material_id: int
    quantity: float
    unit_id: Optional[int] = None
    price: float = 0.0
    amount: float = 0.0
    batch_no: str = ''                    # 批号
    serial_numbers: list[str] = field(default_factory=list)  # 序列号列表
    location_id: Optional[int] = None     # 库位
    project_no: str = ''                  # 项目号
    remark: str = ''
    # 原始数量和基本单位数量（单位换算）
    original_quantity: Optional[float] = None
    original_unit_id: Optional[int] = None
    base_quantity: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'material_id': self.material_id,
            'quantity': self.quantity,
            'unit_id': self.unit_id,
            'price': self.price,
            'amount': self.amount,
            'batch_no': self.batch_no,
            'serial_numbers': self.serial_numbers,
            'location_id': self.location_id,
            'project_no': self.project_no,
            'remark': self.remark,
            'original_quantity': self.original_quantity,
            'original_unit_id': self.original_unit_id,
            'base_quantity': self.base_quantity,
        }


# ---- 6. 异常处理Schema ----

@dataclass
class ExceptionRecord:
    """异常记录：阻塞原因、处理人、处理时限和处理结果。"""
    exception_type: str  # negative_stock / low_stock / overdue / quality
    material_id: Optional[int] = None
    order_id: Optional[int] = None
    description: str = ''
    severity: str = 'medium'  # low / medium / high / critical
    assigned_to: Optional[int] = None
    deadline: Optional[datetime] = None
    status: str = 'open'  # open / processing / resolved / closed
    resolution: str = ''
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'exception_type': self.exception_type,
            'material_id': self.material_id,
            'order_id': self.order_id,
            'description': self.description,
            'severity': self.severity,
            'assigned_to': self.assigned_to,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'status': self.status,
            'resolution': self.resolution,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }
