"""阶段2：文档提取流水线。

统一处理各类文档来源（图片/文本/Excel/PDF），
经过 OCR → 结构化提取 → 物料匹配 → 校验，
输出标准化的 DocumentExtraction 结果。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from .schemas import (
    DocumentExtraction,
    DocumentHeader,
    DocumentLine,
    DocumentType,
    DocumentStatus,
    MatchMethod,
    CONFIDENCE_THRESHOLDS,
)

logger = logging.getLogger(__name__)


def extract_from_text(text: str) -> DocumentExtraction:
    """从纯文本提取文档结构。

    支持：
    - 微信发货通知（如 "明天发鑫达 6204轴承 100套，M8螺母 500个"）
    - 手动输入的物料清单
    - Excel 粘贴的表格文本
    """
    text = (text or '').strip()
    if not text:
        return DocumentExtraction(
            header=DocumentHeader(document_type=DocumentType.OTHER),
            source_type='text',
            source_text=text,
        )

    doc_type = _guess_doc_type(text)
    supplier = _extract_supplier(text) if doc_type == DocumentType.IN_ORDER else ''
    customer = _extract_customer(text) if doc_type in (DocumentType.OUT_ORDER, DocumentType.SALES_OUT) else ''

    items = _parse_material_segments(text)
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(DocumentLine(
            line_no=i,
            code=item.get('code', ''),
            name=item.get('name', ''),
            spec=item.get('spec', ''),
            unit=item.get('unit', ''),
            quantity=item.get('quantity', 0.0),
            raw_text=item.get('raw', ''),
            confidence=0.0,
            needs_confirmation=True,
        ))

    header = DocumentHeader(
        document_type=doc_type,
        supplier=supplier,
        customer=customer,
    )

    extraction = DocumentExtraction(
        header=header,
        lines=lines,
        source_type='text',
        source_text=text,
        total_lines=len(lines),
    )
    _compute_overall_confidence(extraction)
    return extraction


def extract_from_vision(content: str, extracted_json: Optional[dict] = None) -> DocumentExtraction:
    """从视觉模型回复中提取文档结构。

    Args:
        content: 视觉模型回复文本
        extracted_json: 模型已解析的 JSON 结构化结果（如有）
    """
    if extracted_json:
        return _build_extraction_from_json(extracted_json, source_type='image')

    # 尝试从回复文本末尾解析 JSON 代码块
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            return _build_extraction_from_json(data, source_type='image')
        except json.JSONDecodeError:
            pass

    return DocumentExtraction(
        header=DocumentHeader(document_type=DocumentType.OTHER),
        source_type='image',
        source_text=content,
    )


def extract_from_excel_table(table_text: str) -> DocumentExtraction:
    """从 Excel 粘贴的表格文本提取。"""
    lines = []
    for i, row in enumerate(table_text.strip().split('\n'), 1):
        cells = [c.strip() for c in row.split('\t')]
        if len(cells) < 2:
            continue
        lines.append(DocumentLine(
            line_no=i,
            code=cells[0] if len(cells) > 0 else '',
            name=cells[1] if len(cells) > 1 else '',
            spec=cells[2] if len(cells) > 2 else '',
            quantity=_parse_float(cells[3]) if len(cells) > 3 else 0.0,
            unit=cells[4] if len(cells) > 4 else '',
            raw_text=row,
            confidence=0.0,
            needs_confirmation=True,
        ))

    return DocumentExtraction(
        header=DocumentHeader(document_type=DocumentType.IN_ORDER),
        lines=lines,
        source_type='excel',
        source_text=table_text,
        total_lines=len(lines),
    )


def _build_extraction_from_json(data: dict, source_type: str = 'image') -> DocumentExtraction:
    """从 JSON 结构化结果构建 DocumentExtraction。"""
    doc_type_str = data.get('document_type', 'other')
    try:
        doc_type = DocumentType(doc_type_str)
    except ValueError:
        doc_type = DocumentType.OTHER

    header = DocumentHeader(
        document_type=doc_type,
        supplier=data.get('supplier', ''),
        customer=data.get('customer', ''),
        order_no=data.get('order_no', ''),
        purchase_order_no=data.get('purchase_order_no', ''),
        date=data.get('date', ''),
        warehouse=data.get('warehouse', ''),
        remarks=data.get('remarks', ''),
    )

    lines = []
    for i, item in enumerate(data.get('items', []), 1):
        lines.append(DocumentLine(
            line_no=i,
            code=item.get('code', ''),
            name=item.get('name', ''),
            spec=item.get('spec', ''),
            unit=item.get('unit', ''),
            quantity=float(item.get('quantity', 0) or 0),
            box_count=item.get('box_count'),
            batch_no=item.get('batch_no', ''),
            barcode=item.get('barcode', ''),
            raw_text=item.get('raw', ''),
            confidence=0.0,
            needs_confirmation=True,
        ))

    return DocumentExtraction(
        header=header,
        lines=lines,
        source_type=source_type,
        total_lines=len(lines),
    )


def _guess_doc_type(text: str) -> DocumentType:
    """根据文本内容猜测单据类型。"""
    compact = text.replace(' ', '').lower()

    if _is_wechat_delivery(text):
        return DocumentType.IN_ORDER
    if any(w in compact for w in ('送货单', '到货', '采购入库', '供应商发货', '来货', '收货')):
        return DocumentType.IN_ORDER
    if any(w in compact for w in ('销售出库', '客户发货', '发给客户')):
        return DocumentType.SALES_OUT
    if any(w in compact for w in ('领料', '发料', '生产出库')):
        return DocumentType.OUT_ORDER
    if any(w in compact for w in ('调拨', '移库', '转库')):
        return DocumentType.TRANSFER
    if any(w in compact for w in ('盘点', '盘库')):
        return DocumentType.CHECK
    if any(w in compact for w in ('报废', '损坏', '盘亏', '盘盈', '调整')):
        return DocumentType.ADJUSTMENT
    return DocumentType.OTHER


def _is_wechat_delivery(text: str) -> bool:
    """检测微信发货通知格式。"""
    compact = text.strip()
    if not compact:
        return False
    if not re.search(r'(今天|明天|后天|上午|下午|晚上|到货|送货|发货|出货|发)\S{0,20}', compact):
        return False
    if not _parse_material_segments(compact):
        return False
    if any(w in compact for w in ('发给客户', '发往客户', '客户要货', '销售出库')):
        return False
    return True


def _parse_material_segments(text: str) -> list[dict]:
    """解析文本中的物料段。"""
    text = text.strip()
    if not text:
        return []
    normalized = re.sub(r'[\r\n,\uff0c;\uff1b\u3001]+', ' ', text)
    segments = []
    unit_pattern = r'(?:个|只|套|件|箱|包|PCS|pcs|kg|KG|米|支|条)'
    for match in re.finditer(
        r'([A-Za-z0-9_\-\*/\u4e00-\u9fff]{2,40}?)\s*([0-9]+(?:\.[0-9]+)?)\s*(' + unit_pattern + r')?(?=\s|$)',
        normalized,
    ):
        name = (match.group(1) or '').strip()
        qty = float(match.group(2)) if match.group(2) else 0
        unit = (match.group(3) or '').strip()
        if not name or qty <= 0:
            continue
        if re.fullmatch(r'\d+(?:\.\d+)?', name):
            continue
        segments.append({'name': name, 'quantity': round(qty, 2), 'unit': unit, 'raw': match.group(0)})
    return segments


def _extract_supplier(text: str) -> str:
    """从文本提取供应商名称。"""
    text = text.strip()
    patterns = (
        r'(?:今天|明天|后天|上午|下午|晚上)?\s*(?:发|送|出货|发货)\s*([\u4e00-\u9fffA-Za-z0-9_\-]{2,30})',
        r'(?:供应商|厂家)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9_\-]{2,30})',
    )
    stop_words = ('货', '货单', '送货单', '出货通知', '通知', '一下')
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = (match.group(1) or '').strip()
        value = re.split(r'\s|,|，|;|；', value, 1)[0].strip()
        if not value or value in stop_words:
            continue
        return value[:100]
    return ''


def _extract_customer(text: str) -> str:
    """从文本提取客户名称。"""
    text = text.strip()
    patterns = (
        r'(?:客户|客户名称|收货客户)\s*[:：]?\s*([\u4e00-\u9fffA-Za-z0-9_\-]{2,40})',
        r'(?:发给|发货给|送到|发往)\s*([\u4e00-\u9fffA-Za-z0-9_\-]{2,40})',
    )
    bad_prefixes = ('发货', '要货', '出库', '领料')
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = (match.group(1) or '').strip()
        if not value or any(value.startswith(p) for p in bad_prefixes):
            continue
        return value[:100]
    return ''


def _parse_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _compute_overall_confidence(extraction: DocumentExtraction) -> None:
    """计算整体置信度。"""
    if not extraction.lines:
        extraction.overall_confidence = 0.0
        extraction.needs_confirmation = True
        return

    total = len(extraction.lines)
    matched = sum(1 for l in extraction.lines if l.match_method is not None and l.match_method != MatchMethod.NONE)
    high_conf = sum(1 for l in extraction.lines if l.confidence >= CONFIDENCE_THRESHOLDS['high'])

    extraction.matched_lines = matched
    extraction.unmatched_lines = total - matched
    extraction.low_confidence_lines = sum(
        1 for l in extraction.lines
        if l.confidence < CONFIDENCE_THRESHOLDS['low'] and l.match_method != MatchMethod.NONE
    )

    if total > 0:
        extraction.overall_confidence = round(high_conf / total, 4)

    # 有任何未匹配或低置信度行则需要确认
    extraction.needs_confirmation = (
        extraction.unmatched_lines > 0
        or extraction.low_confidence_lines > 0
        or any(l.needs_confirmation for l in extraction.lines)
    )
