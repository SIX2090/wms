"""阶段2：文档识别统一提取Schema。

定义所有文档类型的结构化提取结果格式，包括：
- 单据类型（送货单/领料单/调拨单/盘点单/调整单）
- 表头字段（供应商/客户/单号/日期/采购订单号/仓库）
- 明细行（物料编码/名称/规格/单位/数量/箱数/批号/条码/置信度）
- 匹配结果（匹配方式/匹配物料ID/置信度/是否需人工确认）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DocumentType(str, Enum):
    """支持的单据类型。"""
    IN_ORDER = 'in_order'  # 入库/送货/采购到货
    OUT_ORDER = 'out_order'  # 出库/领料/发料
    SALES_OUT = 'sales_out_order'  # 销售出库
    TRANSFER = 'transfer'  # 调拨
    CHECK = 'check'  # 盘点
    ADJUSTMENT = 'adjustment'  # 库存调整
    PURCHASE_REQUEST = 'purchase_request'  # 采购申请
    OTHER = 'other'  # 其他


class MatchMethod(str, Enum):
    """物料匹配方式（按优先级）。"""
    EXACT_CODE = 'exact_code'  # 精确编码匹配
    EXACT_NAME = 'exact_name'  # 精确名称+规格匹配
    LEARNED_ALIAS = 'learned_alias'  # 已学习别名匹配
    SINGLE_FUZZY = 'single_fuzzy'  # 唯一模糊候选
    MULTIPLE_CANDIDATES = 'multiple'  # 多个候选（需人工选择）
    NONE = 'none'  # 未匹配


class DocumentStatus(str, Enum):
    """文档任务状态。"""
    UPLOADING = 'uploading'  # 上传中
    RECOGNIZING = 'recognizing'  # 识别中
    PENDING_CONFIRM = 'pending_confirm'  # 待确认
    DRAFT_CREATED = 'draft_created'  # 已生成草稿
    FAILED = 'failed'  # 失败
    CANCELLED = 'cancelled'  # 已取消


@dataclass
class DocumentHeader:
    """单据表头信息。"""
    document_type: DocumentType
    supplier: str = ''
    customer: str = ''
    order_no: str = ''  # 单据编号
    purchase_order_no: str = ''  # 采购订单号
    date: str = ''  # 单据日期
    warehouse: str = ''  # 仓库
    remarks: str = ''  # 备注


@dataclass
class DocumentLine:
    """单据明细行。"""
    line_no: int  # 行号
    code: str = ''  # 物料编码
    name: str = ''  # 物料名称
    spec: str = ''  # 规格
    unit: str = ''  # 单位
    quantity: float = 0.0  # 数量
    box_count: Optional[int] = None  # 箱数
    batch_no: str = ''  # 批号
    barcode: str = ''  # 条码
    raw_text: str = ''  # 原始识别文本

    # 匹配结果
    match_method: Optional[MatchMethod] = None
    matched_material_id: Optional[int] = None
    confidence: float = 0.0  # 匹配置信度 0-1
    needs_confirmation: bool = True  # 是否需要人工确认
    confirmation_reason: str = ''  # 确认原因（如"多个候选"/"低置信度"）

    # 校验结果
    validation_errors: list[str] = field(default_factory=list)  # 校验错误列表


@dataclass
class DocumentExtraction:
    """完整的文档提取结果。"""
    header: DocumentHeader
    lines: list[DocumentLine] = field(default_factory=list)
    source_type: str = ''  # 来源类型（image/text/excel/pdf）
    source_text: str = ''  # 原始文本（文本来源时）
    image_url: str = ''  # 图片URL（图片来源时）
    ocr_raw: str = ''  # OCR原始结果
    model_version: str = ''  # 使用的模型版本
    prompt_version: str = ''  # 使用的提示词版本

    # 整体置信度
    overall_confidence: float = 0.0
    needs_confirmation: bool = True  # 整体是否需要确认

    # 统计
    total_lines: int = 0
    matched_lines: int = 0
    unmatched_lines: int = 0
    low_confidence_lines: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于JSON序列化）。"""
        return {
            'header': {
                'document_type': self.header.document_type.value,
                'supplier': self.header.supplier,
                'customer': self.header.customer,
                'order_no': self.header.order_no,
                'purchase_order_no': self.header.purchase_order_no,
                'date': self.header.date,
                'warehouse': self.header.warehouse,
                'remarks': self.header.remarks,
            },
            'lines': [
                {
                    'line_no': line.line_no,
                    'code': line.code,
                    'name': line.name,
                    'spec': line.spec,
                    'unit': line.unit,
                    'quantity': line.quantity,
                    'box_count': line.box_count,
                    'batch_no': line.batch_no,
                    'barcode': line.barcode,
                    'raw_text': line.raw_text,
                    'match_method': line.match_method.value if line.match_method else None,
                    'matched_material_id': line.matched_material_id,
                    'confidence': line.confidence,
                    'needs_confirmation': line.needs_confirmation,
                    'confirmation_reason': line.confirmation_reason,
                    'validation_errors': line.validation_errors,
                }
                for line in self.lines
            ],
            'source_type': self.source_type,
            'source_text': self.source_text,
            'image_url': self.image_url,
            'ocr_raw': self.ocr_raw,
            'model_version': self.model_version,
            'prompt_version': self.prompt_version,
            'overall_confidence': self.overall_confidence,
            'needs_confirmation': self.needs_confirmation,
            'total_lines': self.total_lines,
            'matched_lines': self.matched_lines,
            'unmatched_lines': self.unmatched_lines,
            'low_confidence_lines': self.low_confidence_lines,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'DocumentExtraction':
        """从字典创建实例。"""
        header_data = data.get('header', {})
        header = DocumentHeader(
            document_type=DocumentType(header_data.get('document_type', 'other')),
            supplier=header_data.get('supplier', ''),
            customer=header_data.get('customer', ''),
            order_no=header_data.get('order_no', ''),
            purchase_order_no=header_data.get('purchase_order_no', ''),
            date=header_data.get('date', ''),
            warehouse=header_data.get('warehouse', ''),
            remarks=header_data.get('remarks', ''),
        )

        lines = []
        for line_data in data.get('lines', []):
            match_method = None
            if line_data.get('match_method'):
                match_method = MatchMethod(line_data['match_method'])

            line = DocumentLine(
                line_no=line_data.get('line_no', 0),
                code=line_data.get('code', ''),
                name=line_data.get('name', ''),
                spec=line_data.get('spec', ''),
                unit=line_data.get('unit', ''),
                quantity=line_data.get('quantity', 0.0),
                box_count=line_data.get('box_count'),
                batch_no=line_data.get('batch_no', ''),
                barcode=line_data.get('barcode', ''),
                raw_text=line_data.get('raw_text', ''),
                match_method=match_method,
                matched_material_id=line_data.get('matched_material_id'),
                confidence=line_data.get('confidence', 0.0),
                needs_confirmation=line_data.get('needs_confirmation', True),
                confirmation_reason=line_data.get('confirmation_reason', ''),
                validation_errors=line_data.get('validation_errors', []),
            )
            lines.append(line)

        return cls(
            header=header,
            lines=lines,
            source_type=data.get('source_type', ''),
            source_text=data.get('source_text', ''),
            image_url=data.get('image_url', ''),
            ocr_raw=data.get('ocr_raw', ''),
            model_version=data.get('model_version', ''),
            prompt_version=data.get('prompt_version', ''),
            overall_confidence=data.get('overall_confidence', 0.0),
            needs_confirmation=data.get('needs_confirmation', True),
            total_lines=data.get('total_lines', 0),
            matched_lines=data.get('matched_lines', 0),
            unmatched_lines=data.get('unmatched_lines', 0),
            low_confidence_lines=data.get('low_confidence_lines', 0),
        )


# 置信度阈值配置
CONFIDENCE_THRESHOLDS = {
    'high': 0.95,  # 高置信度，可自动匹配
    'medium': 0.80,  # 中置信度，建议确认
    'low': 0.60,  # 低置信度，必须确认
}

# 需要人工确认的场景
CONFIRMATION_REASONS = {
    'multiple_candidates': '多个候选物料，请选择正确的一个',
    'low_confidence': '匹配置信度较低，请确认',
    'no_match': '未找到匹配物料，请手动选择或创建',
    'over_po_quantity': '数量超过采购订单未到货量，请确认',
    'ambiguous_spec': '规格不明确，请确认',
}
